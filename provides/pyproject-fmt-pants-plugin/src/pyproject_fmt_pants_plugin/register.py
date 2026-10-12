"""Backend entry point: Pants loads this module when `pyproject_fmt_pants_plugin` is in `backend_packages`."""

from typing import TYPE_CHECKING

from pyproject_fmt_pants_plugin.goals.common import rules as common_rules
from pyproject_fmt_pants_plugin.goals.fmt import rules as fmt_rules
from pyproject_fmt_pants_plugin.subsystem import rules as subsystem_rules

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


def rules() -> CollectedRules:
    """Return every rule this backend registers with the Pants engine."""
    return (*common_rules(), *fmt_rules(), *subsystem_rules())
