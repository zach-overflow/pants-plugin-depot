import dataclasses
import json
from textwrap import dedent
from typing import Any

import pytest
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact
from pants.core.target_types import FileTarget
from pants.engine.addresses import Address
from pants.engine.fs import DigestContents, FileContent, Snapshot
from pants.engine.internals.scheduler import ExecutionError
from pants.testutil.rule_runner import RuleRunner

from oras_pants_plugin.constants import SandboxDir
from oras_pants_plugin.goals.package import OCIArtifactPackageFieldSet, construct_oras_push_argv
from oras_pants_plugin_tests.conftest import APP_ADDRESS, APP_DIR, LAYOUT_PATH, FakePackageTarget, make_oci_artifact


def _layout_files(rule_runner: RuleRunner, package: BuiltPackage) -> dict[str, bytes]:
    return {
        content.path: content.content
        for content in rule_runner.request(DigestContents, [package.digest])
        if isinstance(content, FileContent)
    }


def _manifest(layout: dict[str, bytes], layout_path: str) -> tuple[str, dict[str, Any]]:
    """The single manifest of the layout at `layout_path`, as `(digest, manifest)`, asserting every tag shares it."""
    index = json.loads(layout[f"{layout_path}/index.json"])
    digests = {entry["digest"] for entry in index["manifests"]}
    assert len(digests) == 1
    digest = digests.pop()
    algorithm, hex_digest = digest.split(":")
    return digest, json.loads(layout[f"{layout_path}/blobs/{algorithm}/{hex_digest}"])


def test_field_set_applies_to_oci_artifact_targets_only() -> None:
    artifact = make_oci_artifact()
    fake = FakePackageTarget({"content": "x"}, Address(APP_DIR, target_name="pkg"))
    readme = FileTarget({"source": "README.md"}, Address(APP_DIR, target_name="readme"))

    assert OCIArtifactPackageFieldSet.is_applicable(artifact)
    assert not OCIArtifactPackageFieldSet.is_applicable(fake)
    assert not OCIArtifactPackageFieldSet.is_applicable(readme)
    field_set = OCIArtifactPackageFieldSet.create(artifact)
    assert field_set.output_path.value_or_default(file_ending=None) == LAYOUT_PATH


def test_construct_oras_push_argv() -> None:
    """A `:` in a file path is escaped from `oras`' `<file>:<type>` syntax; no tags leaves the layout untagged."""
    assert construct_oras_push_argv(
        SandboxDir.OCI_LAYOUT_OUT_DIRNAME,
        ("v1", "latest"),
        "application/vnd.python.pex.v1",
        ("src.app/app.pex", "dist/app:v1"),
        "linux/amd64",
    ) == (
        "push",
        "--no-tty",
        "--oci-layout",
        "--artifact-type",
        "application/vnd.python.pex.v1",
        "--artifact-platform",
        "linux/amd64",
        f"{SandboxDir.OCI_LAYOUT_OUT_DIRNAME}:v1,latest",
        "src.app/app.pex",
        "dist/app:v1:",
    )
    assert construct_oras_push_argv(SandboxDir.OCI_LAYOUT_OUT_DIRNAME, (), None, ("a.txt",)) == (
        "push",
        "--no-tty",
        "--oci-layout",
        SandboxDir.OCI_LAYOUT_OUT_DIRNAME,
        "a.txt",
    )


def test_package_oci_artifact(oras_rule_runner: RuleRunner) -> None:
    """Runs the real `oras` (downloaded): every `packages` output is a layer of one manifest, tagged with every tag."""
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": dedent(
                """\
                fake_package(name="cli", content="cli")
                fake_package(name="lib", content="lib")
                file(name="version", source="VERSION")
                oci_artifact(
                    name="app",
                    packages=[":cli", ":lib"],
                    oci_tags=["v1", "latest"],
                    oci_tag_files=[":version"],
                    oci_artifact_type="application/vnd.me.app.v1",
                    oci_artifact_platform="linux/amd64",
                )
                """
            ),
            f"{APP_DIR}/VERSION": "1.2.3\n",
        }
    )
    field_set = OCIArtifactPackageFieldSet.create(oras_rule_runner.get_target(APP_ADDRESS))

    package = oras_rule_runner.request(BuiltPackage, [field_set])

    layout = _layout_files(oras_rule_runner, package)
    digest, manifest = _manifest(layout, LAYOUT_PATH)
    assert all(path.startswith(f"{LAYOUT_PATH}/") for path in layout)
    assert f"{LAYOUT_PATH}/ingest" not in oras_rule_runner.request(Snapshot, [package.digest]).dirs
    assert layout[f"{LAYOUT_PATH}/oci-layout"] == b'{"imageLayoutVersion":"1.0.0"}'
    index = json.loads(layout[f"{LAYOUT_PATH}/index.json"])
    # `oras` tags concurrently, so the index order varies.
    assert {entry["annotations"]["org.opencontainers.image.ref.name"] for entry in index["manifests"]} == {
        "v1",
        "latest",
        "1.2.3",
    }
    assert manifest["artifactType"] == "application/vnd.me.app.v1"
    # `--artifact-platform` makes `oras` record the platform in an image config instead of the empty config.
    assert manifest["config"]["mediaType"] == "application/vnd.oci.image.config.v1+json"
    assert json.loads(layout[f"{LAYOUT_PATH}/blobs/{manifest['config']['digest'].replace(':', '/')}"]) == {
        "os": "linux",
        "architecture": "amd64",
    }
    assert [layer["annotations"]["org.opencontainers.image.title"] for layer in manifest["layers"]] == [
        "src.app/cli.txt",
        "src.app/lib.txt",
    ]
    assert all(f"{LAYOUT_PATH}/blobs/{layer['digest'].replace(':', '/')}" in layout for layer in manifest["layers"])
    assert len(package.artifacts) == 1
    artifact = package.artifacts[0]
    assert artifact.relpath == LAYOUT_PATH
    assert artifact.extra_log_lines == (
        f"  OCI artifact {LAYOUT_PATH}:v1,latest,1.2.3 ({digest})",
        "  platform: linux/amd64",
        "  layer: src.app/cli.txt",
        "  layer: src.app/lib.txt",
    )


def test_package_oci_artifact_untagged_with_custom_output_path(oras_rule_runner: RuleRunner) -> None:
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": dedent(
                """\
                fake_package(name="cli", content="cli")
                oci_artifact(name="app", packages=[":cli"], oci_tags=[], output_path="artifacts/app-layout")
                """
            )
        }
    )
    field_set = OCIArtifactPackageFieldSet.create(oras_rule_runner.get_target(APP_ADDRESS))

    package = oras_rule_runner.request(BuiltPackage, [field_set])

    layout = _layout_files(oras_rule_runner, package)
    digest, manifest = _manifest(layout, "artifacts/app-layout")
    index = json.loads(layout["artifacts/app-layout/index.json"])
    assert "org.opencontainers.image.ref.name" not in index["manifests"][0].get("annotations", {})
    assert manifest["artifactType"] == "application/vnd.unknown.artifact.v1"
    assert manifest["config"]["mediaType"] == "application/vnd.oci.empty.v1+json"
    assert package.artifacts == (
        BuiltPackageArtifact(
            "artifacts/app-layout",
            extra_log_lines=(f"  OCI artifact artifacts/app-layout ({digest})", "  layer: src.app/cli.txt"),
        ),
    )


def test_package_oci_artifact_without_packageable_targets_fails(oras_rule_runner: RuleRunner) -> None:
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": dedent(
                """\
                file(name="readme", source="README.md")
                oci_artifact(name="app", packages=[":readme"])
                """
            ),
            f"{APP_DIR}/README.md": "",
        }
    )
    field_set = OCIArtifactPackageFieldSet.create(oras_rule_runner.get_target(APP_ADDRESS))

    with pytest.raises(ExecutionError, match=f"`packages` field of target {APP_ADDRESS} produced no files"):
        oras_rule_runner.request(BuiltPackage, [field_set])


def test_packaged_layout_is_reproducible_in_a_session(oras_rule_runner: RuleRunner) -> None:
    """The same inputs give the same `BuiltPackage` back (the engine memoizes the `oras push`)."""
    oras_rule_runner.write_files(
        {f"{APP_DIR}/BUILD": 'fake_package(name="cli", content="cli")\noci_artifact(name="app", packages=[":cli"])\n'}
    )
    field_set = OCIArtifactPackageFieldSet.create(oras_rule_runner.get_target(APP_ADDRESS))

    first = oras_rule_runner.request(BuiltPackage, [field_set])
    second = oras_rule_runner.request(BuiltPackage, [dataclasses.replace(field_set)])

    assert first == second
