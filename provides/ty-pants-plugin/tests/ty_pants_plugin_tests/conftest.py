from typing import Any

import pytest
from pants.backend.python import target_types_rules
from pants.backend.python.target_types import PythonRequirementTarget, PythonSourcesGeneratorTarget
from pants.core.goals.check import CheckResults
from pants.core.util_rules import external_tool
from pants.core.util_rules.external_tool import UnsupportedVersionUsage
from pants.testutil.option_util import create_subsystem
from pants.testutil.rule_runner import QueryRule, RuleRunner

from pants_plugin_developer_utils.testing_utils import (
    RuleRunnerFactory,
    rule_runner_factory,  # noqa: F401
)
from ty_pants_plugin import check, skip_fields, subsystem
from ty_pants_plugin.check import TyPartitions, TyRequest
from ty_pants_plugin.subsystem import Ty


def make_ty(**overrides: Any) -> Ty:
    """Builds a `Ty` subsystem with default option values, without the engine. Keyword args override options."""
    options: dict[str, Any] = {
        "version": Ty.default_version,
        "known_versions": list(Ty.default_known_versions),
        "url_template": Ty.default_url_template,
        "url_platform_mapping": dict(Ty.default_url_platform_mapping),
        "use_unsupported_version": UnsupportedVersionUsage.RaiseError,
        "skip": False,
        "args": [],
        "config": None,
        "config_discovery": True,
        "interpreter_constraints": ["CPython>=3.10,<3.16"],
    }
    options.update(overrides)
    return create_subsystem(Ty, **options)


@pytest.fixture(scope="function")
def ty_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:  # noqa: F811
    """
    Integration `RuleRunner`: downloads the real `ty` binary and builds a real requirements venv (network).
    Pins the checked code's interpreter constraints to the interpreter the tests run under.
    """
    rule_runner = rule_runner_factory(
        rules=[
            *check.rules(),
            *skip_fields.rules(),
            *subsystem.rules(),
            *external_tool.rules(),
            *target_types_rules.rules(),
            QueryRule(CheckResults, [TyRequest]),
            QueryRule(TyPartitions, [TyRequest]),
        ],
        target_types=[PythonSourcesGeneratorTarget, PythonRequirementTarget],
    )
    set_ty_options(rule_runner)
    return rule_runner


def set_ty_options(rule_runner: RuleRunner, *extra_args: str) -> None:
    """(Re)sets the `RuleRunner` options: the base options every integration test needs plus `extra_args`."""
    rule_runner.set_options(
        # Mirror `[python].pip_version` in `pants.toml`: Pants' default pip predates CPython 3.14.
        ["--python-pip-version=latest", *extra_args],
        # Pin the checked code to the interpreter the tests run under. Set through the environment, not a
        # flag: a flag-ranked value overrides every target's `interpreter_constraints` field.
        env={"PANTS_PYTHON_INTERPRETER_CONSTRAINTS": "['CPython>=3.14,<3.15']"},
        env_inherit={"PATH", "PYENV_ROOT", "HOME"},
    )
