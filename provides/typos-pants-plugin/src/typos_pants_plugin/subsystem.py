import os.path
from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

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

CONFIG_FILE_NAMES: Final[tuple[str, ...]] = ("typos.toml", "_typos.toml", ".typos.toml")
"""The dedicated `typos` config file names, in the order `typos` tries them."""


class Typos(TemplatedExternalTool):
    """The pantsbuild plugin configuration for the `typos` source code spell checker."""

    options_scope = "typos"
    name = "typos"
    help = "The `typos` source code spell checker and corrector (https://github.com/crate-ci/typos)."

    default_version = "1.51.1"
    # Compute with: `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`
    # Pants declares these class attributes without `ClassVar`, so `ty` rejects a `ClassVar` annotation here.
    default_known_versions = [  # noqa: RUF012
        "1.51.1|linux_arm64 |2ac5e37b3236b3c07dec5cdf1527acf143aec4674a6089b0bf424d021b35e099|7190748",
        "1.51.1|linux_x86_64|93c301fd4120ff076e2cc2a6d6a61cab4a4bdb81899287c0938b452e56d1f454|8248699",
        "1.51.1|macos_arm64 |316d50a32c3726a80ab39c6d12141b70080498973c5e8a9b068b12cde78b10c1|3347206",
        "1.51.1|macos_x86_64|f3451079971633a7f769fb958fe06b0d64b5f1dc46df0854aa1ddb9a6f4031d6|3458232",
    ]
    # Every run passes `--force-exclude`, which `typos` added in 1.16.18.
    version_constraints = ">=1.16.18,<2"
    default_url_template = (
        "https://github.com/crate-ci/typos/releases/download/v{version}/typos-v{version}-{platform}.tar.gz"
    )
    # The musl builds are statically linked, so they run on any glibc or musl based distribution.
    default_url_platform_mapping: dict[str, str] = {  # noqa: RUF012
        "linux_arm64": "aarch64-unknown-linux-musl",
        "linux_x86_64": "x86_64-unknown-linux-musl",
        "macos_arm64": "aarch64-apple-darwin",
        "macos_x86_64": "x86_64-apple-darwin",
    }

    skip = SkipOption("fix", "lint")
    args = ArgsListOption(example="--locale en-us --format brief")
    config = FileOption(
        default=None,
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            Path to a config file understood by `typos`, passed as `--config`
            (https://github.com/crate-ci/typos/blob/master/docs/reference.md).

            Setting this option will disable `[{cls.options_scope}].config_discovery`: `typos` then runs with
            `--isolated`, so this file is the only config it reads. Use this option if the config is located in
            a non-standard location.
            """
        ),
    )
    config_discovery = BoolOption(
        default=True,
        advanced=True,
        help=lambda cls: softwrap(
            f"""
            If true, Pants will include every config file `typos` discovers on its own: a `typos.toml`,
            `_typos.toml` or `.typos.toml` file, a `pyproject.toml` file with a `[tool.typos]` table, or a
            `Cargo.toml` file with a `[workspace.metadata.typos]` or `[package.metadata.typos]` table, in the
            directory of a checked file or in any of its ancestors up to the build root.

            If false, `typos` runs with `--isolated` and reads no config file, not even a `pyproject.toml`
            file that is itself being checked.

            Use `[{cls.options_scope}].config` instead if your config is in a non-standard location.
            """
        ),
    )
    glob_pattern = StrListOption(
        default=["**/*"],
        advanced=True,
        help=softwrap(
            """
            A list of glob patterns of files to include/exclude in spell checking, relative to the build root.
            Leading exclamation points exclude an item from spell checking.

            Example:

                ["**/*", "!**/*.lock", "!3rdparty/**"]

            The default includes every file the goal was given. `typos` additionally skips the files its own
            `files.extend-exclude` config globs match, as if `--force-exclude` were passed.
            """
        ),
    )

    def config_request(self, dirs: Iterable[str]) -> ConfigFilesRequest:
        """
        Finds the config files `typos` would discover for files in `dirs`.

        `typos` walks up from each checked file's directory and reads the first config it finds, so the
        candidates are every config file name in each of `dirs`, their ancestors and the build root. A
        `pyproject.toml` or `Cargo.toml` only counts when it holds a `typos` table.
        See https://github.com/crate-ci/typos/blob/master/docs/reference.md#sources
        """
        all_dirs = ("", *dirs)
        return ConfigFilesRequest(
            specified=self.config,
            specified_option_name=f"[{self.options_scope}].config",
            discovery=self.config_discovery,
            check_existence=[os.path.join(d, name) for d in all_dirs for name in CONFIG_FILE_NAMES],
            check_content={
                **{os.path.join(d, "pyproject.toml"): b"[tool.typos" for d in all_dirs},
                **{os.path.join(d, "Cargo.toml"): b"metadata.typos" for d in all_dirs},
            },
        )

    def generate_exe(self, plat: Platform) -> str:
        """The release tarball extracts the binary to its root, next to the docs and licenses."""
        return "./typos"


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, Typos))
