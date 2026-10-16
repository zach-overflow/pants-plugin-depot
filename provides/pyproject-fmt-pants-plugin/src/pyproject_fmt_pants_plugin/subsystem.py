from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from pants.backend.python.subsystems.python_tool_base import PythonToolBase
from pants.backend.python.target_types import ConsoleScript
from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.config_files import ConfigFilesRequest
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import ArgsListOption, BoolOption, FileOption, SkipOption
from pants.util.strutil import softwrap

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class PyprojectFmt(PythonToolBase):
    """An auto-formatter / linter for `pyproject.toml` files."""

    options_scope = "pyproject-fmt"
    name = "PyprojectFmt"
    help_short = "Linter / formatter for `pyproject.toml` files (https://pyproject-fmt.readthedocs.io/en/latest/)."
    default_version = "2.29.4"

    skip = SkipOption("fmt", "lint")

    args = ArgsListOption(
        example="--column-width 120 --keep-full-version",
        extra_help=softwrap(
            """
            These arguments establish defaults: a shared `pyproject-fmt.toml` overrides them, and the
            `[tool.pyproject-fmt]` table of a given `pyproject.toml` file has final precedence. Use them in place
            of a `pyproject-fmt.toml` file to keep the repo-wide settings in `pants.toml`.

            See https://pyproject-fmt.readthedocs.io/en/latest/configuration.html#command-line-interface
            """
        ),
    )
    config = FileOption(
        default=None,
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            Path to a config file understood by pyproject-fmt
            (https://pyproject-fmt.readthedocs.io/en/latest/configuration.html).

            Setting this option will disable `[{cls.options_scope}].config_discovery`. Use
            this option if the config is located in a non-standard location.
            """
        ),
    )
    config_discovery = BoolOption(
        default=True,
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            When True, uses a `pyproject-fmt.toml` file in the build root as the shared config for all
            `pyproject.toml` files in the repo. Each `pyproject.toml` file may adjust its own file-scoped
            settings in a `[tool.pyproject-fmt]` table; `pyproject-fmt` reads those tables itself.

            Setting this option will disable `[{cls.options_scope}].config`.

            See also: https://pyproject-fmt.readthedocs.io/en/latest/configuration.html
            """
        ),
    )
    # Only constrains the interpreter that runs `pyproject-fmt`. It does not need to match the interpreter
    # constraints of the project a given `pyproject.toml` belongs to.
    register_interpreter_constraints = True
    # A list, not a tuple: Pants uses it as the default of the list-typed `interpreter_constraints` option.
    default_interpreter_constraints: ClassVar[Sequence[str]] = ["CPython>=3.14,<3.15"]
    default_requirements = ("pyproject-fmt>=2.29.4,<3",)
    default_main = ConsoleScript("pyproject-fmt")
    default_lockfile_resource = ("pyproject_fmt_pants_plugin.lockfile_resource", "pyproject_fmt_lockfile.json")

    def config_request(self) -> ConfigFilesRequest:
        """
        Finds the `pyproject.toml` file **which configures the shared `pyproject-fmt` settings**.

        NOTE: This method does NOT limit the `pyproject-fmt` run to just the discovered config here.
        Will run the underlying lint and fmt goal against all `pyproject.toml` files in the repo.
        """
        # Refer to https://docs.pytest.org/en/stable/customize.html#finding-the-rootdir for how
        # config files are discovered.
        if not self.config_discovery:
            return ConfigFilesRequest(specified=self.config, discovery=self.config_discovery)

        return ConfigFilesRequest(
            specified=self.config,
            specified_option_name=f"[{self.options_scope}].config",
            discovery=self.config_discovery,
            check_existence=["pyproject-fmt.toml"],
            check_content={"pyproject.toml": b"[tool.pyproject-fmt]"},
        )


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, PyprojectFmt))
