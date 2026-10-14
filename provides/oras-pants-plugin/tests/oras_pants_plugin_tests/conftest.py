from typing import Any, Protocol

import pytest
from pants.backend.python import target_types_rules
from pants.backend.python.target_types import PexBinariesGeneratorTarget, PexBinary
from pants.core.goals.publish import CheckSkipResult, PublishProcesses
from pants.core.util_rules import env_vars, external_tool
from pants.core.util_rules.external_tool import UnsupportedVersionUsage
from pants.engine.addresses import Address
from pants.engine.fs import Digest, DigestContents
from pants.engine.process import Process, ProcessResult
from pants.engine.unions import UnionMembership, UnionRule
from pants.testutil.option_util import create_subsystem
from pants.testutil.rule_runner import QueryRule, RuleRunner

from oras_pants_plugin import fields, subsystem
from oras_pants_plugin.goals import publish
from oras_pants_plugin.goals.publish import OrasPublishPexRequest, OrasPublishSkipRequest
from oras_pants_plugin.subsystem import Oras
from pants_plugin_developer_utils.testing_utils import (
    RuleRunnerFactory,
    rule_runner_factory,  # noqa: F401
)

APP_DIR = "src/app"
"""Directory of the `pex_binary` target the tests publish."""

APP_ADDRESS = Address(APP_DIR, target_name="app")
"""Address of the `pex_binary` target the tests publish."""

PEX_FIELDS_UNION_MEMBERSHIP = UnionMembership.from_rules(rule for rule in fields.rules() if isinstance(rule, UnionRule))
"""Makes the plugin's fields known to `pex_binary` targets built by hand, without the engine."""


class OrasFactory(Protocol):
    """Type of the factory returned by the `oras_factory` fixture."""

    def __call__(self, **overrides: Any) -> Oras: ...


@pytest.fixture(scope="function")
def oras_factory() -> OrasFactory:
    """Factory fixture building an `Oras` subsystem with default option values, without the engine."""

    def _factory(**overrides: Any) -> Oras:
        options: dict[str, Any] = {
            "version": Oras.default_version,
            "known_versions": list(Oras.default_known_versions),
            "url_template": Oras.default_url_template,
            "url_platform_mapping": dict(Oras.default_url_platform_mapping),
            "use_unsupported_version": UnsupportedVersionUsage.RaiseError,
            "skip": False,
            "args": [],
            "extra_env_vars": [],
        }
        options.update(overrides)
        return create_subsystem(Oras, **options)

    return _factory


@pytest.fixture(scope="function")
def oras_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:  # noqa: F811
    """Integration `RuleRunner`: requesting `PublishProcesses` downloads the real `oras` binary (network)."""
    return rule_runner_factory(
        rules=[
            *publish.rules(),
            *fields.rules(),
            *subsystem.rules(),
            *external_tool.rules(),
            *env_vars.rules(),
            *target_types_rules.rules(),
            QueryRule(PublishProcesses, [OrasPublishPexRequest]),
            QueryRule(CheckSkipResult, [OrasPublishSkipRequest]),
            QueryRule(ProcessResult, [Process]),
            QueryRule(DigestContents, [Digest]),
        ],
        target_types=[PexBinary, PexBinariesGeneratorTarget],
    )


def make_pex_binary(**field_values: Any) -> PexBinary:
    """A `pex_binary` target at `APP_ADDRESS` carrying the plugin's fields, built without the engine."""
    return PexBinary(
        {"entry_point": "main.py", **field_values}, APP_ADDRESS, union_membership=PEX_FIELDS_UNION_MEMBERSHIP
    )
