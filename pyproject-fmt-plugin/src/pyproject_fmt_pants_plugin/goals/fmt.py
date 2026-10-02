"""Rules for executing `pyproject-fmt` operations during the `pants fmt` goal execution."""

from collections.abc import Iterable

from pants.core.goals.fmt import FmtFilesRequest, FmtResult, Partitions
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


class PyprojectFmtRequest(FmtFilesRequest):
    """Unique type for triggering a `pyproject-fmt` run as part of the `pants fmt` goal execution."""

    tool_subsystem = PyprojectFmt  # type: ignore[assignment]

    @classproperty
    def tool_name(cls) -> str:
        return "pyproject-fmt format"

    @classproperty
    def tool_id(self) -> str:
        return "pyproject-fmt"


@rule(desc="Partitions the `pyproject.toml` input files for formatting.", level=LogLevel.DEBUG)
async def partition_inputs(request: PyprojectFmtRequest.PartitionRequest, pyproject_fmt: PyprojectFmt) -> Partitions:
    return common_partition_pyproject_toml_inputs(pyproject_fmt.skip, request.files)


@rule(desc="Auto-formats all requested `pyproject.toml` files with `pyproject-fmt`", level=LogLevel.DEBUG)
async def run_pyproject_fmt_formatting(request: PyprojectFmtRequest.Batch, pyproject_fmt: PyprojectFmt) -> FmtResult:
    result = await run_pyproject_fmt_process(RunPyprojectFmtRequest(mode=PyprojectFmtMode.FORMAT), pyproject_fmt)
    return await FmtResult.create(request, result)


def rules() -> Iterable[Rule | UnionRule]:
    return (*collect_rules(), *PyprojectFmtRequest.rules())
