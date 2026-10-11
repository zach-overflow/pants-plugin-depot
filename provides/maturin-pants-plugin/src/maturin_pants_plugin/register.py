from typing import TYPE_CHECKING

from maturin_pants_plugin.goals.maturin_common import rules as common_rules
from maturin_pants_plugin.goals.package import rules as package_rules
from maturin_pants_plugin.goals.publish import rules as publish_rules
from maturin_pants_plugin.subsystem import rules as subsystem_rules
from maturin_pants_plugin.target_types import target_types as maturin_target_types

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules, CollectedTargetTypes


def rules() -> CollectedRules:
    return (*common_rules(), *package_rules(), *publish_rules(), *subsystem_rules())


def target_types() -> CollectedTargetTypes:
    return maturin_target_types()
