from pants.testutil.rule_runner import RuleRunner

from oras_pants_plugin import register


def test_rules() -> None:
    assert len(tuple(register.rules())) > 0


def test_target_types() -> None:
    assert tuple(register.target_types()) == ()


def test_backend_registers_with_the_engine() -> None:
    rule_runner = RuleRunner(rules=register.rules(), target_types=register.target_types())

    assert rule_runner.build_root
