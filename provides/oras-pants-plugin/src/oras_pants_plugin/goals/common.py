"""Rules and field sets shared by the `package` and `publish` goals for `oci_artifact` targets."""

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self

from pants.core.target_types import FileSourceField, ResourceSourceField
from pants.core.util_rules.env_vars import environment_vars_subset
from pants.core.util_rules.external_tool import download_external_tool
from pants.engine.collection import Collection
from pants.engine.env_vars import EnvironmentVars
from pants.engine.fs import EMPTY_DIGEST, Digest, DigestContents, DigestSubset, FileContent, PathGlobs
from pants.engine.internals.graph import hydrate_sources, resolve_targets
from pants.engine.intrinsics import digest_subset_to_digest, get_digest_contents
from pants.engine.platform import Platform
from pants.engine.process import Process, ProcessCacheScope
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.target import Field, FieldSet, HydrateSourcesRequest, InvalidFieldException, SourcesField
from pants.util.logging import LogLevel

from oras_pants_plugin.constants import OCI_LAYOUT_INDEX_FILENAME, SandboxDir
from oras_pants_plugin.subsystem import Oras
from oras_pants_plugin.target_types import OCIArtifactPackagesField, OCITagFilesField, OCITagsField

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


@dataclass(frozen=True)
class OCIArtifactFieldSet(FieldSet):
    """The fields the `package` and `publish` goals both read from an `oci_artifact` target."""

    required_fields: ClassVar[tuple[type[Field], ...]] = (OCIArtifactPackagesField,)

    packages: OCIArtifactPackagesField
    oci_tags: OCITagsField
    oci_tag_files: OCITagFilesField


def oci_reference(base: str, tags: Iterable[str]) -> str:
    """`<base>[:<tag>[,<tag>...]]`, the reference syntax of `oras push` and `oras cp`; no tags means untagged."""
    joined = ",".join(tags)
    return f"{base}:{joined}" if joined else base


def oras_file_arg(path: str) -> str:
    """`oras` parses `<file>:<media type>`, so a path containing `:` needs a trailing `:` to keep the default type."""
    return f"{path}:" if ":" in path else path


@dataclass(frozen=True)
class OCIArtifactTagsRequest:
    """The two tag fields of one `oci_artifact` target."""

    oci_tags: OCITagsField
    oci_tag_files: OCITagFilesField

    @classmethod
    def from_field_set(cls, field_set: OCIArtifactFieldSet) -> Self:
        return cls(oci_tags=field_set.oci_tags, oci_tag_files=field_set.oci_tag_files)


class OCIArtifactTags(Collection[str]):
    """The tags of an `oci_artifact`, in order: the `oci_tags` entries, then the lines of each `oci_tag_files` file."""


def tag_lines(contents: DigestContents) -> tuple[str, ...]:
    """The non-blank lines of every file in `contents`, stripped, in file order."""
    return tuple(
        stripped
        for entry in contents
        if isinstance(entry, FileContent)
        for line in entry.content.decode().splitlines()
        if (stripped := line.strip())
    )


@rule(desc="Resolve the tags of an `oci_artifact` target", level=LogLevel.DEBUG)
async def resolve_oci_artifact_tags(request: OCIArtifactTagsRequest) -> OCIArtifactTags:
    """`oci_tags`, then every non-blank line of the `oci_tag_files` files (code generators run), without duplicates."""
    tags: dict[str, None] = dict.fromkeys(request.oci_tags.value or ())
    tag_files = request.oci_tag_files
    if not tag_files.value:
        return OCIArtifactTags(tags)

    targets = await resolve_targets(**implicitly(tag_files.to_unparsed_address_inputs()))
    hydrated_sources = await concurrently(
        hydrate_sources(
            HydrateSourcesRequest(
                tgt.get(SourcesField), for_sources_types=(FileSourceField, ResourceSourceField), enable_codegen=True
            ),
            **implicitly(),
        )
        for tgt in targets
    )
    contents = await concurrently(get_digest_contents(sources.snapshot.digest) for sources in hydrated_sources)
    for target, sources, digest_contents in zip(targets, hydrated_sources, contents, strict=True):
        listed = f"The `{tag_files.alias}` field of target {tag_files.address} lists {target.address}"
        if sources.sources_type is None:
            raise InvalidFieldException(
                f"{listed}, a `{target.alias}` target without `file` or `resource` sources. List `file`, `resource` "
                "or code generator targets that produce them, such as `scm_version_file`."
            )
        try:
            file_tags = tag_lines(digest_contents)
        except UnicodeDecodeError as e:
            raise InvalidFieldException(f"{listed}, whose files are not UTF-8 text: {e}") from e
        if not file_tags:
            raise InvalidFieldException(f"{listed}, whose files hold no tags: a tag file needs a non-blank line.")
        tags.update(dict.fromkeys(file_tags))
    return OCIArtifactTags(tags)


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
