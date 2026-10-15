"""The `oci_artifact` target and its fields. Reference and media type syntax is validated by `oras` itself."""

from typing import TYPE_CHECKING

from pants.core.goals.package import OutputPathField
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    BoolField,
    SpecialCasedDependencies,
    StringField,
    StringSequenceField,
    Target,
)
from pants.util.docutil import bin_name
from pants.util.strutil import help_text

from oras_pants_plugin.constants import ALL_DEFAULT_REGISTRIES

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedTargetTypes


class OCIArtifactPackagesField(SpecialCasedDependencies):
    """The `package`-able targets whose outputs become the layers of the OCI artifact."""

    alias = "packages"
    help = help_text(
        f"""
        Addresses to any targets that can be built with `{bin_name()} package`, e.g. `["src/app:app"]`.

        Pants builds them as if you had run `{bin_name()} package` and adds every file or directory they
        produce to the OCI artifact as one layer each, titled with the path it would have under `--distdir`
        (e.g. `src.app/app.pex`). A directory, such as a `packed` layout PEX, becomes a gzipped tar layer that
        `oras pull` unpacks again.

        Anything `{bin_name()} package` can build works: a `pex_binary`, a `python_aws_lambda_function`, an
        `archive`, and so on.
        """
    )


class OCIArtifactTypeField(StringField):
    """The OCI `artifactType` of the manifest `oras` creates."""

    alias = "oci_artifact_type"
    help = help_text(
        """
        The media type identifying the kind of artifact, stored as the manifest's `artifactType` and passed to
        `oras push` as `--artifact-type`, e.g. `application/vnd.python.pex.v1`. Leave unset for `oras`' default,
        `application/vnd.unknown.artifact.v1`. See also: https://oras.land/docs/concepts/artifact
        """
    )


class OCITagsField(StringSequenceField):
    """The tags `oras` applies to the artifact, in the packaged layout and in every registry."""

    alias = "oci_tags"
    default = ("latest",)
    help = help_text(
        """
        The tags of the OCI artifact, applied in the packaged OCI image layout and in every registry it is
        published to. An empty list leaves the artifact untagged, addressable by its digest only.
        """
    )


class OCIRegistriesField(StringSequenceField):
    """Where `pants publish` pushes the artifact: registry addresses or `[oras].registries` aliases."""

    alias = "oci_registries"
    default = (ALL_DEFAULT_REGISTRIES,)
    help = help_text(
        f"""
        Addresses or configured aliases of the OCI registries to publish this artifact to with
        `{bin_name()} publish`.

        An address is a host with optional port, e.g. `ghcr.io` or `localhost:5000`, and may carry a path prefix
        that is put in front of `oci_repository`, e.g. `ghcr.io/my-org`. An alias refers to an entry of the
        `[oras].registries` option and is prefixed with `@`.

        By default, every `[oras].registries` entry with `default = true` is used. A target that resolves to no
        registry is skipped by `{bin_name()} publish`.

        Example:

            # pants.toml
            [oras.registries.my-registry-alias]
            address = "myregistrydomain:port"
            default = false # optional

            # src/app/BUILD
            oci_artifact(
                oci_registries=[
                    "@my-registry-alias",
                    "myregistrydomain:port",
                ],
            )
        """
    )


class OCIRepositoryField(StringField):
    """The repository within each registry the artifact is published to."""

    alias = "oci_repository"
    help = help_text(
        f"""
        The repository of the published artifact within each `oci_registries` entry, e.g. `my-org/my-app`,
        giving the reference `<registry address>/<oci_repository>:<tag>`. Leave unset to skip the target in
        `{bin_name()} publish`.
        """
    )


class SkipOCIPublishField(BoolField):
    """A per-target opt-out of `pants publish`."""

    alias = "skip_oras"
    default = False
    help = f"If true, don't publish this artifact with `oras` during `{bin_name()} publish`."


class OCIArtifact(Target):
    """An OCI artifact wrapping the outputs of other `package`-able targets, buildable and publishable with `oras`."""

    alias = "oci_artifact"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        OCIArtifactPackagesField,
        OutputPathField,
        OCIArtifactTypeField,
        OCITagsField,
        OCIRegistriesField,
        OCIRepositoryField,
        SkipOCIPublishField,
    )
    help = help_text(
        f"""
        An OCI artifact wrapping the outputs of other `{bin_name()} package`-able targets, such as `pex_binary`
        targets.

        `{bin_name()} package` builds the artifact into an OCI image layout directory at `output_path` with
        `oras push`, one layer per packaged file or directory. `{bin_name()} publish` copies that layout to each
        `oci_registries` entry with `oras cp`, so the published artifact has the same digest as the packaged one.

        For container images, prefer the `docker_image` target: Pants publishes those natively.
        """
    )


def target_types() -> CollectedTargetTypes:
    return (OCIArtifact,)
