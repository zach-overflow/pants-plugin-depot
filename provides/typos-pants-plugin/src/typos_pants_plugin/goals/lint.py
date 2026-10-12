"""Rules for running `typos` during `pants lint`: every typo is reported and nothing is written."""

from typing import TYPE_CHECKING, Any

from pants.core.goals.lint import LintFilesRequest, LintResult, Partitions
from pants.engine.fs import PathGlobs
from pants.engine.intrinsics import digest_to_snapshot, execute_process
from pants.engine.rules import collect_rules, implicitly, rule
from pants.util.logging import LogLevel

from typos_pants_plugin.goals.common import (
    TyposMode,
    TyposPartitionRequest,
    TyposProcessRequest,
    partition_typos_inputs,
    setup_typos_process,
)
from typos_pants_plugin.subsystem import Typos

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class TyposLintRequest(LintFilesRequest):
    """Unique type for triggering a `typos` check-mode run as part of the `pants lint` goal."""

    tool_subsystem = Typos  # ty: ignore[invalid-assignment]


@rule(desc="Partition the files for `typos` to check", level=LogLevel.DEBUG)
async def partition_typos_lint_inputs(request: TyposLintRequest.PartitionRequest) -> Partitions[str, Any]:
    return await partition_typos_inputs(TyposPartitionRequest(request.files), **implicitly())


@rule(desc="Check spelling with `typos`", level=LogLevel.DEBUG)
async def run_typos_lint(request: TyposLintRequest.Batch) -> LintResult:
    snapshot = await digest_to_snapshot(**implicitly(PathGlobs(request.elements)))
    process = await setup_typos_process(
        TyposProcessRequest(snapshot=snapshot, files=snapshot.files, mode=TyposMode.LINT), **implicitly()
    )
    result = await execute_process(process, **implicitly())
    return LintResult.create(request, result)


def rules() -> CollectedRules:
    return (*collect_rules(), *TyposLintRequest.rules())
