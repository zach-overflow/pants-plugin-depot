"""
Collection of pytest fixtures for testing pantsbuild plugins.

Registered as a pytest plugin through the `pytest11` entry point, so the fixtures are available wherever the
wheel is installed. `pants.testutil` is imported lazily: pytest loads this module at startup in every
environment that has the wheel, including ones without `pantsbuild.pants.testutil`.
"""

from typing import TYPE_CHECKING, Unpack

import pytest

if TYPE_CHECKING:
    from pants.testutil.rule_runner import RuleRunner

    from pants_plugin_developer_utils.testing_utils.testing_types import (
        RuleRunnerCollectedRules,
        RuleRunnerFactory,
        RuleRunnerOptionalKwargs,
    )


@pytest.fixture(scope="function")
def rule_runner_factory() -> RuleRunnerFactory:
    """Fixture factory for generating a `pants.testutil.rule_runner.RuleRunner` instance based on the input params."""

    def _factory(rules: RuleRunnerCollectedRules, **kwargs: Unpack[RuleRunnerOptionalKwargs]) -> RuleRunner:
        from pants.testutil.rule_runner import RuleRunner  # ruff: ignore[import-outside-top-level]

        return RuleRunner(rules=rules, **kwargs)

    return _factory
