from pants.backend.python.subsystems.python_tool_base import PythonToolBase
from pants.backend.python.target_types import ConsoleScript
from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.config_files import ConfigFilesRequest
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import FileOption, SkipOption
from pants.util.strutil import softwrap

from pants_plugin_developer_utils import CollectedRules


class Tach(PythonToolBase):
    """
    Subsystem for the `tach` pantsbuild plugin.

    See also: https://docs.gauge.sh/
    """

    options_scope = "tach"
    name = "Tach"
    help_short = "Python module dependency enforcement and analysis for modular architecture mono-repos."
    default_version = "0.35.2"

    skip = SkipOption("lint")

    config = FileOption(
        default="tach.toml",
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            Path to a config file understood by `tach`.
            (https://docs.gauge.sh/usage/configuration/)

            Setting this option will disable `[{cls.options_scope}].config_discovery`.
            Use this option if the config is located in a non-standard location.
            """
        ),
    )
    # Only constrains the interpreter that runs `tach`. It does not need to match the interpreter
    # constraints of a given project tach is analyzing.
    register_interpreter_constraints = True
    default_requirements = ("tach>=0.35.0,<1",)
    default_main = ConsoleScript("pyproject-fmt")
    default_lockfile_resource = ("tach_pants_plugin.tach_lockfile_resource", "tach_lockfile.json")

    def config_request(self) -> ConfigFilesRequest:
        """Returns a `ConfigFilesRequest` corresponding to the config file set via `[tach].config` in `pants.toml`."""
        return ConfigFilesRequest(specified=self.config, discovery=False)


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, Tach))
