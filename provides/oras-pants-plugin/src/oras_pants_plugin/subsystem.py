"""The `oras` subsystem: where the binary comes from and how `pants package` and `pants publish` run it."""

from typing import TYPE_CHECKING, Any, ClassVar

from pants.core.goals.resolves import ExportableTool
from pants.core.util_rules.external_tool import TemplatedExternalTool
from pants.engine.env_vars import EnvironmentVarsRequest
from pants.engine.platform import Platform
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import ArgsListOption, DictOption, FileOption, SkipOption, StrListOption
from pants.util.memo import memoized_method
from pants.util.strutil import softwrap

from oras_pants_plugin.registries import OCIRegistries

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class Oras(TemplatedExternalTool):
    """
    The configuration and tooling wrapper for the `oras` binary, which builds `oci_artifact` targets into OCI image
    layouts and copies them to OCI registries. See also: https://oras.land/docs/
    """

    options_scope = "oras"
    name = "oras"
    help = "The `oras` CLI for building and publishing OCI artifacts (https://oras.land/)."

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
        example="--to-plain-http --to-insecure",
        extra_help=softwrap(
            """
            Added to every `oras cp` run by `pants publish`, after the plugin's own flags
            (https://oras.land/docs/commands/oras_cp). The registry is the copy's destination, so its flags are
            the `--to-*` ones. A repeated flag overrides the plugin's value.
            """
        ),
    )
    config = FileOption(
        default=None,
        help=softwrap(
            """
            Path to a registry authentication file for `oras`, in the format of `~/.docker/config.json`, passed
            to `oras cp` as `--to-registry-config`. Relative paths are resolved from the build root. Leave unset
            to use the credentials stored by `docker login` or `oras login`.
            See also https://oras.land/docs/how_to_guides/authentication
            """
        ),
    )
    _registries = DictOption[Any](
        help=softwrap(
            """
            Configure OCI registries by alias. The schema for a registry entry is as follows:

                {
                    "registry-alias": {
                        "address": "registry-domain:port",
                        "default": bool,
                    },
                    ...
                }

            An `oci_artifact` target without `oci_registries` is published to every entry with `default = true`;
            an entry aliased `default` is a default too. `oci_registries` may instead list registry addresses and
            aliases prefixed with `@`.
            """
        )
    )
    extra_env_vars = StrListOption(
        default=[],
        advanced=True,
        help=softwrap(
            """
            Additional environment variables to make available to `oras` processes that reach a registry.
            Entries are either strings in the form `ENV_VAR=value` to use explicitly, or just `ENV_VAR` to copy
            the value from Pants's own environment. `PATH`, `HOME` and `DOCKER_CONFIG` are always passed through,
            so the credentials stored by `docker login` or `oras login` and their credential helpers are found.
            Use this for proxy or TLS settings such as `HTTPS_PROXY` or `SSL_CERT_FILE`.
            """
        ),
    )
    # `oras` reads the credentials from `$DOCKER_CONFIG/config.json` and runs the credential helpers from `PATH`.
    _REGISTRY_ENV_VAR_NAMES: ClassVar[tuple[str, ...]] = ("PATH", "HOME", "DOCKER_CONFIG")

    def generate_exe(self, plat: Platform) -> str:
        """The release tarball extracts the binary to its root, next to the license."""
        return "./oras"

    def create_env_vars_request(self) -> EnvironmentVarsRequest:
        """The environment of an `oras` process that reaches a registry: the credential variables plus `extra_env_vars`."""
        return EnvironmentVarsRequest([*self._REGISTRY_ENV_VAR_NAMES, *self.extra_env_vars])

    @memoized_method
    def registries(self) -> OCIRegistries:
        return OCIRegistries.from_dict(self._registries)


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, Oras))
