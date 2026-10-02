"""Rules for executing `pyproject-fmt --check` operations during the `pants lint` goal execution."""

from collections.abc import Iterable

from pants.core.goals.lint import LintFilesRequest, LintResult, Partitions
from pants.engine.rules import Rule, collect_rules, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel
from pants.util.meta import classproperty

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
async def run_pyproject_fmt_check(request: PyprojectFmtLintRequest.Batch, pyproject_fmt: PyprojectFmt) -> LintResult:
    result = await run_pyproject_fmt_process(RunPyprojectFmtRequest(mode=PyprojectFmtMode.CHECK), pyproject_fmt)
    return LintResult.create(request, result)


def rules() -> Iterable[Rule | UnionRule]:
    return (*collect_rules(), *PyprojectFmtLintRequest.rules())
