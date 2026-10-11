import annotationlib
from typing import TypeAliasType

from pants_plugin_developer_utils import CollectedRules, CollectedTargetTypes


def _source(alias: TypeAliasType) -> str:
    return annotationlib.call_evaluate_function(alias.evaluate_value, annotationlib.Format.STRING)


def test_collected_rules_alias() -> None:
    assert isinstance(CollectedRules, TypeAliasType)
    assert _source(CollectedRules) == "Iterable[Rule | UnionRule]"


def test_collected_target_types_alias() -> None:
    assert isinstance(CollectedTargetTypes, TypeAliasType)
    assert _source(CollectedTargetTypes) == "Iterable[type[Target]]"
