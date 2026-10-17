"""
Pants `rule` definitions for running `ty` during a `pants check` goal invocation.

Adapted from the builtin `pants.backend.python.typecheck.mypy` and `pants.backend.python.typecheck.pyright`
backends. `ty` is a static binary, so unlike mypy it is downloaded rather than installed from a resolve. Like
pyright, it resolves third-party imports from a virtual environment Pants builds from the checked targets'
requirements, and first-party imports from the Pants source roots.

See Also:
    https://www.pantsbuild.org/stable/docs/writing-plugins/common-plugin-tasks/add-a-typechecker
"""

import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from pants.backend.python.subsystems.setup import PythonSetup
from pants.backend.python.target_types import InterpreterConstraintsField, PythonResolveField, PythonSourceField
from pants.backend.python.util_rules import pex_from_targets
from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints

# Pants' own `ty`-style partitioning helper has no public equivalent.
from pants.backend.python.util_rules.partition import _partition_by_interpreter_constraints_and_resolve  # ruff: ignore[PLC2701]
from pants.backend.python.util_rules.pex import PexRequest, VenvPexProcess, VenvPexRequest, create_pex, create_venv_pex
from pants.backend.python.util_rules.pex_environment import PexEnvironment
from pants.backend.python.util_rules.pex_from_targets import RequirementsPexRequest
from pants.backend.python.util_rules.python_sources import PythonSourceFilesRequest, prepare_python_sources
from pants.core.goals.check import CheckRequest, CheckResult, CheckResults, CheckSubsystem
from pants.core.util_rules import config_files
from pants.core.util_rules.config_files import find_config_file
from pants.core.util_rules.external_tool import download_external_tool
from pants.core.util_rules.source_files import SourceFilesRequest, determine_source_files
from pants.engine.collection import Collection
from pants.engine.fs import Digest, MergeDigests
from pants.engine.internals.graph import resolve_coarsened_targets as coarsened_targets_get
from pants.engine.intrinsics import execute_process, get_digest_contents, merge_digests
from pants.engine.platform import Platform
from pants.engine.process import Process, ProcessCacheScope, execute_process_or_raise
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.target import CoarsenedTargets, CoarsenedTargetsRequest, Field, FieldSet, Target
from pants.engine.unions import UnionRule
from pants.option.global_options import GlobalOptions
from pants.util.logging import LogLevel
from pants.util.ordered_set import FrozenOrderedSet, OrderedSet
from pants.util.strutil import pluralize

from ty_pants_plugin.skip_fields import SkipTyField
from ty_pants_plugin.subsystem import Ty

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


@dataclass(frozen=True)
class TyFieldSet(FieldSet):
    """Fields required for a target to be eligible as a subject for `ty` type checking."""

    required_fields: ClassVar[tuple[type[Field], ...]] = (PythonSourceField,)

    sources: PythonSourceField
    resolve: PythonResolveField
    interpreter_constraints: InterpreterConstraintsField

    @classmethod
    def opt_out(cls, tgt: Target) -> bool:
        return tgt.get(SkipTyField).value


class TyRequest(CheckRequest[TyFieldSet]):
    """`CheckRequest` for `ty` type checking."""

    field_set_type = TyFieldSet
    tool_name = Ty.options_scope


@dataclass(frozen=True)
class TyPartition:
    """The targets of one `ty` run: they share a resolve and interpreter constraints, so one environment fits all."""

    field_sets: FrozenOrderedSet[TyFieldSet]
    root_targets: CoarsenedTargets
    resolve_description: str | None
    interpreter_constraints: InterpreterConstraints

    def description(self) -> str:
        ics = str(sorted(str(c) for c in self.interpreter_constraints))
        return f"{self.resolve_description}, {ics}" if self.resolve_description else ics


class TyPartitions(Collection[TyPartition]):
    """Collection of `TyPartition` instances."""


@dataclass(frozen=True)
class TyConfigFile:
    """The discovered `ty` config file and whether it, or `[ty].args`, pins the Python version."""

    digest: Digest
    python_version_configured: bool


def python_version_configured(ty: Ty, config_contents: Iterable[bytes]) -> bool:
    """
    Whether the user pinned the Python version through `[ty].args` or the config file.

    Pants otherwise derives `--python-version` from the partition's interpreter constraints, mimicking the
    builtin mypy backend. A user setting wins, as `ty` rejects conflicting values on the command line.
    """
    if any("python-version" in arg or "target-version" in arg for arg in ty.args):
        return True
    return any(b"python-version" in content for content in config_contents)


def generate_argv(
    ty: Ty, *, exe: str, venv_dir: str, source_roots: Iterable[str], python_version: str | None, files: Iterable[str]
) -> tuple[str, ...]:
    """
    The `ty check` command line for one partition.

    Colors are always requested so the process result is cache-hit regardless of the `--colors` setting;
    Pants strips the escape codes afterwards when colors are off.
    """
    argv = [exe, "check", "--color=always", f"--python={venv_dir}"]
    argv.extend(f"--extra-search-path={source_root}" for source_root in source_roots)
    if python_version:
        argv.append(f"--python-version={python_version}")
    if ty.config:
        argv.append(f"--config-file={ty.config}")
    argv.extend(ty.args)
    argv.extend(files)
    return tuple(argv)


@rule(desc="Find the `ty` config file", level=LogLevel.DEBUG)
async def setup_ty_config(ty: Ty) -> TyConfigFile:
    found = await find_config_file(ty.config_request())
    contents = await get_digest_contents(found.snapshot.digest)
    return TyConfigFile(
        digest=found.snapshot.digest,
        python_version_configured=python_version_configured(ty, (file.content for file in contents)),
    )


@rule(desc="Determine if necessary to partition `ty` input", level=LogLevel.DEBUG)
async def determine_ty_partitions(request: TyRequest, ty: Ty, python_setup: PythonSetup) -> TyPartitions:
    resolve_and_interpreter_constraints_to_field_sets = _partition_by_interpreter_constraints_and_resolve(
        request.field_sets, python_setup
    )
    coarsened_targets = await coarsened_targets_get(
        CoarsenedTargetsRequest(field_set.address for field_set in request.field_sets), **implicitly()
    )
    coarsened_targets_by_address = coarsened_targets.by_address()

    return TyPartitions(
        TyPartition(
            FrozenOrderedSet(field_sets),
            CoarsenedTargets(OrderedSet(coarsened_targets_by_address[field_set.address] for field_set in field_sets)),
            resolve if len(python_setup.resolves) > 1 else None,
            interpreter_constraints or ty.interpreter_constraints,
        )
        for (resolve, interpreter_constraints), field_sets in sorted(
            resolve_and_interpreter_constraints_to_field_sets.items()
        )
    )


@rule(desc="Typecheck a partition with `ty`", level=LogLevel.DEBUG)
async def typecheck_ty_partition(
    partition: TyPartition,
    ty: Ty,
    config_file: TyConfigFile,
    check_subsystem: CheckSubsystem,
    pex_environment: PexEnvironment,
    python_setup: PythonSetup,
    platform: Platform,
    global_options: GlobalOptions,
) -> CheckResult:
    root_sources_get = determine_source_files(SourceFilesRequest(fs.sources for fs in partition.field_sets))
    # The transitive closure, so first-party imports of the checked files resolve.
    closure_sources_get = prepare_python_sources(
        PythonSourceFilesRequest(partition.root_targets.closure()), **implicitly()
    )
    requirements_pex_get = create_pex(
        **implicitly(
            RequirementsPexRequest(
                (fs.address for fs in partition.field_sets),
                hardcoded_interpreter_constraints=partition.interpreter_constraints,
            )
        )
    )
    downloaded_ty_get = download_external_tool(ty.get_request(platform))
    root_sources, closure_sources, requirements_pex, downloaded_ty = await concurrently(
        root_sources_get, closure_sources_get, requirements_pex_get, downloaded_ty_get
    )

    # `ty` needs a real virtual environment on disk to resolve third-party imports from. The venv is seeded
    # under the named caches directory (not the sandbox) so `ty` can be pointed at it by absolute path, as
    # the builtin pyright backend does. Pex creates the venv lazily, hence the no-op run that materializes
    # it. That run is per-session: the named cache may be pruned between Pants runs.
    complete_pex_env = pex_environment.in_workspace()
    requirements_venv_pex = await create_venv_pex(
        VenvPexRequest(
            PexRequest(
                output_filename="requirements_venv.pex",
                internal_only=True,
                pex_path=[requirements_pex],
                interpreter_constraints=partition.interpreter_constraints,
            ),
            complete_pex_env,
        ),
        **implicitly(),
    )
    await execute_process_or_raise(
        **implicitly(
            VenvPexProcess(
                requirements_venv_pex,
                description="Materialize the virtual environment for `ty`",
                argv=["-c", "''"],
                cache_scope=ProcessCacheScope.PER_SESSION,
            )
        )
    )
    venv_dir = os.path.join(complete_pex_env.pex_root, requirements_venv_pex.venv_rel_dir)

    input_digest = await merge_digests(
        MergeDigests([closure_sources.source_files.snapshot.digest, downloaded_ty.digest, config_file.digest])
    )
    python_version = (
        None
        if config_file.python_version_configured
        else partition.interpreter_constraints.minimum_python_version(python_setup.interpreter_versions_universe)
    )
    argv = generate_argv(
        ty,
        exe=downloaded_ty.exe,
        venv_dir=venv_dir,
        source_roots=closure_sources.source_roots,
        python_version=python_version,
        files=root_sources.snapshot.files,
    )
    result = await execute_process(
        Process(
            argv=argv,
            input_digest=input_digest,
            description=f"Run ty on {pluralize(len(root_sources.snapshot.files), 'file')}.",
            level=LogLevel.DEBUG,
            cache_scope=check_subsystem.default_process_cache_scope,
        ),
        **implicitly(),
    )
    return CheckResult.from_fallible_process_result(
        result, partition_description=partition.description(), output_simplifier=global_options.output_simplifier()
    )


@rule(desc="Typecheck using `ty`", level=LogLevel.DEBUG)
async def ty_typecheck(request: TyRequest, ty: Ty) -> CheckResults:
    if ty.skip:
        return CheckResults([], checker_name=request.tool_name)

    partitions = await determine_ty_partitions(request, **implicitly())
    partitioned_results = await concurrently(
        typecheck_ty_partition(partition, **implicitly()) for partition in partitions
    )
    return CheckResults(partitioned_results, checker_name=request.tool_name)


def rules() -> CollectedRules:
    return (*collect_rules(), *config_files.rules(), *pex_from_targets.rules(), UnionRule(CheckRequest, TyRequest))
