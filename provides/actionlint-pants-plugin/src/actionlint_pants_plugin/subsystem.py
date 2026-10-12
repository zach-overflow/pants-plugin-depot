"""The `actionlint` subsystem: where the binary comes from and how `pants lint` runs it."""

from typing import TYPE_CHECKING, Final

from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.config_files import ConfigFilesRequest
from pants.core.util_rules.external_tool import TemplatedExternalTool
from pants.engine.platform import Platform
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import ArgsListOption, BoolOption, FileOption, SkipOption
from pants.util.strutil import softwrap

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules

CONFIG_FILE_PATHS: Final[tuple[str, ...]] = (".github/actionlint.yaml", ".github/actionlint.yml")
"""Where `actionlint` looks for its config, relative to the repository root, in the order it tries them."""


class Actionlint(TemplatedExternalTool):
    """The pantsbuild plugin configuration for the `actionlint` GitHub Actions workflow linter."""

    options_scope = "actionlint"
    name = "actionlint"
    help = "The `actionlint` static checker for GitHub Actions workflow files (https://github.com/rhysd/actionlint)."

    default_version = "1.7.12"
    # Compute with: `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`
    # Pants declares these class attributes without `ClassVar`, so `ty` rejects a `ClassVar` annotation here.
    default_known_versions = [  # noqa: RUF012
        "1.7.12|linux_arm64 |325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6|2111482",
        "1.7.12|linux_x86_64|8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8|2353908",
        "1.7.12|macos_arm64 |aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f|2164202",
        "1.7.12|macos_x86_64|5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644|2355828",
    ]
    version_constraints = ">=1.7,<2"
    default_url_template = (
        "https://github.com/rhysd/actionlint/releases/download/v{version}/actionlint_{version}_{platform}.tar.gz"
    )
    # Go binaries are statically linked, so one Linux build runs on any distribution.
    default_url_platform_mapping: dict[str, str] = {  # noqa: RUF012
        "linux_arm64": "linux_arm64",
        "linux_x86_64": "linux_amd64",
        "macos_arm64": "darwin_arm64",
        "macos_x86_64": "darwin_amd64",
    }

    skip = SkipOption("lint")
    args = ArgsListOption(example="-ignore 'SC2086:.+' -oneline")
    config = FileOption(
        default=None,
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            Path to a config file understood by `actionlint`, passed as `-config-file`
            (https://github.com/rhysd/actionlint/blob/main/docs/config.md).

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
            If true, Pants will include a `.github/actionlint.yaml` or `.github/actionlint.yml` file found in
            the build root during a run, which `actionlint` then reads on its own.

            Use `[{cls.options_scope}].config` instead if your config is in a non-standard location.
            """
        ),
    )
    shellcheck = BoolOption(
        default=True,
        help=softwrap(
            """
            If true, `actionlint` runs `shellcheck` on the `run:` steps of every workflow, as it does when
            `shellcheck` is on the `PATH`. Pants downloads the `shellcheck` release configured by
            `[shellcheck].version` and `[shellcheck].known_versions`; the other `[shellcheck]` options,
            including `skip` and `args`, do not apply to this integration.

            The `pyflakes` integration is always disabled, as Pants ships no `pyflakes` tool.
            """
        ),
    )

    def config_request(self) -> ConfigFilesRequest:
        """
        Finds the `actionlint` config file.

        `actionlint` reads `.github/actionlint.yaml` or `.github/actionlint.yml` from the repository root,
        which is the build root in the sandbox. See https://github.com/rhysd/actionlint/blob/main/docs/config.md
        """
        return ConfigFilesRequest(
            specified=self.config,
            specified_option_name=f"[{self.options_scope}].config",
            discovery=self.config_discovery,
            check_existence=CONFIG_FILE_PATHS,
        )

    def generate_exe(self, plat: Platform) -> str:
        """The release tarball extracts the binary to its root, next to the docs and the man page."""
        return "./actionlint"


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, Actionlint))
