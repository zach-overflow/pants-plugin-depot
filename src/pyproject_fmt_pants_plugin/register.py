"""Backend entry point: Pants loads this module when `pyproject_fmt_pants_plugin` is in `backend_packages`."""

from collections.abc import Iterable

from pants.engine.rules import Rule
from pants.engine.target import Target
from pants.engine.unions import UnionRule


def rules() -> Iterable[Rule | UnionRule]:
    """Return every rule this backend registers with the Pants engine."""
    return ()


def target_types() -> Iterable[type[Target]]:
    """Return every target type this backend registers with the Pants engine."""
    return ()
