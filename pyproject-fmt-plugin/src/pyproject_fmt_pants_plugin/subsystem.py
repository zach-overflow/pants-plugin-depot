from collections.abc import Iterable
import os

from pants.backend.python.subsystems.python_tool_base import PythonToolBase
from pants.backend.python.target_types import ConsoleScript
from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.config_files import ConfigFilesRequest
from pants.engine.rules import Rule, collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import BoolOption, FileOption, SkipOption, StrListOption
from pants.util.strutil import softwrap


class PyprojectFmt(PythonToolBase):
    """An auto-formatter / linter for `pyproject.toml` files."""
    options_scope = "pyproject-fmt"
    name = "PyprojectFmt"
    help_short = "Linter / formatter for `pyproject.toml` files (https://pyproject-fmt.readthedocs.io/en/latest/)."
    default_version = "2.29.4"

    skip = SkipOption("lint")
    fmt = SkipOption("fmt")

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
            When True, uses `pyproject-fmt.toml` or `pyproject.toml` file in the build root during a run. 
            If both a `pyproject-fmt.toml` and a `pyproject.toml` file exist at the same directory, 
            `pyproject-fmt.toml` takes precedence. The discovered config will control the shared settings
            for all `pyproject.toml` files in the repo, with per-pyproject.toml files having the ability to
            adjust their individual file-scoped pyproject-fmt settings as needed.

            Setting this option will disable `[{cls.options_scope}].config`.

            See also: https://pyproject-fmt.readthedocs.io/en/latest/configuration.html
            """
        ),
    )
    interpreter_constraints = StrListOption(
        default=["CPython>=3.14,<3.15"],
        advanced=True,
        help=softwrap(
            f"""
            The python interpreter constraints to use for running the `pyproject-fmt` tool. Only pertains to the
            parsing of the `pypyroject.toml`, and does not need to match the Python interpreter constraints of the
            project corresponding to a given `pyproject.toml` file.
            """
        )
    )
    requirements = ["pyproject-fmt>=2.29.4,<3"]
    default_main = ConsoleScript("pyproject-fmt")
    # TODO: package this in the wheel and adjust path
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


def rules() -> Iterable[Rule | UnionRule]:
    return (*collect_rules(), UnionRule(ExportableTool, PyprojectFmt))
