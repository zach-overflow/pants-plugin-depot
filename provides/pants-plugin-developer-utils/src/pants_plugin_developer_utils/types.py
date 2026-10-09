"""Collection of various type aliases for common pantsbuild plugin code type hinting scenarios."""

from collections.abc import Iterable

from pants.engine.rules import Rule
from pants.engine.target import Target
from pants.engine.unions import UnionRule

type CollectedRules = Iterable[Rule | UnionRule]
"""Type alias for the return type of a `rules` function in a plugin's `register.py` file."""


type CollectedTargetTypes = Iterable[type[Target]]
"""Type alias for the return type of a `targets` function in a plugin's `register.py` file."""
