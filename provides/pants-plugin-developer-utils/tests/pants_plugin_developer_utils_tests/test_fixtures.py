from textwrap import dedent

from pants.core.target_types import FileTarget
from pants.engine.addresses import Address
from pants.testutil.rule_runner import RuleRunner

from pants_plugin_developer_utils.testing_utils import RuleRunnerFactory


def test_rule_runner_factory_builds_rule_runner(rule_runner_factory: RuleRunnerFactory) -> None:
    rule_runner = rule_runner_factory(rules=[])

    assert isinstance(rule_runner, RuleRunner)


def test_rule_runner_factory_forwards_kwargs(rule_runner_factory: RuleRunnerFactory) -> None:
    rule_runner = rule_runner_factory(rules=[], target_types=[FileTarget])
    rule_runner.write_files(
        {
            "project/BUILD": dedent(
                """\
                file(name="readme", source="README.md")
                """
            ),
            "project/README.md": "# project\n",
        }
    )

    target = rule_runner.get_target(Address("project", target_name="readme"))

    assert isinstance(target, FileTarget)
