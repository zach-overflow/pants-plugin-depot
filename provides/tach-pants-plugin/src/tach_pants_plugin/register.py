from pants_plugin_developer_utils import CollectedRules
from tach_pants_plugin.goals.lint import rules as lint_rules
from tach_pants_plugin.skip_fields import rules as skip_field_rules
from tach_pants_plugin.subsystem import rules as subsystem_rules


def rules() -> CollectedRules:
    return (*lint_rules(), *skip_field_rules(), *subsystem_rules())
