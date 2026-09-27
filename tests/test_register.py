from pants.testutil.rule_runner import RuleRunner

from pyproject_fmt_pants_plugin import register


def test_backend_registers_with_the_engine() -> None:
    rule_runner = RuleRunner(rules=register.rules(), target_types=register.target_types())

    assert rule_runner.build_root
