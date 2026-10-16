from textwrap import dedent
from typing import Any

import pytest
from pants.engine.fs import DigestContents, FileContent
from pants.engine.internals.scheduler import ExecutionError
from pants.testutil.rule_runner import RuleRunner, run_rule_with_mocks

from oras_pants_plugin.goals.common import (
    OCIArtifactTags,
    OCIArtifactTagsRequest,
    oci_reference,
    oras_file_arg,
    resolve_oci_artifact_tags,
    tag_lines,
)
from oras_pants_plugin.goals.package import OCIArtifactPackageFieldSet
from oras_pants_plugin_tests.conftest import APP_ADDRESS, APP_DIR, make_oci_artifact


def _tags_request(**field_values: Any) -> OCIArtifactTagsRequest:
    return OCIArtifactTagsRequest.from_field_set(OCIArtifactPackageFieldSet.create(make_oci_artifact(**field_values)))


def _tags_request_from_build(rule_runner: RuleRunner, build: str, **files: str) -> OCIArtifactTagsRequest:
    rule_runner.write_files(
        {f"{APP_DIR}/BUILD": dedent(build), **{f"{APP_DIR}/{name}": c for name, c in files.items()}}
    )
    return OCIArtifactTagsRequest.from_field_set(OCIArtifactPackageFieldSet.create(rule_runner.get_target(APP_ADDRESS)))


def test_oci_reference() -> None:
    assert oci_reference("ghcr.io/org/app", ("v1", "latest")) == "ghcr.io/org/app:v1,latest"
    assert oci_reference("ghcr.io/org/app", ()) == "ghcr.io/org/app"


def test_oras_file_arg() -> None:
    assert oras_file_arg("src.app/app.pex") == "src.app/app.pex"
    assert oras_file_arg("dist/app:v1") == "dist/app:v1:"


def test_tag_lines_skips_blank_lines_and_surrounding_whitespace() -> None:
    contents = DigestContents(
        [FileContent("a/VERSION", b"  1.2.3 \n\n"), FileContent("b/tags.txt", b"\r\nstable\r\n\tlatest")]
    )

    assert tag_lines(contents) == ("1.2.3", "stable", "latest")


@pytest.mark.parametrize(
    ("oci_tags", "expected"), [([], ()), (["v1", "latest"], ("v1", "latest")), (["v1", "v1"], ("v1",))]
)
def test_resolve_tags_without_tag_files_needs_no_engine(oci_tags: list[str], expected: tuple[str, ...]) -> None:
    actual = run_rule_with_mocks(resolve_oci_artifact_tags, rule_args=[_tags_request(oci_tags=oci_tags)])

    assert actual == OCIArtifactTags(expected)


def test_resolve_tags_appends_the_lines_of_file_and_resource_targets(oras_rule_runner: RuleRunner) -> None:
    request = _tags_request_from_build(
        oras_rule_runner,
        """\
        fake_package(name="pkg", content="pkg")
        file(name="version", source="VERSION")
        resource(name="channels", source="channels.txt")
        oci_artifact(name="app", packages=[":pkg"], oci_tags=["latest"], oci_tag_files=[":version", ":channels"])
        """,
        VERSION="1.2.3\n",
        **{"channels.txt": "stable\n\nlatest\n"},
    )

    assert oras_rule_runner.request(OCIArtifactTags, [request]) == OCIArtifactTags(("latest", "1.2.3", "stable"))


def test_resolve_tags_rejects_a_target_without_file_sources(oras_rule_runner: RuleRunner) -> None:
    request = _tags_request_from_build(
        oras_rule_runner,
        """\
        fake_package(name="pkg", content="pkg")
        oci_artifact(name="app", packages=[":pkg"], oci_tag_files=[":pkg"])
        """,
    )

    with pytest.raises(
        ExecutionError, match=r"lists src/app:pkg, a `fake_package` target without `file` or `resource`"
    ):
        oras_rule_runner.request(OCIArtifactTags, [request])


def test_resolve_tags_rejects_a_tag_file_without_tags(oras_rule_runner: RuleRunner) -> None:
    request = _tags_request_from_build(
        oras_rule_runner,
        """\
        fake_package(name="pkg", content="pkg")
        file(name="version", source="VERSION")
        oci_artifact(name="app", packages=[":pkg"], oci_tag_files=[":version"])
        """,
        VERSION="\n  \n",
    )

    with pytest.raises(ExecutionError, match=r"lists src/app:version, whose files hold no tags"):
        oras_rule_runner.request(OCIArtifactTags, [request])
