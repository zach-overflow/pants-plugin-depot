from textwrap import dedent

import pytest
from pants.engine.addresses import Address, Addresses
from pants.engine.internals.scheduler import ExecutionError
from pants.engine.target import HydratedSources, HydrateSourcesRequest, Targets
from pants.testutil.rule_runner import QueryRule, RuleRunner

from actionlint_pants_plugin.goals.lint import ActionlintFieldSet
from actionlint_pants_plugin.target_types import (
    GitHubWorkflowDependenciesField,
    GitHubWorkflowSourceField,
    GitHubWorkflowSourcesGeneratorTarget,
    GitHubWorkflowSourceTarget,
    SkipActionlintField,
    target_types,
)
from pants_plugin_developer_utils.testing_utils import RuleRunnerFactory


@pytest.fixture(scope="function")
def targets_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:
    """Engine-only `RuleRunner`: target generation and hydration, no `actionlint` run."""
    return rule_runner_factory(
        rules=[QueryRule(Targets, [Addresses]), QueryRule(HydratedSources, [HydrateSourcesRequest])],
        target_types=[GitHubWorkflowSourceTarget, GitHubWorkflowSourcesGeneratorTarget],
    )


def _generated_addresses(rule_runner: RuleRunner, generator: Address) -> list[str]:
    return sorted(str(tgt.address) for tgt in rule_runner.request(Targets, [Addresses([generator])]))


def test_target_types_registers_both_targets() -> None:
    assert tuple(target_types()) == (GitHubWorkflowSourceTarget, GitHubWorkflowSourcesGeneratorTarget)


def test_generator_yields_one_target_per_workflow_file(targets_rule_runner: RuleRunner) -> None:
    targets_rule_runner.write_files(
        {
            "workflows/BUILD": "github_workflow_sources()\n",
            "workflows/ci.yml": "",
            "workflows/release.yaml": "",
            "workflows/README.md": "",
            "workflows/notes.json": "",
        }
    )

    assert _generated_addresses(targets_rule_runner, Address("workflows")) == [
        "workflows/ci.yml",
        "workflows/release.yaml",
    ]
    generated = targets_rule_runner.get_target(Address("workflows", relative_file_path="ci.yml"))
    assert isinstance(generated, GitHubWorkflowSourceTarget)
    assert generated[GitHubWorkflowSourceField].file_path == "workflows/ci.yml"
    assert generated[SkipActionlintField].value is False
    assert generated[GitHubWorkflowDependenciesField].value is None


def test_explicit_sources_globs(targets_rule_runner: RuleRunner) -> None:
    targets_rule_runner.write_files(
        {
            "workflows/BUILD": "github_workflow_sources(sources=['ci_*.yml', '!ci_draft.yml'])\n",
            "workflows/ci_build.yml": "",
            "workflows/ci_draft.yml": "",
            "workflows/release.yml": "",
        }
    )

    assert _generated_addresses(targets_rule_runner, Address("workflows")) == ["workflows/ci_build.yml"]


def test_moved_fields_land_on_generated_targets(targets_rule_runner: RuleRunner) -> None:
    """`dependencies` and `skip_actionlint` are accepted by the generator but live on the generated targets."""
    targets_rule_runner.write_files(
        {
            "workflows/BUILD": dedent(
                """\
                github_workflow_sources(dependencies=["actions/hello:action"], skip_actionlint=True)
                """
            ),
            "workflows/ci.yml": "",
        }
    )

    generator = targets_rule_runner.get_target(Address("workflows"))
    generated = targets_rule_runner.get_target(Address("workflows", relative_file_path="ci.yml"))

    assert isinstance(generator, GitHubWorkflowSourcesGeneratorTarget)
    assert not generator.has_field(GitHubWorkflowDependenciesField)
    assert not generator.has_field(SkipActionlintField)
    assert generated[GitHubWorkflowDependenciesField].value == ("actions/hello:action",)
    assert generated[SkipActionlintField].value is True


def test_overrides_apply_per_file(targets_rule_runner: RuleRunner) -> None:
    targets_rule_runner.write_files(
        {
            "workflows/BUILD": dedent(
                """\
                github_workflow_sources(
                    overrides={
                        "release.yml": {"skip_actionlint": True},
                        "ci.yml": {"dependencies": ["actions/hello:action"]},
                    },
                )
                """
            ),
            "workflows/ci.yml": "",
            "workflows/release.yml": "",
        }
    )

    ci = targets_rule_runner.get_target(Address("workflows", relative_file_path="ci.yml"))
    release = targets_rule_runner.get_target(Address("workflows", relative_file_path="release.yml"))

    assert ci[SkipActionlintField].value is False
    assert ci[GitHubWorkflowDependenciesField].value == ("actions/hello:action",)
    assert ActionlintFieldSet.is_applicable(ci)
    assert release[SkipActionlintField].value is True
    assert release[GitHubWorkflowDependenciesField].value is None
    assert not ActionlintFieldSet.is_applicable(release)


def test_single_file_target(targets_rule_runner: RuleRunner) -> None:
    targets_rule_runner.write_files(
        {
            "workflows/BUILD": 'github_workflow_source(name="deploy", source="deploy.yml", skip_actionlint=True)\n',
            "workflows/deploy.yml": "",
        }
    )

    target = targets_rule_runner.get_target(Address("workflows", target_name="deploy"))

    assert isinstance(target, GitHubWorkflowSourceTarget)
    assert target[GitHubWorkflowSourceField].file_path == "workflows/deploy.yml"
    assert target[SkipActionlintField].value is True
    assert ActionlintFieldSet.opt_out(target) is True
    assert not ActionlintFieldSet.is_applicable(target)


def test_rejects_unexpected_file_extension(targets_rule_runner: RuleRunner) -> None:
    targets_rule_runner.write_files(
        {"workflows/BUILD": 'github_workflow_source(name="bad", source="bad.json")\n', "workflows/bad.json": "{}"}
    )
    target = targets_rule_runner.get_target(Address("workflows", target_name="bad"))

    with pytest.raises(ExecutionError, match=r"bad\.json"):
        targets_rule_runner.request(HydratedSources, [HydrateSourcesRequest(target[GitHubWorkflowSourceField])])
