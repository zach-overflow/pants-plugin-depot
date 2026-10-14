"""The fields the plugin adds to `pex_binary` and `pex_binaries` targets."""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from pants.backend.python.target_types import PexBinariesGeneratorTarget, PexBinary
from pants.engine.addresses import Address
from pants.engine.target import BoolField, Field, InvalidFieldException, StringField, StringSequenceField
from pants.util.strutil import softwrap

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


def is_untagged_reference(reference: str) -> bool:
    """
    Whether `reference` is a `<registry>/<repository>` OCI reference without a `:<tag>` or `@<digest>` suffix.

    A registry host may carry a port (`localhost:5000/app`), so only the last path segment is inspected.
    """
    registry, separator, repository = reference.rpartition("/")
    return bool(registry and separator and repository) and ":" not in repository and "@" not in repository


class OrasRepositoriesField(StringSequenceField):
    """Where `oras` pushes the target's package output, as untagged OCI references."""

    alias = "oci_repositories"
    help = softwrap(
        """
        The OCI repositories to push this target's package output to as an OCI artifact, given as
        `<registry>/<repository>` references such as `ghcr.io/my-org/my-app` or `localhost:5000/my-app`.
        `pants publish` runs one `oras push` per entry, tagging the artifact with every `oci_tags` entry, so a
        reference MUST NOT carry a `:<tag>` or `@<digest>` suffix. Leave unset to skip the target.
        """
    )

    @classmethod
    def compute_value(cls, raw_value: Iterable[str] | None, address: Address) -> tuple[str, ...] | None:
        value = super().compute_value(raw_value, address)
        invalid = [reference for reference in value or () if not is_untagged_reference(reference)]
        if invalid:
            raise InvalidFieldException(
                softwrap(
                    f"""
                    The `{cls.alias}` field in target {address} must contain `<registry>/<repository>` references
                    without a tag or digest; the tags come from the `{OrasTagsField.alias}` field.
                    Invalid entries: {invalid}.
                    """
                )
            )
        return value


class OrasTagsField(StringSequenceField):
    """The tags `oras` applies to the pushed artifact in every repository."""

    alias = "oci_tags"
    default = ("latest",)
    help = softwrap(
        """
        The tags to apply to the pushed OCI artifact in every `oci_repositories` entry. An empty list pushes the
        artifact untagged, addressable by its digest only.
        """
    )


class OciMediaType(StringField):
    """What OCI `artifactType` to designate the `oras`-published artifact."""

    alias = "oci_media_type"
    help = softwrap(
        """
        The media type identifying the kind of OCI artifact that wraps the package output of this target, passed
        to `oras push` as `--artifact-type` and stored as the manifest's `artifactType`.
        See also: https://oras.land/docs/concepts/artifact
        """
    )


class PexOciMediaType(OciMediaType):
    """The default OCI artifact type for a PEX published via `oras` to an OCI registry."""

    default = "application/vnd.python.pex.v1"


class SkipOrasPublishField(BoolField):
    """A custom field to opt-out of `oras` publication to the configured OCI registry(s)."""

    alias = "skip_oras"
    default = False
    help = "If true, don't publish this target's package output with `oras` during `pants publish`."


PEX_BINARY_PLUGIN_FIELDS: tuple[type[Field], ...] = (
    OrasRepositoriesField,
    OrasTagsField,
    PexOciMediaType,
    SkipOrasPublishField,
)
"""The fields registered on `pex_binary`, and moved from `pex_binaries` onto the targets it generates."""


def rules() -> CollectedRules:
    """Registers the plugin's fields on `pex_binary` and `pex_binaries`."""
    return (
        *(PexBinary.register_plugin_field(field) for field in PEX_BINARY_PLUGIN_FIELDS),
        # `pex_binaries` moves its per-binary fields onto the generated `pex_binary` targets; so must these.
        *(
            PexBinariesGeneratorTarget.register_plugin_field(field, as_moved_field=True)
            for field in PEX_BINARY_PLUGIN_FIELDS
        ),
    )
