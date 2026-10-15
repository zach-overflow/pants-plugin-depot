"""
Implements the `package` goal for `oci_artifact` targets: the packaged outputs of the `packages` targets are pushed
into an OCI image layout directory with `oras push --oci-layout`.
See also:
    https://www.pantsbuild.org/stable/docs/writing-plugins/common-plugin-tasks/add-a-package-type
    https://github.com/opencontainers/image-spec/blob/main/image-layout.md
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pants.core.goals.package import (
    BuiltPackage,
    BuiltPackageArtifact,
    EnvironmentAwarePackageRequest,
    OutputPathField,
    PackageFieldSet,
    environment_aware_package,
)
from pants.engine.fs import AddPrefix, DigestSubset, MergeDigests, PathGlobs, RemovePrefix
from pants.engine.internals.graph import find_valid_field_sets, resolve_targets
from pants.engine.intrinsics import add_prefix, digest_subset_to_digest, merge_digests, remove_prefix
from pants.engine.process import execute_process_or_raise
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.target import FieldSetsPerTargetRequest, InvalidTargetException
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel
from pants.util.strutil import pluralize

from oras_pants_plugin.constants import SandboxDir
from oras_pants_plugin.goals.common import (
    OCIArtifactFieldSet,
    OCILayoutRequest,
    OrasProcessRequest,
    oci_reference,
    oras_file_arg,
    read_oci_layout_manifest,
)
from oras_pants_plugin.target_types import OCIArtifactTypeField

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


@dataclass(frozen=True)
class OCIArtifactPackageFieldSet(PackageFieldSet, OCIArtifactFieldSet):
    """The `PackageFieldSet` for `oci_artifact` targets."""

    output_path: OutputPathField
    oci_artifact_type: OCIArtifactTypeField


def construct_oras_push_argv(
    layout_path: str, tags: Iterable[str], artifact_type: str | None, files: Iterable[str]
) -> tuple[str, ...]:
    """The `oras push` arguments (after the binary) that build the layout at `layout_path` from `files`."""
    argv: list[str] = ["push", "--no-tty", "--oci-layout"]
    if artifact_type:
        argv.extend(["--artifact-type", artifact_type])
    argv.append(oci_reference(layout_path, tags))
    argv.extend(oras_file_arg(file) for file in files)
    return tuple(argv)


@rule(desc="Package an `oci_artifact` target into an OCI image layout with `oras`", level=LogLevel.DEBUG)
async def package_oci_artifact(field_set: OCIArtifactPackageFieldSet) -> BuiltPackage:
    """Builds every `packages` target, then pushes their outputs into a layout at the target's `output_path`."""
    targets = await resolve_targets(**implicitly(field_set.packages.to_unparsed_address_inputs()))
    field_sets_per_target = await find_valid_field_sets(
        FieldSetsPerTargetRequest(PackageFieldSet, targets), **implicitly()
    )
    packages = await concurrently(
        environment_aware_package(EnvironmentAwarePackageRequest(package_field_set))
        for package_field_set in field_sets_per_target.field_sets
    )
    files = tuple(artifact.relpath for package in packages for artifact in package.artifacts if artifact.relpath)
    if not files:
        raise InvalidTargetException(
            f"The `{field_set.packages.alias}` field of target {field_set.address} produced no files to package "
            "into an OCI artifact; list targets that `package` builds, such as a `pex_binary`."
        )

    input_digest = await merge_digests(MergeDigests(package.digest for package in packages))
    tags = field_set.oci_tags.value or ()
    layout_path = field_set.output_path.value_or_default(file_ending=None)
    result = await execute_process_or_raise(
        **implicitly(
            OrasProcessRequest(
                argv=construct_oras_push_argv(
                    SandboxDir.OCI_LAYOUT_OUT_DIRNAME, tags, field_set.oci_artifact_type.value, files
                ),
                description=f"Build OCI artifact {field_set.address} from {pluralize(len(files), 'file')} with `oras`",
                input_digest=input_digest,
                output_directories=(SandboxDir.OCI_LAYOUT_OUT_DIRNAME,),
            )
        )
    )
    # `oras` leaves its empty `ingest/` scratch directory behind in the layout.
    layout_files = await digest_subset_to_digest(
        DigestSubset(
            result.output_digest,
            PathGlobs(
                [
                    f"{SandboxDir.OCI_LAYOUT_OUT_DIRNAME}/**",
                    f"!{SandboxDir.OCI_LAYOUT_OUT_DIRNAME}/ingest",
                    f"!{SandboxDir.OCI_LAYOUT_OUT_DIRNAME}/ingest/**",
                ]
            ),
        )
    )
    layout_digest = await add_prefix(
        AddPrefix(await remove_prefix(RemovePrefix(layout_files, SandboxDir.OCI_LAYOUT_OUT_DIRNAME)), layout_path)
    )
    manifest = await read_oci_layout_manifest(OCILayoutRequest(layout_digest, layout_path))
    return BuiltPackage(
        layout_digest,
        (
            BuiltPackageArtifact(
                layout_path,
                extra_log_lines=(
                    f"  OCI artifact {oci_reference(layout_path, tags)} ({manifest.digest})",
                    *(f"  layer: {file}" for file in files),
                ),
            ),
        ),
    )


def rules() -> CollectedRules:
    """Returns the `package`-goal-specific rules for the `oras` pants plugin."""
    return (*collect_rules(), UnionRule(PackageFieldSet, OCIArtifactPackageFieldSet))
