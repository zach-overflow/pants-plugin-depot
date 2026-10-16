"""Rules for running `actionlint` during `pants lint` on `github_workflow_source` targets."""

import os.path
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Final

from pants.backend.shell.lint.shellcheck.subsystem import Shellcheck
from pants.core.goals.lint import LintResult, LintTargetsRequest
from pants.core.util_rules import config_files, source_files
from pants.core.util_rules.config_files import find_config_file
from pants.core.util_rules.external_tool import DownloadedExternalTool, download_external_tool
from pants.core.util_rules.partitions import PartitionerType
from pants.core.util_rules.source_files import SourceFilesRequest, determine_source_files
from pants.engine.fs import CreateDigest, Digest, Directory, MergeDigests
from pants.engine.internals.graph import transitive_targets
from pants.engine.intrinsics import create_digest, execute_process, merge_digests
from pants.engine.platform import Platform
from pants.engine.process import Process
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.target import Field, FieldSet, SourcesField, Target, TransitiveTargetsRequest
from pants.option.global_options import GlobalOptions
from pants.util.logging import LogLevel
from pants.util.strutil import pluralize

from actionlint_pants_plugin.subsystem import Actionlint
from actionlint_pants_plugin.target_types import (
    GitHubWorkflowDependenciesField,
    GitHubWorkflowSourceField,
    SkipActionlintField,
)

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules

TOOL_INPUT_DIR: Final = "__actionlint_tool"
"""Sandbox directory the downloaded `actionlint` release is mounted in, as an immutable input shared across runs."""

SHELLCHECK_INPUT_DIR: Final = "__shellcheck_tool"
"""Sandbox directory the downloaded `shellcheck` release is mounted in when the integration is enabled."""

PROJECT_MARKER: Final = ".git"
"""
`actionlint` only treats a directory holding `.github/workflows/` as a repository when it also holds a `.git`
entry, and only inside a repository does it read `.github/actionlint.yaml` and validate `uses: ./...`
references. Every sandbox therefore gets an empty `.git` directory at its root.
"""


@dataclass(frozen=True)
class ActionlintFieldSet(FieldSet):
    """Fields required for a target to be linted by `actionlint`."""

    required_fields: ClassVar[tuple[type[Field], ...]] = (GitHubWorkflowSourceField,)

    source: GitHubWorkflowSourceField
    dependencies: GitHubWorkflowDependenciesField

    @classmethod
    def opt_out(cls, tgt: Target) -> bool:
        return tgt.get(SkipActionlintField).value


class ActionlintRequest(LintTargetsRequest):
    """Unique type for triggering an `actionlint` run as part of the `pants lint` goal."""

    field_set_type = ActionlintFieldSet
    tool_subsystem = Actionlint  # ty: ignore[invalid-assignment]
    partitioner_type = PartitionerType.DEFAULT_SINGLE_PARTITION


def generate_argv(
    actionlint: Actionlint, *, exe: str, shellcheck_exe: str | None, files: Iterable[str]
) -> tuple[str, ...]:
    """
    The `actionlint` command line for one batch.

    `-color` is always passed so the cached result is the same whatever `[GLOBAL].colors` is; Pants strips the
    escape codes afterwards when colors are off. An empty `-shellcheck` or `-pyflakes` value disables that
    integration explicitly instead of leaving it to the sandbox's empty `PATH`. `[actionlint].args` come
    last: `actionlint` keeps the last value of a repeated flag, so they override the plugin's flags.
    """
    argv = [exe, "-color", "-pyflakes=", f"-shellcheck={shellcheck_exe or ''}"]
    if actionlint.config:
        argv.extend(["-config-file", actionlint.config])
    argv.extend(actionlint.args)
    argv.extend(sorted(files))
    return tuple(argv)


@rule(desc="Lint GitHub Actions workflows with `actionlint`", level=LogLevel.DEBUG)
async def run_actionlint(
    request: ActionlintRequest.Batch[ActionlintFieldSet, Any],
    actionlint: Actionlint,
    shellcheck: Shellcheck,
    platform: Platform,
    global_options: GlobalOptions,
) -> LintResult:
    downloaded_actionlint, config_files_found, project_marker, closure = await concurrently(
        download_external_tool(actionlint.get_request(platform)),
        find_config_file(actionlint.config_request()),
        create_digest(CreateDigest([Directory(PROJECT_MARKER)])),
        # The transitive closure, so the local actions and reusable workflows the workflows use are present.
        transitive_targets(
            TransitiveTargetsRequest(field_set.address for field_set in request.elements), **implicitly()
        ),
    )
    downloaded_shellcheck: DownloadedExternalTool | None = (
        await download_external_tool(shellcheck.get_request(platform)) if actionlint.shellcheck else None
    )
    sources = await determine_source_files(
        SourceFilesRequest(tgt[SourcesField] for tgt in closure.closure if tgt.has_field(SourcesField))
    )
    input_digest = await merge_digests(
        MergeDigests((sources.snapshot.digest, config_files_found.snapshot.digest, project_marker))
    )

    immutable_input_digests: dict[str, Digest] = {TOOL_INPUT_DIR: downloaded_actionlint.digest}
    shellcheck_exe: str | None = None
    if downloaded_shellcheck is not None:
        immutable_input_digests[SHELLCHECK_INPUT_DIR] = downloaded_shellcheck.digest
        shellcheck_exe = os.path.join(SHELLCHECK_INPUT_DIR, downloaded_shellcheck.exe)
    files = tuple(field_set.source.file_path for field_set in request.elements)

    result = await execute_process(
        Process(
            argv=generate_argv(
                actionlint,
                exe=os.path.join(TOOL_INPUT_DIR, downloaded_actionlint.exe),
                shellcheck_exe=shellcheck_exe,
                files=files,
            ),
            input_digest=input_digest,
            immutable_input_digests=immutable_input_digests,
            description=f"Run actionlint on {pluralize(len(files), 'file')}.",
            level=LogLevel.DEBUG,
        ),
        **implicitly(),
    )
    return LintResult.create(request, result, output_simplifier=global_options.output_simplifier())


def rules() -> CollectedRules:
    return (*collect_rules(), *config_files.rules(), *source_files.rules(), *ActionlintRequest.rules())
