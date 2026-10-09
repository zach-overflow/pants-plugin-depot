"""Rules for executing `pyproject-fmt --check` operations during the `pants lint` goal execution."""

from pants.core.goals.lint import LintFilesRequest, LintResult, Partitions
from pants.engine.fs import PathGlobs
from pants.engine.intrinsics import digest_to_snapshot
from pants.engine.rules import collect_rules, implicitly, rule
from pants.util.logging import LogLevel
from pants.util.meta import classproperty

from pants_plugin_developer_utils import CollectedRules
from pyproject_fmt_pants_plugin.goals.common import (
    PyprojectFmtMode,
    RunPyprojectFmtRequest,
    common_partition_pyproject_toml_inputs,
    run_pyproject_fmt_process,
)
from pyproject_fmt_pants_plugin.subsystem import PyprojectFmt


class PyprojectFmtLintRequest(LintFilesRequest):
    """Request class for running `pyproject-fmt --check` as part of a `pants lint` call."""

    tool_subsystem = PyprojectFmt  # type: ignore[assignment]

    @classproperty
    def tool_name(cls) -> str:
        return "pyproject-fmt check"

    @classproperty
    def tool_id(self) -> str:
        return "pyproject-fmt"


@rule(desc="Partitions the `pyproject.toml` input files for linting.", level=LogLevel.DEBUG)
async def partition_inputs(
    request: PyprojectFmtLintRequest.PartitionRequest, pyproject_fmt: PyprojectFmt
) -> Partitions:
    return common_partition_pyproject_toml_inputs(pyproject_fmt.skip, request.files)


@rule(desc="Run `pyproject-fmt --check` against `pyproject.toml` files.", level=LogLevel.DEBUG)
async def run_pyproject_fmt_check(request: PyprojectFmtLintRequest.Batch) -> LintResult:
    snapshot = await digest_to_snapshot(**implicitly(PathGlobs(request.elements)))
    result = await run_pyproject_fmt_process(
        RunPyprojectFmtRequest(mode=PyprojectFmtMode.CHECK, snapshot=snapshot), **implicitly()
    )
    return LintResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        linter_name=request.tool_name,
        partition_description=request.partition_metadata.description,
    )


def rules() -> CollectedRules:
    return (*collect_rules(), *PyprojectFmtLintRequest.rules())
