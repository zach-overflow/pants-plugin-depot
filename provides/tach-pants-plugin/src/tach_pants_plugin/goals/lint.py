from pants.engine.rules import collect_rules

from pants_plugin_developer_utils import CollectedRules


def rules() -> CollectedRules:
    return collect_rules()
