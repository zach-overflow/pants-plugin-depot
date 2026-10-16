"""Lets Python dependency inference resolve imports of a `scm_version` target's generated module."""

from collections import defaultdict
from typing import TYPE_CHECKING, cast

from pants.backend.python.dependency_inference.module_mapper import (
    FirstPartyPythonMappingImpl,
    FirstPartyPythonMappingImplMarker,
    ModuleProvider,
    ModuleProviderType,
    ResolveName,
)
from pants.backend.python.subsystems.setup import PythonSetup
from pants.backend.python.target_types import PythonResolveField
from pants.core.util_rules.stripped_source_files import StrippedFileNameRequest, strip_file_name
from pants.engine.internals.selectors import concurrently
from pants.engine.rules import collect_rules, rule
from pants.engine.target import AllTargets, Targets
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel

from vcs_versioning_pants_plugin.target_types import ScmVersionGenerateToField, ScmVersionPythonResolveField

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class ScmVersionMappingMarker(FirstPartyPythonMappingImplMarker):
    """Registers this mapping with Pants' Python dependency inference. Its own marker: no clash with `vcs_version`."""


class AllScmVersionTargets(Targets):
    """Exists so `map_scm_version_to_python_modules` is not invalidated by every target change."""


@rule(desc="Find all scm_version targets in project", level=LogLevel.DEBUG)
async def find_all_scm_version_targets(targets: AllTargets) -> AllScmVersionTargets:
    # `scm_version_file` targets generate plain files, not modules; only `scm_version` has a `python_resolve`.
    return AllScmVersionTargets(tgt for tgt in targets if tgt.has_field(ScmVersionPythonResolveField))


@rule
async def map_scm_version_to_python_modules(
    scm_version_targets: AllScmVersionTargets, python_setup: PythonSetup, _: ScmVersionMappingMarker
) -> FirstPartyPythonMappingImpl:
    suffix = ".py"
    targets = [tgt for tgt in scm_version_targets if cast("str", tgt[ScmVersionGenerateToField].value).endswith(suffix)]
    stripped_files = await concurrently(
        strip_file_name(StrippedFileNameRequest(cast("str", tgt[ScmVersionGenerateToField].value))) for tgt in targets
    )
    resolves_to_modules_to_providers: defaultdict[ResolveName, defaultdict[str, list[ModuleProvider]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for tgt, stripped_file in zip(targets, stripped_files, strict=True):
        resolve = tgt[PythonResolveField].normalized_value(python_setup)
        module = stripped_file.value[: -len(suffix)].replace("/", ".")
        resolves_to_modules_to_providers[resolve][module].append(ModuleProvider(tgt.address, ModuleProviderType.IMPL))
    return FirstPartyPythonMappingImpl.create(resolves_to_modules_to_providers)


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(FirstPartyPythonMappingImplMarker, ScmVersionMappingMarker))
