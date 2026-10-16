from pants.core.goals.package import OutputPathField

from oras_pants_plugin.constants import ALL_DEFAULT_REGISTRIES
from oras_pants_plugin.target_types import (
    OCIArtifact,
    OCIArtifactPackagesField,
    OCIArtifactPlatformField,
    OCIArtifactTypeField,
    OCIRegistriesField,
    OCIRepositoryField,
    OCITagFilesField,
    OCITagsField,
    SkipOCIPublishField,
    target_types,
)
from oras_pants_plugin_tests.conftest import make_oci_artifact


def test_target_types() -> None:
    assert tuple(target_types()) == (OCIArtifact,)


def test_field_defaults() -> None:
    target = make_oci_artifact()

    assert target[OCIArtifactPackagesField].value == (":pkg",)
    assert target[OutputPathField].value == OutputPathField.DEFAULT
    assert target[OCIArtifactTypeField].value is None
    assert target[OCIArtifactPlatformField].value is None
    assert target[OCITagsField].value == ("latest",)
    assert target[OCITagFilesField].value is None
    assert target[OCIRegistriesField].value == (ALL_DEFAULT_REGISTRIES,)
    assert target[OCIRepositoryField].value is None
    assert target[SkipOCIPublishField].value is False


def test_field_values() -> None:
    target = make_oci_artifact(
        oci_artifact_type="application/vnd.python.pex.v1",
        oci_artifact_platform="linux/arm64/v8",
        oci_tags=[],
        oci_tag_files=[":version", "src/other:tags"],
        oci_registries=["@prod", "localhost:5000"],
        oci_repository="my-org/my-app",
        skip_oras=True,
    )

    assert target[OCIArtifactTypeField].value == "application/vnd.python.pex.v1"
    assert target[OCIArtifactPlatformField].value == "linux/arm64/v8"
    assert target[OCITagsField].value == ()
    assert target[OCITagFilesField].value == (":version", "src/other:tags")
    assert target[OCIRegistriesField].value == ("@prod", "localhost:5000")
    assert target[OCIRepositoryField].value == "my-org/my-app"
    assert target[SkipOCIPublishField].value is True
