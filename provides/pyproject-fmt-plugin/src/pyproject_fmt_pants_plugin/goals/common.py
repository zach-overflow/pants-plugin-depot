"""Common rules across multiple pants goals with which `pyproject-fmt` integrates."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum, unique

from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.pex import VenvPex, VenvPexProcess, create_venv_pex, setup_venv_pex_process
from pants.core.util_rules.config_files import find_config_file
from pants.core.util_rules.partitions import Partitions
from pants.engine.fs import MergeDigests, PathGlobs
from pants.engine.intrinsics import execute_process, get_digest_entries, merge_digests, path_globs_to_digest
from pants.engine.process import FallibleProcessResult
from pants.engine.rules import Rule, collect_rules, concurrently, implicitly, rule
from pants.engine.unions import UnionRule
from pants.source.filespec import FilespecMatcher
from pants.util.logging import LogLevel
from pants.util.strutil import pluralize

from pyproject_fmt_pants_plugin.subsystem import PyprojectFmt


@unique
class PyprojectFmtMode(StrEnum):
    """Supported modes for `pyproject-fmt`: check mode (fail if changes would occur), or fmt mode (apply changes)."""

    CHECK = "check"
    FORMAT = "format"


@dataclass(frozen=True)
class RunPyprojectFmtRequest:
    """Wrapper for the unique details of a given `pyproject-fmt` run for either `fmt` or `lint` goals."""

    mode: PyprojectFmtMode

    @property
    def is_check(self) -> bool:
        """Returns `True` if the request is for running `pyproject-fmt --check` (via the `pants lint` goal)."""
        return self.mode is PyprojectFmtMode.CHECK

    @property
    def is_format(self) -> bool:
        """Returns `True` if running `pyproject-fmt` without the `--check` flag (via the `pants fmt` goal)."""
        return self.mode is PyprojectFmtMode.CHECK


def common_partition_pyproject_toml_inputs(skip: bool, files: Iterable[str]) -> Partitions:
    """Helper for partitioning the subject pyproject.toml files, regardless of goal being invoked."""
    if skip or not files:
        return Partitions()

    return Partitions.single_partition(
        sorted(FilespecMatcher(includes=["**/pyproject.toml"], excludes=[]).matches(tuple(files)))
    )


@rule(desc="Creates the venv tool pex from which to run `pyproject-fmt`.", level=LogLevel.DEBUG)
async def create_pyproject_fmt_venv_pex(pyproject_fmt: PyprojectFmt) -> VenvPex:
    return await create_venv_pex(
        **implicitly(
            pyproject_fmt.to_pex_request(
                interpreter_constraints=InterpreterConstraints(constraints=pyproject_fmt.interpreter_constraints),
                extra_requirements=pyproject_fmt.requirements,
            )
        )
    )


@rule(
    desc="Calls the underlying tool in a separate process with the goal-specific options + any subsystem settings.",
    level=LogLevel.DEBUG,
)
async def run_pyproject_fmt_process(
    request: RunPyprojectFmtRequest, pyproject_fmt: PyprojectFmt
) -> FallibleProcessResult:
    (config_files, subject_files_digest) = await concurrently(
        find_config_file(pyproject_fmt.config_request()),
        path_globs_to_digest(PathGlobs(["**/pyproject.toml", "pyproject.toml"])),
    )
    conf_filepaths = config_files.snapshot.files
    if len(conf_filepaths) != 1:
        raise ValueError(
            f"Expected exactly 1 shared `pyproject-fmt` config, but found {len(conf_filepaths)} shared configs."
        )

    args: list[str] = ["--config", conf_filepaths[0]]
    if request.is_check:
        args.append("--check")

    (input_digest, ppf_pex, subject_files_entries) = await concurrently(
        merge_digests(MergeDigests([subject_files_digest, config_files.snapshot.digest])),
        create_pyproject_fmt_venv_pex(pyproject_fmt),
        get_digest_entries(subject_files_digest),
    )
    # Final args in the `pyproject-fmt` command should be the paths to the subject `pyproject.toml` files.
    subject_filepaths = tuple(sorted([entry.path for entry in subject_files_entries]))
    args.extend(list(subject_filepaths))

    desc_txt = (
        f"Run pyproject-fmt {'--check' if request.is_check else ''} on {pluralize(len(subject_filepaths), 'file')}."
    )
    venv_pex_process = await setup_venv_pex_process(
        VenvPexProcess(
            ppf_pex,
            argv=args,
            input_digest=input_digest,
            # TODO: determine if the outputs need to be different here for FORMAT mode.
            output_files=subject_filepaths if request.is_format else None,
            description=desc_txt,
            level=LogLevel.DEBUG,
        ),
        **implicitly(),
    )
    return await execute_process(venv_pex_process, **implicitly())


def rules() -> Iterable[Rule | UnionRule]:
    return collect_rules()
