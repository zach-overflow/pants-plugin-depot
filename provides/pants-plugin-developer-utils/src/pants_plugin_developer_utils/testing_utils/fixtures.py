"""Collection of pytest fixtures for testing pantsbuild plugins."""

from typing import Unpack

import pytest
from pants.testutil.rule_runner import RuleRunner

from pants_plugin_developer_utils.testing_utils.testing_types import RuleRunnerFactory, RuleRunnerOptionalKwargs
from pants_plugin_developer_utils.types import CollectedRules


@pytest.fixture(scope="function")
def rule_runner_factory() -> RuleRunnerFactory:
    """Fixture factory for generating a `pants.testutil.rule_runner.RuleRunner` instance based on the input params."""

    def _factory(rules: CollectedRules, **kwargs: Unpack[RuleRunnerOptionalKwargs]) -> RuleRunner:
        return RuleRunner(rules=rules, **kwargs)

    return _factory
