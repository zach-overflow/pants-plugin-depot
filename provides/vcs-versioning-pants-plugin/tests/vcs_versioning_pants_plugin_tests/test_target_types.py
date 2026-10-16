import pytest
from pants.engine.addresses import Address
from pants.engine.target import InvalidTargetException

from vcs_versioning_pants_plugin.target_types import (
    DEFAULT_TAG_REGEX,
    ScmVersionDummySourceField,
    ScmVersionFileDummySourceField,
    ScmVersionFileTarget,
    ScmVersionFileTemplateField,
    ScmVersionGenerateToField,
    ScmVersionLocalSchemeField,
    ScmVersionPythonResolveField,
    ScmVersionTagPrefixField,
    ScmVersionTagRegexField,
    ScmVersionTarget,
    ScmVersionTemplateField,
)

ADDRESS = Address("src/pkg", target_name="version")


def test_scm_version_file_defaults() -> None:
    target = ScmVersionFileTarget({"generate_to": "src/pkg/version.txt"}, ADDRESS)

    assert target[ScmVersionGenerateToField].value == "src/pkg/version.txt"
    # The shared codegen reads the base field class; the subclass supplies the default.
    assert target[ScmVersionTemplateField].value == "{version}\n"
    assert isinstance(target[ScmVersionTemplateField], ScmVersionFileTemplateField)
    assert target[ScmVersionTagPrefixField].value is None
    assert target[ScmVersionTagRegexField].value == DEFAULT_TAG_REGEX
    assert target[ScmVersionLocalSchemeField].value is None
    assert target.has_field(ScmVersionFileDummySourceField)
    assert not target.has_field(ScmVersionDummySourceField)
    assert not target.has_field(ScmVersionPythonResolveField)


def test_scm_version_file_values() -> None:
    target = ScmVersionFileTarget(
        {"generate_to": "VERSION", "template": "v{version}", "tag_prefix": "app-v", "local_scheme": "no-local-version"},
        ADDRESS,
    )

    assert target[ScmVersionTemplateField].value == "v{version}"
    assert target[ScmVersionTagPrefixField].value == "app-v"
    assert target[ScmVersionLocalSchemeField].value == "no-local-version"


def test_scm_version_requires_a_template() -> None:
    with pytest.raises(InvalidTargetException, match=r"The `template` field in target src/pkg:version must be defined"):
        ScmVersionTarget({"generate_to": "src/pkg/version.py"}, ADDRESS)
