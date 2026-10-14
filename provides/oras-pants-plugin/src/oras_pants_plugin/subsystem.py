"""The `oras` subsystem: where the binary comes from and how `pants publish` runs it."""

from typing import TYPE_CHECKING, Final

from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.external_tool import TemplatedExternalTool
from pants.engine.platform import Platform
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import ArgsListOption, SkipOption, StrListOption
from pants.util.strutil import softwrap

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules

ORAS_BASE_ENV_VAR_NAMES: Final[tuple[str, ...]] = ("PATH", "HOME", "DOCKER_CONFIG")
"""
Always passed to `oras` processes. `oras` reads the credentials `docker login` and `oras login` store in
`$DOCKER_CONFIG/config.json` or `~/.docker/config.json`, and runs the credential helpers named there from `PATH`.
"""


class Oras(TemplatedExternalTool):
    """
    The configuration and tooling wrapper for the `oras` binary to publish arbitrary artifacts as OCI artifacts in
    OCI-compliant registries. See also: https://oras.land/docs/
    """

    options_scope = "oras"
    name = "oras"
    help = "The `oras` CLI for pushing files to OCI registries as OCI artifacts (https://oras.land/)."

    default_version = "1.3.4"
    # Compute with: `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`
    # Pants declares these class attributes without `ClassVar`, so `ty` rejects a `ClassVar` annotation here.
    default_known_versions = [  # noqa: RUF012
        "1.3.4|linux_arm64 |15702c6e3a4a56a8bd8ac5c17efdbcab56d9bada661ccbcf017f5b10c1d89399|4238235",
        "1.3.4|linux_x86_64|f27adb935022d94df8dc77719c322dda592c78a0d57a6f7dcdd8d900b248c454|4679642",
        "1.3.4|macos_arm64 |217761a9500242ff473de8656b5aca21136ff39e17e9e61fd8936bbfd902704c|4401355",
        "1.3.4|macos_x86_64|5e964f3d5a36eb9499a9d3e252a86b09e7adf3e6f6447eec56fd249c6702af7e|4750901",
    ]
    version_constraints = ">=1.3,<2"
    default_url_template = (
        "https://github.com/oras-project/oras/releases/download/v{version}/oras_{version}_{platform}.tar.gz"
    )
    # Go binaries are statically linked, so one Linux build runs on any distribution.
    default_url_platform_mapping: dict[str, str] = {  # noqa: RUF012
        "linux_arm64": "linux_arm64",
        "linux_x86_64": "linux_amd64",
        "macos_arm64": "darwin_arm64",
        "macos_x86_64": "darwin_amd64",
    }

    skip = SkipOption("publish")
    args = ArgsListOption(
        example="--registry-config /path/to/auth.json --plain-http",
        extra_help=softwrap(
            """
            Added to every `oras push` run by `pants publish`, after the plugin's own flags
            (https://oras.land/docs/commands/oras_push). A repeated flag overrides the plugin's value.
            """
        ),
    )
    extra_env_vars = StrListOption(
        default=[],
        advanced=True,
        help=softwrap(
            """
            Additional environment variables to make available to `oras` processes. Entries are either strings
            in the form `ENV_VAR=value` to use explicitly, or just `ENV_VAR` to copy the value from Pants's own
            environment. `PATH`, `HOME` and `DOCKER_CONFIG` are always passed through, so the credentials stored
            by `docker login` or `oras login` and their credential helpers are found. Use this for proxy or TLS
            settings such as `HTTPS_PROXY` or `SSL_CERT_FILE`.
            """
        ),
    )

    def generate_exe(self, plat: Platform) -> str:
        """The release tarball extracts the binary to its root, next to the license."""
        return "./oras"


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, Oras))
