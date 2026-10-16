from dataclasses import dataclass
from typing import Any, Protocol

import pytest
from pants.core.goals import package as core_package
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact, OutputPathField, PackageFieldSet
from pants.core.goals.publish import CheckSkipResult, PublishProcesses
from pants.core.target_types import FileTarget, ResourceTarget
from pants.core.util_rules import env_vars, external_tool
from pants.core.util_rules.external_tool import UnsupportedVersionUsage
from pants.engine.addresses import Address
from pants.engine.fs import CreateDigest, Digest, DigestContents, FileContent, Snapshot
from pants.engine.intrinsics import create_digest
from pants.engine.process import Process, ProcessResult
from pants.engine.rules import collect_rules, rule
from pants.engine.target import COMMON_TARGET_FIELDS, StringField, Target
from pants.engine.unions import UnionRule
from pants.testutil.option_util import create_subsystem
from pants.testutil.rule_runner import QueryRule, RuleRunner

from oras_pants_plugin import subsystem
from oras_pants_plugin.goals import common, package, publish
from oras_pants_plugin.goals.common import OCIArtifactTags, OCIArtifactTagsRequest
from oras_pants_plugin.goals.package import OCIArtifactPackageFieldSet
from oras_pants_plugin.goals.publish import OCIPublishRequest, OrasPublishSkipRequest
from oras_pants_plugin.subsystem import Oras
from oras_pants_plugin.target_types import OCIArtifact
from pants_plugin_developer_utils.testing_utils import (
    RuleRunnerFactory,
    rule_runner_factory,  # noqa: F401
)

APP_DIR = "src/app"
"""Directory of the `oci_artifact` target the tests build and publish."""

APP_ADDRESS = Address(APP_DIR, target_name="app")
"""Address of the `oci_artifact` target the tests build and publish."""

LAYOUT_PATH = "src.app/app"
"""The default `output_path` of `APP_ADDRESS`: where `pants package` writes the OCI image layout."""


class FakePackageContentField(StringField):
    alias = "content"
    required = True
    value: str


class FakePackageTarget(Target):
    """A stand-in for `pex_binary`: `pants package` writes `content` to `<output_path>.txt`, with no tool involved."""

    alias = "fake_package"
    core_fields = (*COMMON_TARGET_FIELDS, FakePackageContentField, OutputPathField)
    help = "Test-only package-able target."


@dataclass(frozen=True)
class FakePackageFieldSet(PackageFieldSet):
    required_fields = (FakePackageContentField,)

    content: FakePackageContentField
    output_path: OutputPathField


@rule
async def package_fake(field_set: FakePackageFieldSet) -> BuiltPackage:
    path = field_set.output_path.value_or_default(file_ending="txt")
    digest = await create_digest(CreateDigest([FileContent(path, field_set.content.value.encode())]))
    return BuiltPackage(digest, (BuiltPackageArtifact(path),))


class OrasFactory(Protocol):
    """Type of the factory returned by the `oras_factory` fixture."""

    def __call__(self, **overrides: Any) -> Oras: ...


@pytest.fixture(scope="function")
def oras_factory() -> OrasFactory:
    """Factory fixture building an `Oras` subsystem with default option values, without the engine."""

    def _factory(**overrides: Any) -> Oras:
        options: dict[str, Any] = {
            "version": Oras.default_version,
            "known_versions": list(Oras.default_known_versions),
            "url_template": Oras.default_url_template,
            "url_platform_mapping": dict(Oras.default_url_platform_mapping),
            "use_unsupported_version": UnsupportedVersionUsage.RaiseError,
            "skip": False,
            "allow_publish": True,
            "args": [],
            "config": None,
            "registries": {},
            "extra_env_vars": [],
        }
        options.update(overrides)
        return create_subsystem(Oras, **options)

    return _factory


@pytest.fixture(scope="function")
def oras_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:  # noqa: F811
    """Integration `RuleRunner`: requesting a `BuiltPackage` or `PublishProcesses` downloads the real `oras` (network)."""
    return rule_runner_factory(
        rules=[
            *common.rules(),
            *package.rules(),
            *publish.rules(),
            *subsystem.rules(),
            *core_package.rules(),
            *external_tool.rules(),
            *env_vars.rules(),
            *collect_rules({"package_fake": package_fake}),
            UnionRule(PackageFieldSet, FakePackageFieldSet),
            QueryRule(BuiltPackage, [OCIArtifactPackageFieldSet]),
            QueryRule(OCIArtifactTags, [OCIArtifactTagsRequest]),
            QueryRule(PublishProcesses, [OCIPublishRequest]),
            QueryRule(CheckSkipResult, [OrasPublishSkipRequest]),
            QueryRule(ProcessResult, [Process]),
            QueryRule(DigestContents, [Digest]),
            QueryRule(Snapshot, [Digest]),
        ],
        target_types=[OCIArtifact, FakePackageTarget, FileTarget, ResourceTarget],
    )


def make_oci_artifact(**field_values: Any) -> OCIArtifact:
    """An `oci_artifact` target at `APP_ADDRESS`, built without the engine."""
    return OCIArtifact({"packages": [":pkg"], **field_values}, APP_ADDRESS)
