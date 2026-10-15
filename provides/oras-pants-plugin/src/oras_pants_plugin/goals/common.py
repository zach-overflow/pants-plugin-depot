"""Rules and field sets shared by the `package` and `publish` goals for `oci_artifact` targets."""

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from pants.core.util_rules.env_vars import environment_vars_subset
from pants.core.util_rules.external_tool import download_external_tool
from pants.engine.env_vars import EnvironmentVars
from pants.engine.fs import EMPTY_DIGEST, Digest, DigestSubset, PathGlobs
from pants.engine.intrinsics import digest_subset_to_digest, get_digest_contents
from pants.engine.platform import Platform
from pants.engine.process import Process, ProcessCacheScope
from pants.engine.rules import collect_rules, implicitly, rule
from pants.engine.target import Field, FieldSet
from pants.util.logging import LogLevel

from oras_pants_plugin.constants import OCI_LAYOUT_INDEX_FILENAME, SandboxDir
from oras_pants_plugin.subsystem import Oras
from oras_pants_plugin.target_types import OCIArtifactPackagesField, OCITagsField

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


@dataclass(frozen=True)
class OCIArtifactFieldSet(FieldSet):
    """The fields the `package` and `publish` goals both read from an `oci_artifact` target."""

    required_fields: ClassVar[tuple[type[Field], ...]] = (OCIArtifactPackagesField,)

    packages: OCIArtifactPackagesField
    oci_tags: OCITagsField


def oci_reference(base: str, tags: Iterable[str]) -> str:
    """`<base>[:<tag>[,<tag>...]]`, the reference syntax of `oras push` and `oras cp`; no tags means untagged."""
    joined = ",".join(tags)
    return f"{base}:{joined}" if joined else base


def oras_file_arg(path: str) -> str:
    """`oras` parses `<file>:<media type>`, so a path containing `:` needs a trailing `:` to keep the default type."""
    return f"{path}:" if ":" in path else path


@dataclass(frozen=True)
class OrasProcessRequest:
    """An `oras` invocation; `argv` follows the binary. `with_registry_env` passes the credential environment through."""

    argv: tuple[str, ...]
    description: str
    input_digest: Digest = EMPTY_DIGEST
    output_directories: tuple[str, ...] = ()
    cache_scope: ProcessCacheScope = ProcessCacheScope.SUCCESSFUL
    with_registry_env: bool = False


@rule(desc="Set up an `oras` process", level=LogLevel.DEBUG)
async def setup_oras_process(request: OrasProcessRequest, oras: Oras, platform: Platform) -> Process:
    downloaded_oras = await download_external_tool(oras.get_request(platform))
    env = (
        await environment_vars_subset(oras.create_env_vars_request(), **implicitly())
        if request.with_registry_env
        else EnvironmentVars()
    )
    exe = os.path.normpath(os.path.join(SandboxDir.ORAS_INPUT_DIRNAME, downloaded_oras.exe))
    return Process(
        argv=(exe, *request.argv),
        input_digest=request.input_digest,
        immutable_input_digests={SandboxDir.ORAS_INPUT_DIRNAME: downloaded_oras.digest},
        env=env,
        output_directories=request.output_directories,
        description=request.description,
        level=LogLevel.DEBUG,
        cache_scope=request.cache_scope,
    )


@dataclass(frozen=True)
class OCILayoutRequest:
    """An OCI image layout directory at `path` within `digest`."""

    digest: Digest
    path: str


@dataclass(frozen=True)
class OCILayoutManifest:
    """The single manifest of an OCI image layout, by `<algorithm>:<hex>` digest."""

    digest: str


@rule(desc="Read the manifest digest of an OCI image layout", level=LogLevel.DEBUG)
async def read_oci_layout_manifest(request: OCILayoutRequest) -> OCILayoutManifest:
    index_path = os.path.join(request.path, OCI_LAYOUT_INDEX_FILENAME)
    index_digest = await digest_subset_to_digest(DigestSubset(request.digest, PathGlobs([index_path])))
    contents = await get_digest_contents(index_digest)
    if not contents:
        raise ValueError(f"`{request.path}` is not an OCI image layout: it has no `{OCI_LAYOUT_INDEX_FILENAME}`.")
    index = json.loads(contents[0].content)
    digests: set[str] = {str(manifest["digest"]) for manifest in index.get("manifests", ())}
    if len(digests) != 1:
        raise ValueError(
            f"Expected exactly one manifest in the OCI image layout `{request.path}`, found {sorted(digests)}."
        )
    return OCILayoutManifest(digests.pop())


def rules() -> CollectedRules:
    return collect_rules()
