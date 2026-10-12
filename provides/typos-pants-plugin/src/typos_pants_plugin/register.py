"""Backend entry point: Pants loads this module when `typos_pants_plugin` is in `backend_packages`."""

from typing import TYPE_CHECKING

from typos_pants_plugin.goals.common import rules as common_rules
from typos_pants_plugin.goals.fix import rules as fix_rules
from typos_pants_plugin.goals.lint import rules as lint_rules
from typos_pants_plugin.subsystem import rules as subsystem_rules

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


def rules() -> CollectedRules:
    """Return every rule this backend registers with the Pants engine."""
    return (*common_rules(), *fix_rules(), *lint_rules(), *subsystem_rules())
