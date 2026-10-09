"""Collection of types for common type hints in pantsbuild plugin test code."""

from collections.abc import Iterable
from typing import Any, NotRequired, Protocol, TypedDict, Unpack

from pants.build_graph.build_file_aliases import BuildFileAliases
from pants.engine.environment import EnvironmentName
from pants.engine.rules import Rule
from pants.engine.unions import UnionRule
from pants.goal.auxiliary_goal import AuxiliaryGoal
from pants.testutil.rule_runner import QueryRule, RuleRunner
from pants.util.logging import LogLevel

from pants_plugin_developer_utils import CollectedTargetTypes


class RuleRunnerFactory(Protocol):
    """Type alias for the return type of the `pants_plugin_test_utils.rule_runner_factory` fixture factory."""

    def __call__(self, rules: RuleRunnerCollectedRules, **kwargs: Unpack[RuleRunnerOptionalKwargs]) -> RuleRunner: ...


type RuleRunnerCollectedRules = Iterable[Rule | UnionRule | QueryRule]


class RuleRunnerOptionalKwargs(TypedDict):
    """
    Collection of keyword argument names and their associated types which may be optionally provided to the
    `pants.testutil.rule_runner.RuleRunner` constructor.
    """

    target_types: NotRequired[CollectedTargetTypes | None]
    objects: NotRequired[dict[str, Any] | None]
    aliases: NotRequired[Iterable[BuildFileAliases] | None]
    context_aware_object_factories: NotRequired[dict[str, Any] | None]
    isolated_local_store: NotRequired[bool]
    preserve_tmpdirs: NotRequired[bool]
    ca_certs_path: NotRequired[str | None]
    bootstrap_args: NotRequired[Iterable[str]]
    extra_session_values: NotRequired[dict[Any, Any] | None]
    max_workunit_verbosity: NotRequired[LogLevel]
    inherent_environment: NotRequired[EnvironmentName | None]
    is_bootstrap: NotRequired[bool]
    auxiliary_goals: NotRequired[Iterable[type[AuxiliaryGoal]] | None]
