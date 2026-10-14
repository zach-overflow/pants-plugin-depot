import dataclasses
import json
from typing import Any

import pytest
from pants.backend.python.goals.package_pex_binary import PexBinaryFieldSet
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

from oras_pants_plugin.goals.publish import (
    ORAS_INPUT_DIR,
    OrasPublishFieldSet,
    OrasPublishPexFieldSet,
    OrasPublishPexRequest,
    OrasPublishSkipRequest,
    OrasPushRequest,
    check_if_skip_oras_push,
    construct_oras_push_argv,
    publish_pex_as_oci_artifact,
)
from oras_pants_plugin_tests.conftest import APP_ADDRESS, APP_DIR, OrasFactory, make_pex_binary

_REPOSITORIES = ("ghcr.io/my-org/my-app", "localhost:5000/my-app")
_PEX_PATH = "src.app/app.pex"
_FILES = (_PEX_PATH, "src.app/app")
_OUTPUT_DATA = PublishOutputData({"publisher": "oras", "target": APP_ADDRESS})


def _skip_request(**field_values: Any) -> OrasPublishSkipRequest:
    target = make_pex_binary(**field_values)
    return OrasPublishSkipRequest(
        package_fs=PexBinaryFieldSet.create(target), publish_fs=OrasPublishPexFieldSet.create(target)
    )


def _publish_request(packages: tuple[BuiltPackage, ...], **field_values: Any) -> OrasPublishPexRequest:
    field_set = OrasPublishPexFieldSet.create(make_pex_binary(oci_repositories=list(_REPOSITORIES), **field_values))
    return OrasPublishPexRequest(field_set=field_set, packages=packages)


def test_field_set() -> None:
    target = make_pex_binary(oci_repositories=["ghcr.io/my-org/my-app"])
    assert OrasPublishPexFieldSet.is_applicable(target)
    field_set = OrasPublishPexFieldSet.create(target)
    package_fs = PexBinaryFieldSet.create(target)

    skip_request = field_set.check_skip_request(package_fs)

    assert isinstance(skip_request, OrasPublishSkipRequest)
    assert skip_request.publish_fs is field_set
    assert skip_request.package_fs is package_fs
    assert skip_request.address == APP_ADDRESS
    assert field_set.get_output_data() == _OUTPUT_DATA
    assert OrasPublishPexFieldSet.rules() == (
        UnionRule(PublishFieldSet, OrasPublishPexFieldSet),
        UnionRule(PublishRequest, OrasPublishPexRequest),
    )
    assert set(OrasPublishPexFieldSet.required_fields) > set(OrasPublishFieldSet.required_fields)


@pytest.mark.parametrize(
    ("skip_option", "field_values", "expected_reason"),
    [
        (True, {"oci_repositories": ["ghcr.io/my-org/my-app"]}, "(by `[oras].skip = True`)"),
        (
            False,
            {"oci_repositories": ["ghcr.io/my-org/my-app"], "skip_oras": True},
            f"(by `skip_oras` on {APP_ADDRESS})",
        ),
        (False, {}, f"(no `oci_repositories` specified for {APP_ADDRESS})"),
        (False, {"oci_repositories": []}, f"(no `oci_repositories` specified for {APP_ADDRESS})"),
    ],
)
def test_check_if_skip_oras_push_skips(
    skip_option: bool, field_values: dict[str, Any], expected_reason: str, oras_factory: OrasFactory
) -> None:
    actual = run_rule_with_mocks(
        check_if_skip_oras_push, rule_args=[_skip_request(**field_values), oras_factory(skip=skip_option)]
    )

    assert actual.skip_publish
    assert actual.skip_package
    assert actual.skipped_packages == (
        PublishPackages(names=(_PEX_PATH,), description=expected_reason, data=_OUTPUT_DATA),
    )


def test_check_if_skip_oras_push_does_not_skip(oras_factory: OrasFactory) -> None:
    actual = run_rule_with_mocks(
        check_if_skip_oras_push, rule_args=[_skip_request(oci_repositories=["ghcr.io/my-org/my-app"]), oras_factory()]
    )

    assert actual == CheckSkipResult.no_skip()


@pytest.mark.parametrize(
    ("tags", "expected_reference"),
    [
        (("v1", "latest"), "ghcr.io/my-org/my-app:v1,latest"),
        (("v1",), "ghcr.io/my-org/my-app:v1"),
        ((), "ghcr.io/my-org/my-app"),
    ],
)
def test_push_request_reference(tags: tuple[str, ...], expected_reference: str) -> None:
    request = OrasPushRequest(repository="ghcr.io/my-org/my-app", tags=tags, files=_FILES, input_digest=EMPTY_DIGEST)

    assert request.reference == expected_reference


def test_construct_oras_push_argv(oras_factory: OrasFactory) -> None:
    """`[oras].args` follow the plugin's flags, and a `:` in a file path is escaped from `oras`' `<file>:<type>` syntax."""
    request = OrasPushRequest(
        repository="ghcr.io/my-org/my-app",
        tags=("v1",),
        files=(_PEX_PATH, "dist/app:v1.pex"),
        input_digest=EMPTY_DIGEST,
        artifact_type="application/vnd.python.pex.v1",
    )

    actual = construct_oras_push_argv(oras_factory(args=["--plain-http", "--artifact-type", "x/y"]), "./oras", request)

    assert actual == (
        "./oras",
        "push",
        "--artifact-type",
        "application/vnd.python.pex.v1",
        "--plain-http",
        "--artifact-type",
        "x/y",
        "ghcr.io/my-org/my-app:v1",
        _PEX_PATH,
        "dist/app:v1.pex:",
    )


def test_construct_oras_push_argv_without_artifact_type(oras_factory: OrasFactory) -> None:
    request = OrasPushRequest(
        repository="ghcr.io/my-org/my-app", tags=(), files=(_PEX_PATH,), input_digest=EMPTY_DIGEST
    )

    assert construct_oras_push_argv(oras_factory(), "./oras", request) == (
        "./oras",
        "push",
        "ghcr.io/my-org/my-app",
        _PEX_PATH,
    )


def test_publish_pex_as_oci_artifact_without_artifacts() -> None:
    request = _publish_request((BuiltPackage(EMPTY_DIGEST, ()),))

    actual = run_rule_with_mocks(publish_pex_as_oci_artifact, rule_args=[request])

    assert actual == PublishProcesses()


def test_publish_pex_as_oci_artifact() -> None:
    """One interactive `oras push` process per repository, each pushing every built artifact with every tag."""
    packages = (
        BuiltPackage(EMPTY_DIGEST, (BuiltPackageArtifact(_PEX_PATH), BuiltPackageArtifact(None, ("built it",)))),
        BuiltPackage(EMPTY_DIGEST, (BuiltPackageArtifact("src.app/app"),)),
    )
    request = _publish_request(packages, oci_tags=["v1", "latest"])
    merged_digest = Snapshot.create_for_testing(list(_FILES), []).digest
    push_requests: list[OrasPushRequest] = []

    def mock_setup_oras_push_process(push_request: OrasPushRequest) -> Process:
        push_requests.append(push_request)
        return Process(
            argv=("oras", "push", push_request.reference, *push_request.files),
            description=push_request.reference,
            env={"HOME": "/home/me"},
            input_digest=push_request.input_digest,
        )

    actual = run_rule_with_mocks(
        publish_pex_as_oci_artifact,
        rule_args=[request],
        mock_calls={
            "pants.engine.intrinsics.merge_digests": lambda _merge_digests: merged_digest,
            "oras_pants_plugin.goals.publish.setup_oras_push_process": mock_setup_oras_push_process,
        },
    )

    assert push_requests == [
        OrasPushRequest(
            repository=repository,
            tags=("v1", "latest"),
            files=_FILES,
            input_digest=merged_digest,
            artifact_type="application/vnd.python.pex.v1",
        )
        for repository in _REPOSITORIES
    ]
    assert len(actual) == len(_REPOSITORIES)
    for publish, repository in zip(actual, _REPOSITORIES, strict=True):
        assert publish.names == _FILES
        assert publish.description == f"{repository}:v1,latest"
        assert publish.data == PublishOutputData({"repository": repository, "tags": ("v1", "latest")})
        assert isinstance(publish.process, InteractiveProcess)
        assert publish.process.process.argv == ("oras", "push", f"{repository}:v1,latest", *_FILES)
        assert publish.process.process.env == FrozenDict({"HOME": "/home/me"})
        assert publish.process.process.input_digest == merged_digest


def test_check_skip_request_is_a_union_member(oras_rule_runner: RuleRunner) -> None:
    """The engine dispatches `CheckSkipRequest` to the plugin's rule; `[oras].skip` reaches it through the options."""
    oras_rule_runner.set_options(["--oras-skip"])
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": 'pex_binary(name="app", entry_point="main.py", oci_repositories=["ghcr.io/my-org/my-app"])\n'
        }
    )
    target = oras_rule_runner.get_target(APP_ADDRESS)
    request = OrasPublishPexFieldSet.create(target).check_skip_request(PexBinaryFieldSet.create(target))
    assert isinstance(request, CheckSkipRequest)

    actual = oras_rule_runner.request(CheckSkipResult, [request])

    assert actual.skipped_packages == (
        PublishPackages(names=(_PEX_PATH,), description="(by `[oras].skip = True`)", data=_OUTPUT_DATA),
    )


def test_oras_push_into_an_oci_layout(oras_rule_runner: RuleRunner) -> None:
    """
    Runs the real `oras` (downloaded) with the process the plugin builds. `--oci-layout-path` redirects the push
    from the registry in the reference to a directory in the sandbox, which is captured and inspected.
    """
    oras_rule_runner.set_options(["--oras-args=['--oci-layout-path', 'oci-layout']"])
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": (
                'pex_binary(name="app", entry_point="main.py", oci_repositories=["example.com/team/app"], '
                'oci_tags=["v1", "latest"])\n'
            ),
            f"{APP_DIR}/main.py": "",
        }
    )
    pex_snapshot = oras_rule_runner.make_snapshot({_PEX_PATH: "#!/usr/bin/env python3\n"})
    field_set = OrasPublishPexFieldSet.create(oras_rule_runner.get_target(APP_ADDRESS))
    request = OrasPublishPexRequest(
        field_set=field_set, packages=(BuiltPackage(pex_snapshot.digest, (BuiltPackageArtifact(_PEX_PATH),)),)
    )

    publishes = oras_rule_runner.request(PublishProcesses, [request])

    assert len(publishes) == 1
    assert publishes[0].names == (_PEX_PATH,)
    assert publishes[0].description == "example.com/team/app:v1,latest"
    assert isinstance(publishes[0].process, InteractiveProcess)
    process = publishes[0].process.process
    assert process.argv[0] == f"{ORAS_INPUT_DIR}/oras"
    assert process.description == "Push 1 file to example.com/team/app:v1,latest with `oras`"
    assert ORAS_INPUT_DIR in process.immutable_input_digests

    result = oras_rule_runner.request(ProcessResult, [dataclasses.replace(process, output_directories=("oci-layout",))])

    layout = {
        content.path: content.content
        for content in oras_rule_runner.request(DigestContents, [result.output_digest])
        if isinstance(content, FileContent)
    }
    index = json.loads(layout["oci-layout/index.json"])
    # In layout mode `oras` keeps the whole reference in the first tag's annotation, so only the tag suffixes compare.
    ref_names = [entry["annotations"]["org.opencontainers.image.ref.name"] for entry in index["manifests"]]
    assert {ref_name.rsplit(":", 1)[-1] for ref_name in ref_names} == {"v1", "latest"}
    assert {entry["digest"] for entry in index["manifests"]} == {index["manifests"][0]["digest"]}
    algorithm, digest = index["manifests"][0]["digest"].split(":")
    manifest = json.loads(layout[f"oci-layout/blobs/{algorithm}/{digest}"])
    assert manifest["artifactType"] == "application/vnd.python.pex.v1"
    assert [layer["annotations"]["org.opencontainers.image.title"] for layer in manifest["layers"]] == [_PEX_PATH]
