from typing import TYPE_CHECKING

from ty_pants_plugin.check import rules as check_rules
from ty_pants_plugin.skip_fields import rules as skip_field_rules
from ty_pants_plugin.subsystem import rules as subsystem_rules

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


def rules() -> CollectedRules:
    return (*check_rules(), *skip_field_rules(), *subsystem_rules())
