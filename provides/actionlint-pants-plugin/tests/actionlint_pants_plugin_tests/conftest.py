from collections.abc import Iterable
from typing import Any, Protocol

import pytest
from pants.core.goals.lint import LintResult
from pants.core.target_types import FilesGeneratorTarget, FileTarget
from pants.core.util_rules import external_tool
from pants.core.util_rules.external_tool import UnsupportedVersionUsage
from pants.core.util_rules.partitions import Partitions
from pants.engine.addresses import Address
from pants.testutil.option_util import create_subsystem
from pants.testutil.rule_runner import QueryRule, RuleRunner

from actionlint_pants_plugin import subsystem
from actionlint_pants_plugin.goals import lint
from actionlint_pants_plugin.goals.lint import ActionlintFieldSet, ActionlintRequest
from actionlint_pants_plugin.subsystem import Actionlint
from actionlint_pants_plugin.target_types import GitHubWorkflowSourcesGeneratorTarget, GitHubWorkflowSourceTarget
from pants_plugin_developer_utils.testing_utils import (
    RuleRunnerFactory,
    rule_runner_factory,  # noqa: F401
)

WORKFLOWS_DIR = ".github/workflows"
"""Where GitHub reads workflows from; `actionlint` recognizes a repository by this directory and a `.git` entry."""

# A `RuleRunner` ignores dot-directories like a default `pants.toml` does, which would hide `.github/`.
SHOW_GITHUB_DIR_BOOTSTRAP_ARGS = ("--pants-ignore=+['!.github/']",)


class ActionlintFactory(Protocol):
    """Type of the factory returned by the `actionlint_factory` fixture."""

    def __call__(self, **overrides: Any) -> Actionlint: ...


@pytest.fixture(scope="function")
def actionlint_factory() -> ActionlintFactory:
    """Factory fixture building an `Actionlint` subsystem with default option values, without the engine."""

    def _factory(**overrides: Any) -> Actionlint:
        options: dict[str, Any] = {
            "version": Actionlint.default_version,
            "known_versions": list(Actionlint.default_known_versions),
            "url_template": Actionlint.default_url_template,
            "url_platform_mapping": dict(Actionlint.default_url_platform_mapping),
            "use_unsupported_version": UnsupportedVersionUsage.RaiseError,
            "skip": False,
            "args": [],
            "config": None,
            "config_discovery": True,
            "shellcheck": True,
        }
        options.update(overrides)
        return create_subsystem(Actionlint, **options)

    return _factory


@pytest.fixture(scope="function")
def actionlint_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:  # noqa: F811
    """Integration `RuleRunner`: downloads the real `actionlint` and `shellcheck` binaries (network)."""
    return rule_runner_factory(
        rules=[
            *lint.rules(),
            *subsystem.rules(),
            *external_tool.rules(),
            QueryRule(Partitions, [ActionlintRequest.PartitionRequest]),
            QueryRule(LintResult, [ActionlintRequest.Batch]),
        ],
        target_types=[
            GitHubWorkflowSourceTarget,
            GitHubWorkflowSourcesGeneratorTarget,
            FilesGeneratorTarget,
            FileTarget,
        ],
        bootstrap_args=SHOW_GITHUB_DIR_BOOTSTRAP_ARGS,
    )


def workflow_address(file_name: str) -> Address:
    """The address of the `github_workflow_source` target generated for `.github/workflows/<file_name>`."""
    return Address(WORKFLOWS_DIR, relative_file_path=file_name)


def run_lint(rule_runner: RuleRunner, addresses: Iterable[Address]) -> list[LintResult]:
    """Partitions the applicable targets as `pants lint` would, then runs `actionlint` on each partition as one batch."""
    targets = [rule_runner.get_target(address) for address in addresses]
    field_sets = tuple(ActionlintFieldSet.create(tgt) for tgt in targets if ActionlintFieldSet.is_applicable(tgt))
    partitions = rule_runner.request(Partitions, [ActionlintRequest.PartitionRequest(field_sets)])
    return [
        rule_runner.request(
            LintResult, [ActionlintRequest.Batch(ActionlintRequest.tool_name, partition.elements, partition.metadata)]
        )
        for partition in partitions
    ]
