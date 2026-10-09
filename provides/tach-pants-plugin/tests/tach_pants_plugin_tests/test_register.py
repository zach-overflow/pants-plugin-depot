from pants.testutil.rule_runner import RuleRunner

from tach_pants_plugin import register


def test_backend_registers_with_the_engine() -> None:
    rule_runner = RuleRunner(rules=register.rules())

    assert rule_runner.build_root
