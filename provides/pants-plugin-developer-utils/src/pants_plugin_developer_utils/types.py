"""
Collection of various type aliases for common pantsbuild plugin code type hinting scenarios.

`type` aliases evaluate lazily, and the package is a pytest plugin loaded in environments without Pants, so the
Pants imports are type-checking only.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pants.engine.rules import Rule
    from pants.engine.target import Target
    from pants.engine.unions import UnionRule

type CollectedRules = Iterable[Rule | UnionRule]
"""Type alias for the return type of a `rules` function in a plugin's `register.py` file."""


type CollectedTargetTypes = Iterable[type[Target]]
"""Type alias for the return type of a `target_types` function in a plugin's `register.py` file."""
