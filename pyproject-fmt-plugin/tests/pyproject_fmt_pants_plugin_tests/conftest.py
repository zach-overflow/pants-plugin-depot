from collections.abc import Callable

from pants.engine.rules import Rule
from pants.engine.unions import UnionRule
from pants.testutil.rule_runner import RuleRunner
import pytest


type RuleRunnerFactory = Callable[[tuple[Rule | UnionRule, ...]], RuleRunner]


@pytest.fixture(scope="function")
def rule_runner_factory() -> RuleRunnerFactory:
    """Factory fixture for generating specific `RuleRunner` fixtures in unit tests."""
    def _factory(rules: tuple[Rule | UnionRule]) -> RuleRunner:
        return RuleRunner(rules=rules)

    return _factory
