"""Backend entry point: Pants loads this module when `oras_pants_plugin` is in `backend_packages`."""

from typing import TYPE_CHECKING

from oras_pants_plugin.goals.common import rules as common_rules
from oras_pants_plugin.goals.package import rules as package_rules
from oras_pants_plugin.goals.publish import rules as publish_rules
from oras_pants_plugin.subsystem import rules as subsystem_rules
from oras_pants_plugin.target_types import target_types as oras_target_types

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules, CollectedTargetTypes


def rules() -> CollectedRules:
    """Return every rule this backend registers with the Pants engine."""
    return (*common_rules(), *package_rules(), *publish_rules(), *subsystem_rules())


def target_types() -> CollectedTargetTypes:
    """The plugin registers the `oci_artifact` target."""
    return oras_target_types()
