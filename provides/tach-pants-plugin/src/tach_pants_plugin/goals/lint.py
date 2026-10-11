from typing import TYPE_CHECKING

from pants.engine.rules import collect_rules

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


def rules() -> CollectedRules:
    return collect_rules()
