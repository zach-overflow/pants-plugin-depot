"""Backend entry point: Pants loads this module when `actionlint_pants_plugin` is in `backend_packages`."""

from typing import TYPE_CHECKING

from actionlint_pants_plugin.goals.lint import rules as lint_rules
from actionlint_pants_plugin.subsystem import rules as subsystem_rules
from actionlint_pants_plugin.target_types import target_types as actionlint_target_types

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules, CollectedTargetTypes


def rules() -> CollectedRules:
    """Return every rule this backend registers with the Pants engine."""
    return (*lint_rules(), *subsystem_rules())


def target_types() -> CollectedTargetTypes:
    """Return every target type this backend registers with the Pants engine."""
    return actionlint_target_types()
