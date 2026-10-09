"""Common rules across multiple pants goals with which `pyproject-fmt` integrates."""

import os
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum, unique

from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.pex import VenvPex, VenvPexProcess, create_venv_pex, setup_venv_pex_process
from pants.core.util_rules.config_files import find_config_file
from pants.core.util_rules.partitions import Partitions
from pants.engine.fs import Digest, MergeDigests, Snapshot
from pants.engine.intrinsics import execute_process, merge_digests
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.source.filespec import FilespecMatcher
from pants.util.logging import LogLevel

from pants_plugin_developer_utils import CollectedRules
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
    snapshot: Snapshot
    """The `pyproject.toml` files of the goal's batch."""

    @property
    def is_check(self) -> bool:
        """Returns `True` if the request is for running `pyproject-fmt --check` (via the `pants lint` goal)."""
        return self.mode is PyprojectFmtMode.CHECK

    @property
    def is_format(self) -> bool:
        """Returns `True` if running `pyproject-fmt` without the `--check` flag (via the `pants fmt` goal)."""
        return self.mode is PyprojectFmtMode.FORMAT


@dataclass(frozen=True)
class PyprojectFmtResult:
    """Aggregate of the per-file `pyproject-fmt` processes of one `RunPyprojectFmtRequest`."""

    exit_code: int
    stdout: str
    stderr: str
    output_digest: Digest
    """The processed `pyproject.toml` files. Empty in check mode."""


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
async def run_pyproject_fmt_process(request: RunPyprojectFmtRequest, pyproject_fmt: PyprojectFmt) -> PyprojectFmtResult:
    (config_files, ppf_pex) = await concurrently(
        find_config_file(pyproject_fmt.config_request()), create_pyproject_fmt_venv_pex(**implicitly())
    )
    input_digest = await merge_digests(MergeDigests([request.snapshot.digest, config_files.snapshot.digest]))

    args: list[str] = []
    # `--config` only accepts a standalone `pyproject-fmt.toml`. Passing a `pyproject.toml` fails on its
    # `[project]` table; `pyproject-fmt` reads `[tool.pyproject-fmt]` tables from each input file itself.
    shared_config = pyproject_fmt.config or next(
        (path for path in config_files.snapshot.files if os.path.basename(path) == "pyproject-fmt.toml"), None
    )
    if shared_config:
        args.extend(["--config", shared_config])
    if request.is_check:
        args.append("--check")

    # `pyproject-fmt` stops after the first input it changes (`any()` over a generator), so run one process per file.
    processes = await concurrently(
        setup_venv_pex_process(
            VenvPexProcess(
                ppf_pex,
                argv=(*args, filepath),
                input_digest=input_digest,
                output_files=(filepath,) if request.is_format else None,
                description=f"Run pyproject-fmt{' --check' if request.is_check else ''} on {filepath}.",
                level=LogLevel.DEBUG,
            ),
            **implicitly(),
        )
        for filepath in request.snapshot.files
    )
    results = await concurrently(execute_process(process, **implicitly()) for process in processes)
    output_digest = await merge_digests(MergeDigests(result.output_digest for result in results))
    return PyprojectFmtResult(
        exit_code=max((result.exit_code for result in results), default=0),
        stdout="".join(result.stdout.decode() for result in results),
        stderr="".join(result.stderr.decode() for result in results),
        output_digest=output_digest,
    )


def rules() -> CollectedRules:
    return collect_rules()
