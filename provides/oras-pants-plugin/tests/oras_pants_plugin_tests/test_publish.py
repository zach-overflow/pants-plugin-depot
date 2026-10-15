import dataclasses
import json
from textwrap import dedent
from typing import Any

import pytest
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact
from pants.core.goals.publish import (
    CheckSkipRequest,
    CheckSkipResult,
    PublishFieldSet,
    PublishOutputData,
    PublishPackages,
    PublishProcesses,
    PublishRequest,
)
from pants.engine.fs import EMPTY_DIGEST, DigestContents, FileContent, Snapshot
from pants.engine.process import InteractiveProcess, Process, ProcessResult
from pants.engine.unions import UnionRule
from pants.testutil.rule_runner import RuleRunner, run_rule_with_mocks
from pants.util.frozendict import FrozenDict

from oras_pants_plugin.constants import SandboxDir
from oras_pants_plugin.goals.common import OCILayoutManifest, OCILayoutRequest
from oras_pants_plugin.goals.package import OCIArtifactPackageFieldSet
from oras_pants_plugin.goals.publish import (
    OCICopyRequest,
    OCIPublishFieldSet,
    OCIPublishRequest,
    OrasPublishSkipRequest,
    check_if_skip_oras_publish,
    construct_oras_cp_argv,
    publish_oci_artifact,
)
from oras_pants_plugin.registries import OCIRegistryNotFoundError
from oras_pants_plugin_tests.conftest import APP_ADDRESS, APP_DIR, LAYOUT_PATH, OrasFactory, make_oci_artifact

_REGISTRIES = ("ghcr.io/my-org", "localhost:5000")
_REPOSITORY = "my-app"
_DIGEST = "sha256:" + "0" * 64
_OUTPUT_DATA = PublishOutputData({"publisher": "oras", "target": APP_ADDRESS})
_PROD_REGISTRIES = {"prod": {"address": "ghcr.io/my-org", "default": True}}


def _skip_request(**field_values: Any) -> OrasPublishSkipRequest:
    target = make_oci_artifact(**field_values)
    return OrasPublishSkipRequest(
        package_fs=OCIArtifactPackageFieldSet.create(target), publish_fs=OCIPublishFieldSet.create(target)
    )


def _publish_request(packages: tuple[BuiltPackage, ...], **field_values: Any) -> OCIPublishRequest:
    field_set = OCIPublishFieldSet.create(
        make_oci_artifact(**{"oci_registries": list(_REGISTRIES), "oci_repository": _REPOSITORY, **field_values})
    )
    return OCIPublishRequest(field_set=field_set, packages=packages)


def _copy_request(**overrides: Any) -> OCICopyRequest:
    values: dict[str, Any] = {
        "registry": "ghcr.io/my-org",
        "repository": _REPOSITORY,
        "tags": ("v1",),
        "layout_path": LAYOUT_PATH,
        "manifest_digest": _DIGEST,
        "input_digest": EMPTY_DIGEST,
    }
    values.update(overrides)
    return OCICopyRequest(**values)


def test_field_set() -> None:
    target = make_oci_artifact(oci_repository=_REPOSITORY)
    assert OCIPublishFieldSet.is_applicable(target)
    field_set = OCIPublishFieldSet.create(target)
    package_fs = OCIArtifactPackageFieldSet.create(target)

    skip_request = field_set.check_skip_request(package_fs)

    assert isinstance(skip_request, OrasPublishSkipRequest)
    assert skip_request.publish_fs is field_set
    assert skip_request.package_fs is package_fs
    assert skip_request.address == APP_ADDRESS
    assert field_set.get_output_data() == _OUTPUT_DATA
    assert OCIPublishFieldSet.rules() == (
        UnionRule(PublishFieldSet, OCIPublishFieldSet),
        UnionRule(PublishRequest, OCIPublishRequest),
    )


@pytest.mark.parametrize(
    ("options", "field_values", "expected_reason"),
    [
        ({"skip": True}, {"oci_repository": _REPOSITORY, "oci_registries": ["ghcr.io"]}, "(by `[oras].skip = True`)"),
        (
            {},
            {"oci_repository": _REPOSITORY, "oci_registries": ["ghcr.io"], "skip_oras": True},
            f"(by `skip_oras` on {APP_ADDRESS})",
        ),
        ({}, {"oci_registries": ["ghcr.io"]}, f"(no `oci_repository` specified for {APP_ADDRESS})"),
        (
            {},
            {"oci_repository": _REPOSITORY},
            f"(no `oci_registries` resolved for {APP_ADDRESS}; set the field or mark an `[oras].registries` entry "
            "`default = true`)",
        ),
        (
            {},
            {"oci_repository": _REPOSITORY, "oci_registries": []},
            f"(no `oci_registries` resolved for {APP_ADDRESS}; set the field or mark an `[oras].registries` entry "
            "`default = true`)",
        ),
    ],
)
def test_check_if_skip_oras_publish_skips(
    options: dict[str, Any], field_values: dict[str, Any], expected_reason: str, oras_factory: OrasFactory
) -> None:
    actual = run_rule_with_mocks(
        check_if_skip_oras_publish, rule_args=[_skip_request(**field_values), oras_factory(**options)]
    )

    assert actual.skip_publish
    assert actual.skip_package
    assert actual.skipped_packages == (
        PublishPackages(names=(APP_ADDRESS.spec,), description=expected_reason, data=_OUTPUT_DATA),
    )


@pytest.mark.parametrize(
    ("options", "field_values"),
    [
        ({}, {"oci_repository": _REPOSITORY, "oci_registries": ["ghcr.io"]}),
        ({"registries": _PROD_REGISTRIES}, {"oci_repository": _REPOSITORY}),
        ({"registries": _PROD_REGISTRIES}, {"oci_repository": _REPOSITORY, "oci_registries": ["@prod"]}),
    ],
)
def test_check_if_skip_oras_publish_does_not_skip(
    options: dict[str, Any], field_values: dict[str, Any], oras_factory: OrasFactory
) -> None:
    actual = run_rule_with_mocks(
        check_if_skip_oras_publish, rule_args=[_skip_request(**field_values), oras_factory(**options)]
    )

    assert actual == CheckSkipResult.no_skip()


def test_check_if_skip_oras_publish_rejects_unknown_alias(oras_factory: OrasFactory) -> None:
    request = _skip_request(oci_repository=_REPOSITORY, oci_registries=["@staging"])

    with pytest.raises(OCIRegistryNotFoundError, match="staging"):
        run_rule_with_mocks(check_if_skip_oras_publish, rule_args=[request, oras_factory()])


@pytest.mark.parametrize(
    ("tags", "expected_reference"),
    [
        (("v1", "latest"), "ghcr.io/my-org/my-app:v1,latest"),
        (("v1",), "ghcr.io/my-org/my-app:v1"),
        ((), "ghcr.io/my-org/my-app"),
    ],
)
def test_copy_request_references(tags: tuple[str, ...], expected_reference: str) -> None:
    request = _copy_request(tags=tags)

    assert request.source == f"{LAYOUT_PATH}@{_DIGEST}"
    assert request.reference == expected_reference


def test_construct_oras_cp_argv(oras_factory: OrasFactory) -> None:
    """`[oras].args` follow the plugin's flags, so a repeated flag overrides the plugin's value."""
    oras = oras_factory(args=["--to-plain-http", "--to-registry-config", "/other.json"])

    assert construct_oras_cp_argv(oras, _copy_request(), "/root/auth.json") == (
        "cp",
        "--from-oci-layout",
        "--to-registry-config",
        "/root/auth.json",
        "--to-plain-http",
        "--to-registry-config",
        "/other.json",
        f"{LAYOUT_PATH}@{_DIGEST}",
        "ghcr.io/my-org/my-app:v1",
    )
    assert construct_oras_cp_argv(oras_factory(), _copy_request(tags=()), None) == (
        "cp",
        "--from-oci-layout",
        f"{LAYOUT_PATH}@{_DIGEST}",
        "ghcr.io/my-org/my-app",
    )


@pytest.mark.parametrize(
    ("packages", "field_values"),
    [
        ((BuiltPackage(EMPTY_DIGEST, ()),), {}),
        ((BuiltPackage(EMPTY_DIGEST, (BuiltPackageArtifact(LAYOUT_PATH),)),), {"oci_registries": []}),
    ],
)
def test_publish_oci_artifact_without_layouts_or_registries(
    packages: tuple[BuiltPackage, ...], field_values: dict[str, Any], oras_factory: OrasFactory
) -> None:
    actual = run_rule_with_mocks(
        publish_oci_artifact, rule_args=[_publish_request(packages, **field_values), oras_factory()]
    )

    assert actual == PublishProcesses()


def test_publish_oci_artifact(oras_factory: OrasFactory) -> None:
    """One interactive `oras cp` per registry, from the packaged layout's manifest digest, with every tag."""
    layout_digest = Snapshot.create_for_testing([f"{LAYOUT_PATH}/index.json"], [LAYOUT_PATH]).digest
    packages = (BuiltPackage(layout_digest, (BuiltPackageArtifact(LAYOUT_PATH), BuiltPackageArtifact(None))),)
    request = _publish_request(packages, oci_tags=["v1", "latest"])
    layout_requests: list[OCILayoutRequest] = []
    copy_requests: list[OCICopyRequest] = []

    def mock_read_oci_layout_manifest(layout_request: OCILayoutRequest) -> OCILayoutManifest:
        layout_requests.append(layout_request)
        return OCILayoutManifest(_DIGEST)

    def mock_setup_oras_cp_process(copy_request: OCICopyRequest) -> Process:
        copy_requests.append(copy_request)
        return Process(
            argv=("oras", "cp", copy_request.source, copy_request.reference),
            description=copy_request.reference,
            env={"HOME": "/home/me"},
            input_digest=copy_request.input_digest,
        )

    actual = run_rule_with_mocks(
        publish_oci_artifact,
        rule_args=[request, oras_factory()],
        mock_calls={
            "pants.engine.intrinsics.merge_digests": lambda _merge_digests: layout_digest,
            "oras_pants_plugin.goals.common.read_oci_layout_manifest": mock_read_oci_layout_manifest,
            "oras_pants_plugin.goals.publish.setup_oras_cp_process": mock_setup_oras_cp_process,
        },
    )

    assert layout_requests == [OCILayoutRequest(layout_digest, LAYOUT_PATH)]
    assert copy_requests == [
        _copy_request(registry=registry, tags=("v1", "latest"), input_digest=layout_digest) for registry in _REGISTRIES
    ]
    assert len(actual) == len(_REGISTRIES)
    for publish, registry in zip(actual, _REGISTRIES, strict=True):
        assert publish.names == (LAYOUT_PATH,)
        assert publish.description == f"{registry}/{_REPOSITORY}:v1,latest"
        assert publish.data == PublishOutputData(
            {"registry": registry, "repository": _REPOSITORY, "tags": ("v1", "latest"), "digest": _DIGEST}
        )
        assert isinstance(publish.process, InteractiveProcess)
        assert publish.process.process.argv == (
            "oras",
            "cp",
            f"{LAYOUT_PATH}@{_DIGEST}",
            f"{registry}/{_REPOSITORY}:v1,latest",
        )
        assert publish.process.process.env == FrozenDict({"HOME": "/home/me"})
        assert publish.process.process.input_digest == layout_digest


def test_publish_oci_artifact_resolves_registry_aliases(oras_factory: OrasFactory) -> None:
    packages = (BuiltPackage(EMPTY_DIGEST, (BuiltPackageArtifact(LAYOUT_PATH),)),)
    field_set = OCIPublishFieldSet.create(
        make_oci_artifact(oci_registries=["@prod", "localhost:5000", "ghcr.io/my-org"], oci_repository=_REPOSITORY)
    )
    oras = oras_factory(registries=_PROD_REGISTRIES)

    actual = run_rule_with_mocks(
        publish_oci_artifact,
        rule_args=[OCIPublishRequest(field_set=field_set, packages=packages), oras],
        mock_calls={
            "pants.engine.intrinsics.merge_digests": lambda _merge_digests: EMPTY_DIGEST,
            "oras_pants_plugin.goals.common.read_oci_layout_manifest": lambda _request: OCILayoutManifest(_DIGEST),
            "oras_pants_plugin.goals.publish.setup_oras_cp_process": lambda request: Process(
                argv=("oras",), description=request.reference
            ),
        },
    )

    assert [publish.description for publish in actual] == [
        "ghcr.io/my-org/my-app:latest",
        "localhost:5000/my-app:latest",
    ]


def test_check_skip_request_is_a_union_member(oras_rule_runner: RuleRunner) -> None:
    """The engine dispatches `CheckSkipRequest` to the plugin's rule; `[oras].skip` reaches it through the options."""
    oras_rule_runner.set_options(["--oras-skip"])
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": (
                'fake_package(name="cli", content="cli")\n'
                'oci_artifact(name="app", packages=[":cli"], oci_registries=["ghcr.io"], oci_repository="my-app")\n'
            )
        }
    )
    target = oras_rule_runner.get_target(APP_ADDRESS)
    request = OCIPublishFieldSet.create(target).check_skip_request(OCIArtifactPackageFieldSet.create(target))
    assert isinstance(request, CheckSkipRequest)

    actual = oras_rule_runner.request(CheckSkipResult, [request])

    assert actual.skipped_packages == (
        PublishPackages(names=(APP_ADDRESS.spec,), description="(by `[oras].skip = True`)", data=_OUTPUT_DATA),
    )


def test_default_registries_reach_the_skip_rule_through_the_options(oras_rule_runner: RuleRunner) -> None:
    oras_rule_runner.set_options(['--oras-registries={"prod": {"address": "ghcr.io/my-org", "default": true}}'])
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": (
                'fake_package(name="cli", content="cli")\n'
                'oci_artifact(name="app", packages=[":cli"], oci_repository="my-app")\n'
            )
        }
    )
    target = oras_rule_runner.get_target(APP_ADDRESS)
    request = OCIPublishFieldSet.create(target).check_skip_request(OCIArtifactPackageFieldSet.create(target))
    assert request is not None

    assert oras_rule_runner.request(CheckSkipResult, [request]) == CheckSkipResult.no_skip()


def test_oras_cp_from_the_packaged_layout_into_an_oci_layout(oras_rule_runner: RuleRunner) -> None:
    """
    Packages a real layout, then runs the real `oras cp` the plugin builds. `--to-oci-layout` in `[oras].args`
    turns the registry reference into a directory in the sandbox, which is captured and inspected.
    """
    oras_rule_runner.set_options(
        ["--oras-args=['--to-oci-layout']", "--oras-config=auth/config.json"], env_inherit={"PATH", "HOME"}
    )
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": dedent(
                """\
                fake_package(name="cli", content="cli")
                oci_artifact(
                    name="app",
                    packages=[":cli"],
                    oci_tags=["v1", "latest"],
                    oci_artifact_type="application/vnd.me.app.v1",
                    oci_registries=["example.com/team"],
                    oci_repository="app",
                )
                """
            ),
            "auth/config.json": "{}",
        }
    )
    target = oras_rule_runner.get_target(APP_ADDRESS)
    package = oras_rule_runner.request(BuiltPackage, [OCIArtifactPackageFieldSet.create(target)])
    request = OCIPublishRequest(field_set=OCIPublishFieldSet.create(target), packages=(package,))

    publishes = oras_rule_runner.request(PublishProcesses, [request])

    assert len(publishes) == 1
    assert publishes[0].names == (LAYOUT_PATH,)
    assert publishes[0].description == "example.com/team/app:v1,latest"
    assert isinstance(publishes[0].process, InteractiveProcess)
    process = publishes[0].process.process
    assert process.argv[0] == f"{SandboxDir.ORAS_INPUT_DIRNAME}/oras"
    assert process.argv[1:5] == (
        "cp",
        "--from-oci-layout",
        "--to-registry-config",
        f"{oras_rule_runner.build_root}/auth/config.json",
    )
    assert process.description.startswith(f"Copy OCI artifact {LAYOUT_PATH}@sha256:")
    assert SandboxDir.ORAS_INPUT_DIRNAME in process.immutable_input_digests
    assert "PATH" in process.env

    result = oras_rule_runner.request(
        ProcessResult, [dataclasses.replace(process, output_directories=("example.com",))]
    )

    copied = {
        content.path: content.content
        for content in oras_rule_runner.request(DigestContents, [result.output_digest])
        if isinstance(content, FileContent)
    }
    index = json.loads(copied["example.com/team/app/index.json"])
    # `oras` tags concurrently, so the index order varies.
    assert {entry["annotations"]["org.opencontainers.image.ref.name"] for entry in index["manifests"]} == {
        "v1",
        "latest",
    }
    assert {entry["digest"] for entry in index["manifests"]} == {publishes[0].data["digest"]}
    algorithm, hex_digest = index["manifests"][0]["digest"].split(":")
    manifest = json.loads(copied[f"example.com/team/app/blobs/{algorithm}/{hex_digest}"])
    assert manifest["artifactType"] == "application/vnd.me.app.v1"
    assert [layer["annotations"]["org.opencontainers.image.title"] for layer in manifest["layers"]] == [
        "src.app/cli.txt"
    ]
