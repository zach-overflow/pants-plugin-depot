from typing import TYPE_CHECKING

from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.config_files import ConfigFilesRequest
from pants.core.util_rules.external_tool import TemplatedExternalTool
from pants.engine.platform import Platform
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import ArgsListOption, BoolOption, FileOption, SkipOption, StrListOption
from pants.util.strutil import softwrap

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class Ty(TemplatedExternalTool):
    """The pantsbuild plugin configuration for the `ty` Python type checker."""

    options_scope = "ty"
    name = "ty"
    help = "The `ty` type checker for Python (https://docs.astral.sh/ty/)."

    default_version = "0.0.86"
    # Compute with: `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`
    # Pants declares these class attributes without `ClassVar`, so `ty` rejects a `ClassVar` annotation here.
    default_known_versions = [  # ruff: ignore[RUF012]
        "0.0.86|linux_arm64 |ff3f848d01d6849131ed712fc946c026b33a95720408eaece26d28d3c2e52c45|13019630",
        "0.0.86|linux_x86_64|cedbbe26a4f12533cfa728e07c8f053c86c7642548c72e92971e1154a94f3583|14149832",
        "0.0.86|macos_arm64 |ba782554d855aa69ce6ec8fa5898f5256a8603eb81f35d1927434576a434ae4e|12770181",
        "0.0.86|macos_x86_64|6b7908dec8629f9c18fe8c76fdcc22497ff823b14c351636aebe4d552d0e1fe9|13581573",
    ]
    version_constraints = ">=0.0.80,<1"
    default_url_template = "https://github.com/astral-sh/ty/releases/download/{version}/ty-{platform}.tar.gz"
    # The musl builds are statically linked, so they run on any glibc or musl based distribution.
    default_url_platform_mapping: dict[str, str] = {  # ruff: ignore[RUF012]
        "linux_arm64": "aarch64-unknown-linux-musl",
        "linux_x86_64": "x86_64-unknown-linux-musl",
        "macos_arm64": "aarch64-apple-darwin",
        "macos_x86_64": "x86_64-apple-darwin",
    }

    skip = SkipOption("check")
    args = ArgsListOption(example="--output-format concise --error-on-warning")
    config = FileOption(
        default=None,
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            Path to a `ty.toml` config file (https://docs.astral.sh/ty/configuration/).

            Setting this option will disable `[{cls.options_scope}].config_discovery`. Use this option if the
            config is located in a non-standard location.
            """
        ),
    )
    config_discovery = BoolOption(
        default=True,
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            If true, Pants will include a `ty.toml` file, or a `pyproject.toml` file containing a `[tool.ty]`
            table, found in the build root during a run. `ty` reads its configuration from the directory it
            runs in and its ancestors, and Pants always runs it from the build root.

            Use `[{cls.options_scope}].config` instead if your config is in a non-standard location.
            """
        ),
    )
    _interpreter_constraints = StrListOption(
        advanced=True,
        default=["CPython>=3.10,<3.16"],
        help=softwrap(
            """
            Python interpreter constraints used to build the virtual environment `ty` resolves third-party
            imports from, when the checked code declares no interpreter constraints of its own.
            """
        ),
    )

    @property
    def interpreter_constraints(self) -> InterpreterConstraints:
        """Fallback constraints for the third-party environment `ty` inspects. `ty` itself is a static binary."""
        return InterpreterConstraints(self._interpreter_constraints)

    def config_request(self) -> ConfigFilesRequest:
        """
        Finds the `ty` config file in the build root.

        `ty` discovers its config by walking up from the current directory, and Pants runs it from the build
        root of the sandbox, so only a config in the build root takes effect. `ty.toml` takes precedence over
        `pyproject.toml` when both exist. See https://docs.astral.sh/ty/configuration/#configuration-files.

        `check_content` is a substring test, and `[tool.ty.rules]` alone is valid `ty` config, so the needle
        MUST be the open `[tool.ty` prefix. It also matches e.g. `[tool.typos]`, which only ships a
        `pyproject.toml` that `ty` then ignores.
        """
        return ConfigFilesRequest(
            specified=self.config,
            specified_option_name=f"[{self.options_scope}].config",
            discovery=self.config_discovery,
            check_existence=["ty.toml"],
            check_content={"pyproject.toml": b"[tool.ty"},
        )

    def generate_exe(self, plat: Platform) -> str:
        """The release tarball extracts to `ty-<target-triple>/ty`."""
        return f"./ty-{self.url_platform_mapping[plat.value]}/ty"


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, Ty))
