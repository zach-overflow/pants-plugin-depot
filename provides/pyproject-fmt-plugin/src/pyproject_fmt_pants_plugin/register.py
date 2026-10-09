"""Backend entry point: Pants loads this module when `pyproject_fmt_pants_plugin` is in `backend_packages`."""

from pants_plugin_developer_utils import CollectedRules
from pyproject_fmt_pants_plugin.goals.common import rules as common_rules
from pyproject_fmt_pants_plugin.goals.fmt import rules as fmt_rules
from pyproject_fmt_pants_plugin.goals.lint import rules as lint_rules
from pyproject_fmt_pants_plugin.subsystem import rules as subsystem_rules


def rules() -> CollectedRules:
    """Return every rule this backend registers with the Pants engine."""
    return (*common_rules(), *fmt_rules(), *lint_rules(), *subsystem_rules())
