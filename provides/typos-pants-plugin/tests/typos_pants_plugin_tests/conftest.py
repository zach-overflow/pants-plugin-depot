from collections.abc import Iterable
from typing import Any, Protocol

import pytest
from pants.core.goals.fix import FixResult
from pants.core.goals.lint import LintResult
from pants.core.util_rules import external_tool
from pants.core.util_rules.external_tool import UnsupportedVersionUsage
from pants.core.util_rules.partitions import Partitions
from pants.engine.fs import Digest, DigestContents, PathGlobs, Snapshot
from pants.engine.process import FallibleProcessResult, Process
from pants.testutil.option_util import create_subsystem
from pants.testutil.rule_runner import QueryRule, RuleRunner

from pants_plugin_developer_utils.testing_utils import (
    RuleRunnerFactory,
    rule_runner_factory,  # ruff: ignore[unused-import]
)
from typos_pants_plugin import subsystem
from typos_pants_plugin.goals import common, fix, lint
from typos_pants_plugin.goals.common import TyposProcessRequest
from typos_pants_plugin.goals.fix import TyposFixRequest
from typos_pants_plugin.goals.lint import TyposLintRequest
from typos_pants_plugin.subsystem import Typos


class TyposFactory(Protocol):
    """Type of the factory returned by the `typos_factory` fixture."""

    def __call__(self, **overrides: Any) -> Typos: ...


@pytest.fixture(scope="function")
def typos_factory() -> TyposFactory:
    """Factory fixture building a `Typos` subsystem with default option values, without the engine."""

    def _factory(**overrides: Any) -> Typos:
        options: dict[str, Any] = {
            "version": Typos.default_version,
            "known_versions": list(Typos.default_known_versions),
            "url_template": Typos.default_url_template,
            "url_platform_mapping": dict(Typos.default_url_platform_mapping),
            "use_unsupported_version": UnsupportedVersionUsage.RaiseError,
            "skip": False,
            "args": [],
            "config": None,
            "config_discovery": True,
            "glob_pattern": ["**/*"],
        }
        options.update(overrides)
        return create_subsystem(Typos, **options)

    return _factory


@pytest.fixture(scope="function")
def typos_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:  # ruff: ignore[redefined-while-unused]
    """Integration `RuleRunner`: downloads the real `typos` binary (network) and runs it on the written files."""
    return rule_runner_factory(
        rules=[
            *common.rules(),
            *fix.rules(),
            *lint.rules(),
            *subsystem.rules(),
            *external_tool.rules(),
            QueryRule(Partitions, [TyposFixRequest.PartitionRequest]),
            QueryRule(Partitions, [TyposLintRequest.PartitionRequest]),
            QueryRule(FixResult, [TyposFixRequest.Batch]),
            QueryRule(LintResult, [TyposLintRequest.Batch]),
            QueryRule(Process, [TyposProcessRequest]),
            QueryRule(FallibleProcessResult, [Process]),
            QueryRule(Snapshot, [PathGlobs]),
            QueryRule(DigestContents, [Digest]),
        ]
    )


def run_fix(rule_runner: RuleRunner, files: Iterable[str]) -> list[FixResult]:
    """Partitions `files` as `pants fix` would, then runs `typos` on each partition as a single batch."""
    partitions = rule_runner.request(Partitions, [TyposFixRequest.PartitionRequest(tuple(files))])
    results: list[FixResult] = []
    for partition in partitions:
        snapshot = rule_runner.request(Snapshot, [PathGlobs(partition.elements)])
        batch = TyposFixRequest.Batch(TyposFixRequest.tool_name, partition.elements, partition.metadata, snapshot)
        results.append(rule_runner.request(FixResult, [batch]))
    return results


def run_lint(rule_runner: RuleRunner, files: Iterable[str]) -> list[LintResult]:
    """Partitions `files` as `pants lint` would, then runs `typos` on each partition as a single batch."""
    partitions = rule_runner.request(Partitions, [TyposLintRequest.PartitionRequest(tuple(files))])
    return [
        rule_runner.request(
            LintResult, [TyposLintRequest.Batch(TyposLintRequest.tool_name, partition.elements, partition.metadata)]
        )
        for partition in partitions
    ]


def read_digest(rule_runner: RuleRunner, digest: Digest) -> dict[str, str]:
    """The decoded contents of every file in `digest`, keyed by path."""
    return {file.path: file.content.decode() for file in rule_runner.request(DigestContents, [digest])}
