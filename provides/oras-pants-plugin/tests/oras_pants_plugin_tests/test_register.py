from pants.core.goals import package as core_package
from pants.core.util_rules import env_vars, external_tool
from pants.testutil.rule_runner import RuleRunner

from oras_pants_plugin import register
from oras_pants_plugin.target_types import OCIArtifact


def test_rules() -> None:
    assert len(tuple(register.rules())) > 0


def test_target_types() -> None:
    assert tuple(register.target_types()) == (OCIArtifact,)


def test_backend_registers_with_the_engine() -> None:
    """The plugin's rules call into core `package`, external tool and env var rules, which every real run loads."""
    rule_runner = RuleRunner(
        rules=[*register.rules(), *core_package.rules(), *external_tool.rules(), *env_vars.rules()],
        target_types=register.target_types(),
    )

    assert rule_runner.build_root
