from typing import TYPE_CHECKING

from pants.backend.python.target_types import (
    PythonSourcesGeneratorTarget,
    PythonSourceTarget,
    PythonTestsGeneratorTarget,
    PythonTestTarget,
    PythonTestUtilsGeneratorTarget,
)
from pants.engine.target import BoolField

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class SkipTyField(BoolField):
    """Field for the Python source targets to opt out of `ty` type checking."""

    alias = "skip_ty"
    default = False
    help = "If true, don't run `ty` type checking on this target's code."


def rules() -> CollectedRules:
    """Registers `skip_ty` on every builtin target type that `ty` can check."""
    return (
        PythonSourcesGeneratorTarget.register_plugin_field(SkipTyField),
        PythonSourceTarget.register_plugin_field(SkipTyField),
        PythonTestsGeneratorTarget.register_plugin_field(SkipTyField),
        PythonTestTarget.register_plugin_field(SkipTyField),
        PythonTestUtilsGeneratorTarget.register_plugin_field(SkipTyField),
    )
