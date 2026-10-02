"""Backend entry point: Pants loads this module when `pyproject_fmt_pants_plugin` is in `backend_packages`."""

from collections.abc import Iterable

from pants.engine.rules import Rule
from pants.engine.unions import UnionRule

from pyproject_fmt_pants_plugin.goals.common import rules as common_rules
from pyproject_fmt_pants_plugin.goals.fmt import rules as fmt_rules
from pyproject_fmt_pants_plugin.goals.lint import rules as lint_rules
from pyproject_fmt_pants_plugin.subsystem import rules as subsystem_rules


def rules() -> Iterable[Rule | UnionRule]:
    """Return every rule this backend registers with the Pants engine."""
    return (*common_rules(), *fmt_rules(), *lint_rules(), *subsystem_rules())
