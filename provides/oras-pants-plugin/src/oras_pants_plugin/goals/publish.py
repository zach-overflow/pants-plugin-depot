"""
Implements the `publish` goal for `oci_artifact` targets: the OCI image layout `pants package` built is copied to each
registry with `oras cp --from-oci-layout`, so the published artifact keeps the packaged digest.
See also:
    https://www.pantsbuild.org/stable/docs/writing-plugins/common-plugin-tasks/add-a-publisher
    https://oras.land/docs/commands/oras_cp
"""

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pants.base.build_root import BuildRoot
from pants.core.goals.package import PackageFieldSet
from pants.core.goals.publish import (
    CheckSkipRequest,
    CheckSkipResult,
    PublishFieldSet,
    PublishOutputData,
    PublishPackages,
    PublishProcesses,
    PublishRequest,
)
from pants.engine.fs import Digest, MergeDigests
from pants.engine.intrinsics import merge_digests
from pants.engine.process import InteractiveProcess, Process, ProcessCacheScope
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel

from oras_pants_plugin.goals.common import (
    OCIArtifactFieldSet,
    OCIArtifactTagsRequest,
    OCILayoutRequest,
    OrasProcessRequest,
    oci_reference,
    read_oci_layout_manifest,
    resolve_oci_artifact_tags,
    setup_oras_process,
)
from oras_pants_plugin.subsystem import Oras
from oras_pants_plugin.target_types import OCIRegistriesField, OCIRepositoryField, SkipOCIPublishField

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class OCIPublishRequest(PublishRequest["OCIPublishFieldSet"]):
    """The `PublishRequest` carrying the OCI image layout(s) `pants package` built for an `oci_artifact` target."""


@dataclass(frozen=True)
class OCIPublishFieldSet(PublishFieldSet[OCIPublishRequest], OCIArtifactFieldSet):
    """The `PublishFieldSet` for `oci_artifact` targets."""

    publish_request_type = OCIPublishRequest

    oci_registries: OCIRegistriesField
    oci_repository: OCIRepositoryField
    skip_oras: SkipOCIPublishField

    def check_skip_request(self, package_fs: PackageFieldSet) -> OrasPublishSkipRequest | None:
        return OrasPublishSkipRequest(package_fs=package_fs, publish_fs=self)

    def get_output_data(self) -> PublishOutputData:
        return PublishOutputData({"publisher": "oras", **super().get_output_data()})


class OrasPublishSkipRequest(CheckSkipRequest[OCIPublishFieldSet]):
    """The input to determining if an `oci_artifact` target is skipped, and so not packaged, during a publish run."""


@rule(desc="Checks whether publishing an `oci_artifact` target is skipped.", level=LogLevel.DEBUG)
async def check_if_skip_oras_publish(request: OrasPublishSkipRequest, oras: Oras) -> CheckSkipResult:
    """Skips both packaging and publishing when nothing would be pushed, and says why."""
    field_set = request.publish_fs
    if oras.skip:
        reason = f"(by `[{Oras.options_scope}].skip = True`)"
    elif not oras.allow_publish:
        reason = f"(by `[{Oras.options_scope}].allow_publish = False`)"
    elif field_set.skip_oras.value:
        reason = f"(by `{field_set.skip_oras.alias}` on {request.address})"
    elif not field_set.oci_repository.value:
        reason = f"(no `{field_set.oci_repository.alias}` specified for {request.address})"
    elif not oras.registries().resolve(field_set.oci_registries.value or ()):
        reason = (
            f"(no `{field_set.oci_registries.alias}` resolved for {request.address}; set the field or mark an "
            f"`[{Oras.options_scope}].registries` entry `default = true`)"
        )
    else:
        return CheckSkipResult.no_skip()
    return CheckSkipResult.skip(names=[request.address.spec], description=reason, data=field_set.get_output_data())


@dataclass(frozen=True)
class OCICopyRequest:
    """One `oras cp`: the manifest at `manifest_digest` in the layout at `layout_path` goes to `registry`/`repository`."""

    registry: str
    repository: str
    tags: tuple[str, ...]
    layout_path: str
    manifest_digest: str
    input_digest: Digest

    @property
    def source(self) -> str:
        """The `<layout path>@<digest>` source reference; the digest form works for an untagged layout too."""
        return f"{self.layout_path}@{self.manifest_digest}"

    @property
    def reference(self) -> str:
        """The `<registry>/<repository>[:<tag>[,<tag>...]]` destination reference."""
        return oci_reference(f"{self.registry}/{self.repository}", self.tags)


def construct_oras_cp_argv(oras: Oras, request: OCICopyRequest, registry_config: str | None) -> tuple[str, ...]:
    """The `oras cp` arguments (after the binary) for `request`, with `[oras].args` after the plugin's own flags."""
    argv: list[str] = ["cp", "--from-oci-layout"]
    if registry_config:
        argv.extend(["--to-registry-config", registry_config])
    argv.extend(oras.args)
    argv.extend([request.source, request.reference])
    return tuple(argv)


@rule(desc="Set up an `oras cp` process", level=LogLevel.DEBUG)
async def setup_oras_cp_process(request: OCICopyRequest, oras: Oras, build_root: BuildRoot) -> Process:
    registry_config = os.path.join(build_root.path, oras.config) if oras.config else None
    return await setup_oras_process(
        OrasProcessRequest(
            argv=construct_oras_cp_argv(oras, request, registry_config),
            description=f"Copy OCI artifact {request.source} to {request.reference} with `oras`",
            input_digest=request.input_digest,
            # Publishing must run every time: the engine asserts this scope for non-interactive publish processes.
            cache_scope=ProcessCacheScope.PER_SESSION,
            with_registry_env=True,
        ),
        **implicitly(),
    )


@rule(desc="Copies the packaged OCI artifact to every configured OCI registry with `oras`.", level=LogLevel.DEBUG)
async def publish_oci_artifact(request: OCIPublishRequest, oras: Oras) -> PublishProcesses:
    """One interactive `oras cp` per registry and packaged layout, with the same tags `pants package` applied."""
    field_set = request.field_set
    layout_paths = tuple(
        artifact.relpath for package in request.packages for artifact in package.artifacts if artifact.relpath
    )
    registries = oras.registries().resolve(field_set.oci_registries.value or ())
    repository = field_set.oci_repository.value
    if not layout_paths or not registries or not repository:
        return PublishProcesses()

    tags = await resolve_oci_artifact_tags(OCIArtifactTagsRequest.from_field_set(field_set))
    input_digest = await merge_digests(MergeDigests(package.digest for package in request.packages))
    manifests = await concurrently(
        read_oci_layout_manifest(OCILayoutRequest(input_digest, layout_path)) for layout_path in layout_paths
    )
    copy_requests = tuple(
        OCICopyRequest(
            registry=registry.address,
            repository=repository,
            tags=tuple(tags),
            layout_path=layout_path,
            manifest_digest=manifest.digest,
            input_digest=input_digest,
        )
        for layout_path, manifest in zip(layout_paths, manifests, strict=True)
        for registry in registries
    )
    processes = await concurrently(
        setup_oras_cp_process(copy_request, **implicitly()) for copy_request in copy_requests
    )
    return PublishProcesses(
        PublishPackages(
            names=(copy_request.layout_path,),
            process=InteractiveProcess.from_process(process),
            description=copy_request.reference,
            data=PublishOutputData(
                {
                    "registry": copy_request.registry,
                    "repository": copy_request.repository,
                    "tags": copy_request.tags,
                    "digest": copy_request.manifest_digest,
                }
            ),
        )
        for copy_request, process in zip(copy_requests, processes, strict=True)
    )


def rules() -> CollectedRules:
    """Returns the `publish`-goal-specific rules for the `oras` pants plugin."""
    return (*collect_rules(), *OCIPublishFieldSet.rules(), UnionRule(CheckSkipRequest, OrasPublishSkipRequest))
