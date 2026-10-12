"""Target types for GitHub Actions workflow files: one target per workflow, generated from a `sources` glob."""

from typing import TYPE_CHECKING, Final

from pants.backend.adhoc.target_types import AdhocToolDependenciesField
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    BoolField,
    MultipleSourcesField,
    OverridesField,
    SingleSourceField,
    Target,
    TargetFilesGenerator,
    generate_file_based_overrides_field_help_message,
    generate_multiple_sources_field_help_message,
)
from pants.util.strutil import softwrap

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedTargetTypes

WORKFLOW_FILE_EXTENSIONS: Final[tuple[str, str]] = (".yaml", ".yml")
"""The file extensions GitHub Actions accepts for workflow files."""


class GitHubWorkflowSourceField(SingleSourceField):
    """The workflow file of a `github_workflow_source` target."""

    expected_file_extensions = WORKFLOW_FILE_EXTENSIONS
    uses_source_roots = False


class GitHubWorkflowDependenciesField(AdhocToolDependenciesField):
    """Targets the workflow refers to, included in the sandbox so `actionlint` can validate the references."""

    help = softwrap(
        """
        Addresses to targets the workflow uses, e.g. the `files` target holding the `action.yml` of a local
        action (`uses: ./.github/actions/<name>`), a reusable workflow (`uses: ./.github/workflows/<file>`),
        or a script a `run:` step invokes.

        `actionlint` validates local action and reusable workflow references against the files it finds next
        to the workflow, and `pants --changed-since` re-lints the workflow whenever a dependency changes.
        """
    )


class SkipActionlintField(BoolField):
    """Opt-out field for a single workflow file."""

    alias = "skip_actionlint"
    default = False
    help = "If true, don't run `actionlint` on this target's workflow file."


class GitHubWorkflowSourceTarget(Target):
    """Single target (non-generator), corresponding to a single GitHub Actions workflow file."""

    alias = "github_workflow_source"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        GitHubWorkflowDependenciesField,
        GitHubWorkflowSourceField,
        SkipActionlintField,
    )
    help = "A single GitHub Actions workflow YAML file."


class GitHubWorkflowSourcesGeneratingSourcesField(MultipleSourcesField):
    """Multi-source field for the `GitHubWorkflowSourcesGeneratorTarget` target."""

    default = tuple(f"*{extension}" for extension in WORKFLOW_FILE_EXTENSIONS)
    expected_file_extensions = WORKFLOW_FILE_EXTENSIONS
    help = generate_multiple_sources_field_help_message("Example: `sources=['ci_*.yaml', 'release.yml', '!draft.yml']`")
    uses_source_roots = False


class GitHubWorkflowSourcesOverridesField(OverridesField):
    """Per-file field overrides for the targets a `github_workflow_sources` generator produces."""

    help = generate_file_based_overrides_field_help_message(
        GitHubWorkflowSourceTarget.alias,
        """
        overrides={
            "release.yml": {"skip_actionlint": True},
            "ci.yml": {"dependencies": [".github/actions/setup:action"]},
        }
        """,
    )


class GitHubWorkflowSourcesGeneratorTarget(TargetFilesGenerator):
    """Generator target which generates an individual `GitHubWorkflowSourceTarget` instance per file."""

    alias = "github_workflow_sources"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        GitHubWorkflowSourcesGeneratingSourcesField,
        GitHubWorkflowSourcesOverridesField,
    )
    generated_target_cls = GitHubWorkflowSourceTarget
    copied_fields = COMMON_TARGET_FIELDS
    moved_fields = (GitHubWorkflowDependenciesField, SkipActionlintField)
    help = f"Generate a `{GitHubWorkflowSourceTarget.alias}` target for each file matching the `sources` field."


def target_types() -> CollectedTargetTypes:
    return (GitHubWorkflowSourceTarget, GitHubWorkflowSourcesGeneratorTarget)
