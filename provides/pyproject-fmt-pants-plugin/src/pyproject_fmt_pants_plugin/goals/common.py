"""Rules shared by the `pyproject-fmt` goal integrations."""

import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.pex import VenvPex, VenvPexProcess, create_venv_pex, setup_venv_pex_process
from pants.core.util_rules.config_files import find_config_file
from pants.core.util_rules.partitions import Partitions
from pants.engine.fs import Digest, MergeDigests, Snapshot
from pants.engine.intrinsics import execute_process, merge_digests
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.source.filespec import FilespecMatcher
from pants.util.logging import LogLevel

from pyproject_fmt_pants_plugin.subsystem import PyprojectFmt

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


@dataclass(frozen=True)
class RunPyprojectFmtRequest:
    """Wrapper for the unique details of a given `pyproject-fmt` run."""

    snapshot: Snapshot
    """The `pyproject.toml` files of the goal's batch."""


@dataclass(frozen=True)
class PyprojectFmtResult:
    """Aggregate of the per-file `pyproject-fmt` processes of one `RunPyprojectFmtRequest`."""

    exit_code: int
    stdout: str
    stderr: str
    output_digest: Digest
    """The formatted `pyproject.toml` files."""


def common_partition_pyproject_toml_inputs(*, skip: bool, files: Iterable[str]) -> Partitions[str, Any]:
    """Helper for partitioning the subject pyproject.toml files, regardless of goal being invoked."""
    files = tuple(files)
    if skip or not files:
        return Partitions()

    return Partitions.single_partition(
        sorted(FilespecMatcher(includes=["**/pyproject.toml"], excludes=[]).matches(files))
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


def get_pyproject_fmt_argv(extra_args: Iterable[str], shared_config_filepath: str | None) -> tuple[str, ...]:
    """
    Builds the arguments shared by every `pyproject-fmt` process of a run, without the input file.

    `pyproject-fmt` treats CLI values as defaults, so `--config` and the per-file `[tool.pyproject-fmt]` table
    override `extra_args` regardless of argument order.
    """
    argv: list[str] = []
    if shared_config_filepath:
        argv.extend(["--config", shared_config_filepath])
    argv.extend(extra_args)
    return tuple(argv)


@rule(desc="Calls the underlying tool in a separate process with any subsystem settings.", level=LogLevel.DEBUG)
async def run_pyproject_fmt_process(request: RunPyprojectFmtRequest, pyproject_fmt: PyprojectFmt) -> PyprojectFmtResult:
    (config_files, ppf_pex) = await concurrently(
        find_config_file(pyproject_fmt.config_request()), create_pyproject_fmt_venv_pex(**implicitly())
    )
    input_digest = await merge_digests(MergeDigests([request.snapshot.digest, config_files.snapshot.digest]))

    # `--config` only accepts a standalone `pyproject-fmt.toml`. Passing a `pyproject.toml` fails on its
    # `[project]` table; `pyproject-fmt` reads `[tool.pyproject-fmt]` tables from each input file itself.
    shared_config = pyproject_fmt.config or next(
        (path for path in config_files.snapshot.files if os.path.basename(path) == "pyproject-fmt.toml"), None
    )
    args = get_pyproject_fmt_argv(extra_args=pyproject_fmt.args, shared_config_filepath=shared_config)

    # `pyproject-fmt` stops after the first input it changes (`any()` over a generator), so run one process per file.
    processes = await concurrently(
        setup_venv_pex_process(
            VenvPexProcess(
                ppf_pex,
                argv=(*args, filepath),
                input_digest=input_digest,
                output_files=(filepath,),
                description=f"Run pyproject-fmt on {filepath}.",
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
