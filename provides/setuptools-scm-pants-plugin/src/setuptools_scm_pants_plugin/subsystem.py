from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from pants.backend.python.subsystems.python_tool_base import PythonToolBase
from pants.backend.python.target_types import EntryPoint
from pants.core.goals.resolves import ExportableTool
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class SetuptoolsScm(PythonToolBase):
    """The `setuptools-scm` tool that `scm_version` targets run to derive a version from git tags."""

    # Not `setuptools-scm`: that scope belongs to Pants' own subsystem in `pants.backend.experimental.python`.
    options_scope = "setuptools-scm-tool"
    name = "setuptools-scm"
    help_short = "Derives versions from git tags with setuptools-scm (https://setuptools-scm.readthedocs.io/)."

    default_main = EntryPoint("setuptools_scm")
    # `>=10` for `[tool.setuptools_scm] tag.prefix`, which `scm_version(tag_prefix=...)` relies on.
    # MUST match the `setuptools-scm-tool` requirement in `provides/setuptools-scm-pants-plugin/BUILD`.
    default_requirements = ("setuptools-scm>=10.3.4,<11",)
    # Only constrains the interpreter that runs `setuptools-scm`, not the versioned code.
    register_interpreter_constraints = True
    # A list, not a tuple: Pants uses it as the default of the list-typed `interpreter_constraints` option.
    default_interpreter_constraints: ClassVar[Sequence[str]] = ["CPython>=3.14,<3.15"]
    default_lockfile_resource = ("setuptools_scm_pants_plugin.lockfile_resource", "setuptools_scm_lockfile.json")


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, SetuptoolsScm))
