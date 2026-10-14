"""Backend entry point: Pants loads this module when `oras_pants_plugin` is in `backend_packages`."""

from typing import TYPE_CHECKING

from oras_pants_plugin.fields import rules as field_rules
from oras_pants_plugin.goals.publish import rules as publish_rules
from oras_pants_plugin.subsystem import rules as subsystem_rules

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules, CollectedTargetTypes


def rules() -> CollectedRules:
    """Return every rule this backend registers with the Pants engine."""
    return (*field_rules(), *publish_rules(), *subsystem_rules())


def target_types() -> CollectedTargetTypes:
    """The plugin adds fields to the builtin `pex_binary` targets and registers no target types of its own."""
    return ()
