from pants.backend.python.target_types import (
    PythonSourcesGeneratorTarget,
    PythonSourceTarget,
    PythonTestsGeneratorTarget,
    PythonTestTarget,
)
from pants.engine.target import BoolField

from pants_plugin_developer_utils import CollectedRules


class SkipTachLintField(BoolField):
    """Additional field registered on targets which `tach` may consider during a `pants lint` run."""

    alias = "skip_tach_lint"
    default = False
    help = "When `True`, the target will be omitted from `tach`'s consideration during `pants lint` runs."


def rules() -> CollectedRules:
    return (
        PythonSourceTarget.register_plugin_field(SkipTachLintField),
        PythonSourcesGeneratorTarget.register_plugin_field(SkipTachLintField),
        PythonTestTarget.register_plugin_field(SkipTachLintField),
        PythonTestsGeneratorTarget.register_plugin_field(SkipTachLintField),
    )
