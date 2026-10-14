"""
Implements a publisher for wrapping `BuiltPackage` instances as OCI artifacts and publishing those to an OCI
registry by using `oras`.
See also:
    https://www.pantsbuild.org/stable/docs/writing-plugins/common-plugin-tasks/add-a-publisher
    https://oras.land/
"""

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from pants.backend.python.goals.package_pex_binary import PexBinaryFieldSet
from pants.backend.python.target_types import PexLayoutField
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
from pants.core.util_rules.env_vars import environment_vars_subset
from pants.core.util_rules.external_tool import download_external_tool
from pants.engine.env_vars import EnvironmentVarsRequest
from pants.engine.fs import Digest, MergeDigests
from pants.engine.intrinsics import merge_digests
from pants.engine.platform import Platform
from pants.engine.process import InteractiveProcess, Process, ProcessCacheScope
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel
from pants.util.strutil import pluralize

from oras_pants_plugin.fields import (
    OciMediaType,
    OrasRepositoriesField,
    OrasTagsField,
    PexOciMediaType,
    SkipOrasPublishField,
)
from oras_pants_plugin.subsystem import ORAS_BASE_ENV_VAR_NAMES, Oras

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules

ORAS_INPUT_DIR: Final[str] = "__oras__"
"""Sandbox directory the downloaded `oras` binary is mounted in, out of the way of the pushed files."""


class OrasPublishRequest(PublishRequest["OrasPublishFieldSet"]):
    """The general `PublishRequest` type which should be subtyped per `oras`-publishable target type."""


class OrasPublishPexRequest(OrasPublishRequest):
    """The `PublishRequest` subtype specifically for publishing PEX artifacts to OCI registries."""


@dataclass(frozen=True)
class OrasPublishFieldSet(PublishFieldSet[OrasPublishRequest]):
    """
    The base `PublishFieldSet` to subtype per `oras`-publishable target type.

    A subtype narrows `required_fields` to the target type's `OciMediaType` subclass, so `oci_media_type` carries
    that subclass's default.
    """

    required_fields = (OrasRepositoriesField, OrasTagsField, OciMediaType, SkipOrasPublishField)

    oci_repositories: OrasRepositoriesField
    oci_tags: OrasTagsField
    oci_media_type: OciMediaType
    skip_oras: SkipOrasPublishField

    def check_skip_request(self, package_fs: PackageFieldSet) -> OrasPublishSkipRequest | None:
        return OrasPublishSkipRequest(package_fs=package_fs, publish_fs=self)

    def get_output_data(self) -> PublishOutputData:
        return PublishOutputData({"publisher": "oras", **super().get_output_data()})


@dataclass(frozen=True)
class OrasPublishPexFieldSet(OrasPublishFieldSet):
    """The fields required for publishing a `pex_binary` target's package output artifact to an OCI registry."""

    publish_request_type = OrasPublishPexRequest
    required_fields = (*OrasPublishFieldSet.required_fields, PexOciMediaType, PexLayoutField)


class OrasPublishSkipRequest(CheckSkipRequest[OrasPublishFieldSet]):
    """The input to determining if an `oras`-compatible target should be skipped during a publish run."""


@rule(desc="Checks whether `oras push` is skipped for a target.", level=LogLevel.DEBUG)
async def check_if_skip_oras_push(request: OrasPublishSkipRequest, oras: Oras) -> CheckSkipResult:
    """Skips both packaging and publishing when nothing would be pushed, and says why."""
    if oras.skip:
        reason = f"(by `[{Oras.options_scope}].skip = True`)"
    elif request.publish_fs.skip_oras.value:
        reason = f"(by `{request.publish_fs.skip_oras.alias}` on {request.address})"
    elif not request.publish_fs.oci_repositories.value:
        reason = f"(no `{request.publish_fs.oci_repositories.alias}` specified for {request.address})"
    else:
        return CheckSkipResult.no_skip()
    name = (
        request.package_fs.output_pex_filename()
        if isinstance(request.package_fs, PexBinaryFieldSet)
        else request.address.spec
    )
    return CheckSkipResult.skip(names=[name], description=reason, data=request.publish_fs.get_output_data())


@dataclass(frozen=True)
class OrasPushRequest:
    """One `oras push`: every `files` entry becomes a layer of the artifact at `repository`, tagged with `tags`."""

    repository: str
    tags: tuple[str, ...]
    files: tuple[str, ...]
    input_digest: Digest
    artifact_type: str | None = None

    @property
    def reference(self) -> str:
        """The `<repository>[:<tag>[,<tag>...]]` argument of `oras push`; no tags pushes the artifact untagged."""
        return f"{self.repository}:{','.join(self.tags)}" if self.tags else self.repository


def construct_oras_push_argv(oras: Oras, exe: str, request: OrasPushRequest) -> tuple[str, ...]:
    """Returns the full `oras push` command line for `request`, with `[oras].args` after the plugin's own flags."""
    argv: list[str] = [exe, "push"]
    if request.artifact_type:
        argv.extend(["--artifact-type", request.artifact_type])
    argv.extend(oras.args)
    argv.append(request.reference)
    # `oras` parses `<file>:<media type>`, so a path containing `:` needs a trailing `:` to keep the default type.
    argv.extend(f"{file}:" if ":" in file else file for file in request.files)
    return tuple(argv)


@rule(desc="Set up an `oras push` process", level=LogLevel.DEBUG)
async def setup_oras_push_process(request: OrasPushRequest, oras: Oras, platform: Platform) -> Process:
    downloaded_oras, env = await concurrently(
        download_external_tool(oras.get_request(platform)),
        environment_vars_subset(
            EnvironmentVarsRequest([*ORAS_BASE_ENV_VAR_NAMES, *oras.extra_env_vars]), **implicitly()
        ),
    )
    return Process(
        argv=construct_oras_push_argv(
            oras, os.path.normpath(os.path.join(ORAS_INPUT_DIR, downloaded_oras.exe)), request
        ),
        input_digest=request.input_digest,
        immutable_input_digests={ORAS_INPUT_DIR: downloaded_oras.digest},
        env=env,
        description=f"Push {pluralize(len(request.files), 'file')} to {request.reference} with `oras`",
        level=LogLevel.DEBUG,
        # Publishing must run every time: the engine asserts this scope for non-interactive publish processes.
        cache_scope=ProcessCacheScope.PER_SESSION,
    )


@rule(
    desc="Uses `oras` to wrap PEX artifacts as an OCI artifact and push to the configured OCI registry.",
    level=LogLevel.DEBUG,
)
async def publish_pex_as_oci_artifact(request: OrasPublishPexRequest) -> PublishProcesses:
    """One interactive `oras push` per repository, each pushing every artifact `pants package` built."""
    files = tuple(artifact.relpath for pkg in request.packages for artifact in pkg.artifacts if artifact.relpath)
    if not files:
        return PublishProcesses()

    input_digest = await merge_digests(MergeDigests(pkg.digest for pkg in request.packages))
    field_set = request.field_set
    push_requests = tuple(
        OrasPushRequest(
            repository=repository,
            tags=field_set.oci_tags.value or (),
            files=files,
            input_digest=input_digest,
            artifact_type=field_set.oci_media_type.value,
        )
        for repository in field_set.oci_repositories.value or ()
    )
    processes = await concurrently(
        setup_oras_push_process(push_request, **implicitly()) for push_request in push_requests
    )
    return PublishProcesses(
        PublishPackages(
            names=files,
            process=InteractiveProcess.from_process(process),
            description=push_request.reference,
            data=PublishOutputData({"repository": push_request.repository, "tags": push_request.tags}),
        )
        for push_request, process in zip(push_requests, processes, strict=True)
    )


def rules() -> CollectedRules:
    """Returns the `publish`-goal-specific rules for the `oras` pants plugin."""
    return (*collect_rules(), *OrasPublishPexFieldSet.rules(), UnionRule(CheckSkipRequest, OrasPublishSkipRequest))
