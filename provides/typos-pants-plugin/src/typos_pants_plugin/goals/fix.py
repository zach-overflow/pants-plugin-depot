"""Rules for running `typos` during `pants fix`: the unambiguous corrections are written back to the workspace."""

from typing import TYPE_CHECKING, Any

from pants.core.goals.fix import FixFilesRequest, FixResult, Partitions
from pants.engine.intrinsics import execute_process
from pants.engine.process import ProcessExecutionFailure
from pants.engine.rules import collect_rules, implicitly, rule
from pants.option.global_options import KeepSandboxes
from pants.util.logging import LogLevel

from typos_pants_plugin.goals.common import (
    TYPOS_FOUND_EXIT_CODE,
    TyposMode,
    TyposPartitionRequest,
    TyposProcessRequest,
    partition_typos_inputs,
    setup_typos_process,
)
from typos_pants_plugin.subsystem import Typos

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class TyposFixRequest(FixFilesRequest):
    """Unique type for triggering a `typos --write-changes` run as part of the `pants fix` goal."""

    tool_subsystem = Typos  # type: ignore[assignment]
    # `pants lint` runs `typos` in check mode through `TyposLintRequest` rather than diffing this fixer's
    # output: `typos` only writes corrections for typos with a single candidate, and never renames files, so
    # the check mode reports strictly more than what a `fix` run changes.
    enable_lint_rules = False


@rule(desc="Partition the files for `typos` to fix", level=LogLevel.DEBUG)
async def partition_typos_fix_inputs(request: TyposFixRequest.PartitionRequest) -> Partitions[Any]:
    return await partition_typos_inputs(TyposPartitionRequest(request.files), **implicitly())


@rule(desc="Fix typos with `typos`", level=LogLevel.DEBUG)
async def run_typos_fix(request: TyposFixRequest.Batch, keep_sandboxes: KeepSandboxes) -> FixResult:
    process = await setup_typos_process(
        TyposProcessRequest(snapshot=request.snapshot, files=request.files, mode=TyposMode.FIX), **implicitly()
    )
    result = await execute_process(process, **implicitly())
    # `typos --write-changes` writes every unambiguous correction, then still exits 2 if ambiguous typos remain
    # for `lint` to report. Any other failure is a usage or config error that MUST abort the goal.
    if result.exit_code not in (0, TYPOS_FOUND_EXIT_CODE):
        raise ProcessExecutionFailure.from_result(result, process.description, keep_sandboxes)
    return await FixResult.create(request, result)


def rules() -> CollectedRules:
    return (*collect_rules(), *TyposFixRequest.rules())
