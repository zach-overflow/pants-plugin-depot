import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from pants.backend.python.util_rules.pex import VenvPex, VenvPexProcess, create_venv_pex, setup_venv_pex_process
from pants.core.util_rules.env_vars import environment_vars_subset
from pants.core.util_rules.source_files import SourceFilesRequest, determine_source_files
from pants.engine.env_vars import EnvironmentVarsRequest
from pants.engine.fs import EMPTY_DIGEST, Digest, Snapshot
from pants.engine.internals.graph import transitive_targets
from pants.engine.process import Process, ProcessCacheScope
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.target import Field, FieldSet, SourcesField, TransitiveTargetsRequest
from pants.util.frozendict import FrozenDict
from pants.util.logging import LogLevel
from pants.util.strutil import softwrap

from maturin_pants_plugin.subsystem import Maturin
from maturin_pants_plugin.target_types import (
    CargoTomlField,
    MaturinWheelDependenciesField,
    MaturinWheelSourcesField,
    PyProjectTomlField,
)

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules

MATURIN_WHEELS_OUT_DIR = "__maturin_wheels__"
"""Sandbox directory `maturin build --out` writes to. Stripped from the digest so wheels land flat in `dist/`."""

MATURIN_CARGO_TARGET_CACHE_PATH = ".maturin_cargo_target"
MATURIN_CARGO_TARGET_CACHE = FrozenDict({"maturin_cargo_target": MATURIN_CARGO_TARGET_CACHE_PATH})
"""Append-only named cache holding cargo's `target/` directory, so builds in fresh sandboxes stay incremental."""

MATURIN_BASE_ENV_VAR_NAMES = ("PATH", "HOME", "CARGO_HOME", "RUSTUP_HOME")
"""Always passed to `maturin` processes: a sandboxed process otherwise has no `PATH` to find `cargo` or pythons."""

MATURIN_UPLOAD_ENV_VAR_NAMES = ("MATURIN_PYPI_TOKEN", "MATURIN_USERNAME", "MATURIN_PASSWORD")
"""Credentials `maturin upload` reads from the environment."""


@dataclass(frozen=True)
class MaturinFieldSet(FieldSet):
    """Fields shared by the `package` and `publish` field sets of a `maturin_wheel` target."""

    required_fields: ClassVar[tuple[type[Field], ...]] = (MaturinWheelSourcesField, CargoTomlField, PyProjectTomlField)

    sources: MaturinWheelSourcesField
    cargo_toml: CargoTomlField
    pyproject_toml: PyProjectTomlField
    dependencies: MaturinWheelDependenciesField


def construct_maturin_build_argv(maturin: Maturin, cargo_toml_filepath: str) -> tuple[str, ...]:
    """Returns the arguments of a `maturin build` invocation, without the leading `maturin`."""
    argv: list[str] = [
        "build",
        "--out",
        MATURIN_WHEELS_OUT_DIR,
        "--target-dir",
        MATURIN_CARGO_TARGET_CACHE_PATH,
        "--manifest-path",
        cargo_toml_filepath,
        "--bindings",
        maturin.bindings,
        "--compatibility",
        maturin.compatibility,
    ]
    for interpreter in maturin.interpreter:
        argv.extend(["--interpreter", interpreter])
    if maturin.jobs is not None:
        argv.extend(["--jobs", str(maturin.jobs)])
    if maturin.profile_guided_optimization:
        argv.append("--pgo")
    if maturin.release:
        argv.append("--release")
    return tuple(argv)


def construct_maturin_upload_argv(maturin: Maturin, repository: str, wheel_relpaths: Iterable[str]) -> tuple[str, ...]:
    """Returns the arguments of a `maturin upload` invocation for one repository, without the leading `maturin`."""
    argv: list[str] = ["upload", "--non-interactive"]
    if repository.startswith("@"):
        argv.extend(["--repository", repository[1:]])
    else:
        argv.extend(["--repository-url", repository])
    if maturin.skip_existing:
        argv.append("--skip-existing")
    argv.extend(wheel_relpaths)
    return tuple(argv)


@dataclass(frozen=True)
class MaturinProcessRequest:
    """One `maturin` invocation. The engine turns it into a `Process` via `setup_maturin_process`."""

    argv: tuple[str, ...]
    description: str
    input_digest: Digest = EMPTY_DIGEST
    output_directories: tuple[str, ...] = ()
    extra_env_var_names: tuple[str, ...] = ()
    cache_scope: ProcessCacheScope = ProcessCacheScope.SUCCESSFUL


class InvalidMaturinWheelError(Exception):
    """Raised when a `maturin_wheel` target's manifests are laid out in a way `maturin build` cannot consume."""


@dataclass(frozen=True)
class MaturinSources:
    """Every file of a `maturin_wheel` target and its transitive dependencies, at repo-relative paths."""

    snapshot: Snapshot


@rule(desc="Gather the sources of a `maturin_wheel` target and its dependencies", level=LogLevel.DEBUG)
async def get_maturin_sources(field_set: MaturinFieldSet) -> MaturinSources:
    cargo_toml, pyproject_toml = field_set.cargo_toml.file_path, field_set.pyproject_toml.file_path
    if os.path.dirname(cargo_toml) != os.path.dirname(pyproject_toml):
        raise InvalidMaturinWheelError(
            softwrap(
                f"""
                The `{field_set.pyproject_toml.alias}` of {field_set.address} ({pyproject_toml}) must be in the same
                directory as its `{field_set.cargo_toml.alias}` ({cargo_toml}): `maturin` looks for `pyproject.toml`
                next to the `Cargo.toml` given as `--manifest-path`.
                """
            )
        )
    closure = await transitive_targets(TransitiveTargetsRequest([field_set.address]), **implicitly())
    # Dependencies such as `file` or `python_sources` targets bring their own sources fields, so collect every one.
    sources_fields = [
        field for target in closure.closure for field in target.field_values.values() if isinstance(field, SourcesField)
    ]
    source_files = await determine_source_files(SourceFilesRequest(sources_fields))
    missing = [manifest for manifest in (cargo_toml, pyproject_toml) if manifest not in source_files.files]
    if missing:
        raise InvalidMaturinWheelError(
            softwrap(
                f"""
                The `{field_set.sources.alias}` of {field_set.address} do not include {", ".join(missing)}.
                `maturin build` needs both `{field_set.cargo_toml.alias}` and `{field_set.pyproject_toml.alias}`, so
                add them to `{field_set.sources.alias}`, or make sure the files exist.
                """
            )
        )
    return MaturinSources(source_files.snapshot)


@rule(desc="Create the venv pex that runs `maturin`", level=LogLevel.DEBUG)
async def create_maturin_venv_pex(maturin: Maturin) -> VenvPex:
    # Pants leaves the constraints blank for lockfile-backed tools, which would fall back to `[python]` ones and may
    # pick an interpreter the 3.14-only lockfile cannot satisfy. The tool's own constraints are authoritative.
    return await create_venv_pex(
        **implicitly(maturin.to_pex_request(interpreter_constraints=maturin.interpreter_constraints))
    )


@rule(desc="Set up a `maturin` process", level=LogLevel.DEBUG)
async def setup_maturin_process(request: MaturinProcessRequest, maturin: Maturin) -> Process:
    venv_pex, env = await concurrently(
        create_maturin_venv_pex(**implicitly()),
        environment_vars_subset(
            EnvironmentVarsRequest(
                [*MATURIN_BASE_ENV_VAR_NAMES, *maturin.extra_env_vars, *request.extra_env_var_names]
            ),
            **implicitly(),
        ),
    )
    return await setup_venv_pex_process(
        VenvPexProcess(
            venv_pex,
            argv=request.argv,
            description=request.description,
            level=LogLevel.DEBUG,
            input_digest=request.input_digest,
            extra_env=env,
            output_directories=request.output_directories or None,
            cache_scope=request.cache_scope,
            append_only_caches=MATURIN_CARGO_TARGET_CACHE,
        ),
        **implicitly(),
    )


def rules() -> CollectedRules:
    """Returns the common, non-goal-specific rules for the maturin pants plugin."""
    return collect_rules()
