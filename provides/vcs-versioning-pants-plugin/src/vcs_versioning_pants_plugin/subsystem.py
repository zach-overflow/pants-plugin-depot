from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from pants.backend.python.subsystems.python_tool_base import PythonToolBase
from pants.backend.python.target_types import EntryPoint
from pants.core.goals.resolves import ExportableTool
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class VcsVersioning(PythonToolBase):
    """
    The `vcs-versioning` tool that `scm_version` targets run to derive a version from git tags.

    `vcs-versioning` is the core library of setuptools-scm: the version extraction, tag parsing and version
    schemes, without the setuptools build hooks. setuptools-scm's CLI is this same program.
    """

    options_scope = "vcs-versioning"
    name = "vcs-versioning"
    help_short = "Derives versions from git tags with vcs-versioning, the core of setuptools-scm (https://setuptools-scm.readthedocs.io/)."

    default_main = EntryPoint("vcs_versioning")
    # `>=2.5` for `tag.prefix`, which `scm_version(tag_prefix=...)` relies on.
    # MUST match the `vcs-versioning-tool` requirement in `provides/vcs-versioning-pants-plugin/BUILD`.
    default_requirements = ("vcs-versioning>=2.5,<3",)
    # Only constrains the interpreter that runs `vcs-versioning`, not the versioned code.
    register_interpreter_constraints = True
    # A list, not a tuple: Pants uses it as the default of the list-typed `interpreter_constraints` option.
    default_interpreter_constraints: ClassVar[Sequence[str]] = ["CPython>=3.14,<3.15"]
    default_lockfile_resource: ClassVar[tuple[str, str]] = (
        "vcs_versioning_pants_plugin.lockfile_resource",
        "vcs_versioning_lockfile.json",
    )


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, VcsVersioning))
