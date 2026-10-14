from textwrap import dedent

import pytest
from pants.backend.python.target_types import PexBinariesGeneratorTarget, PexBinary
from pants.engine.addresses import Address
from pants.engine.target import InvalidFieldException
from pants.engine.unions import UnionRule
from pants.testutil.rule_runner import RuleRunner

from oras_pants_plugin import fields
from oras_pants_plugin.fields import (
    PEX_BINARY_PLUGIN_FIELDS,
    OrasRepositoriesField,
    OrasTagsField,
    PexOciMediaType,
    SkipOrasPublishField,
    is_untagged_reference,
)
from oras_pants_plugin_tests.conftest import APP_ADDRESS, APP_DIR, make_pex_binary


def test_rules_register_every_field_on_both_pex_targets() -> None:
    assert set(fields.rules()) == {
        *(UnionRule(PexBinary.PluginField, field) for field in PEX_BINARY_PLUGIN_FIELDS),
        *(UnionRule(PexBinariesGeneratorTarget.MovedPluginField, field) for field in PEX_BINARY_PLUGIN_FIELDS),
    }


@pytest.mark.parametrize(
    "reference", ["ghcr.io/my-org/my-app", "localhost:5000/my-app", "registry.example.com:443/team/sub/app"]
)
def test_is_untagged_reference_accepts_registry_and_repository(reference: str) -> None:
    assert is_untagged_reference(reference)


@pytest.mark.parametrize(
    "reference",
    [
        "ghcr.io/my-org/my-app:v1",
        "ghcr.io/my-org/my-app@sha256:0123",
        "localhost:5000",
        "my-app",
        "ghcr.io/",
        "/my-app",
        "",
    ],
)
def test_is_untagged_reference_rejects_tags_digests_and_bare_names(reference: str) -> None:
    assert not is_untagged_reference(reference)


def test_oci_repositories_rejects_tagged_references() -> None:
    with pytest.raises(InvalidFieldException, match=r"oci_repositories.*\['ghcr.io/my-org/my-app:v1'\]"):
        OrasRepositoriesField(["ghcr.io/my-org/my-app", "ghcr.io/my-org/my-app:v1"], APP_ADDRESS)


def test_field_defaults() -> None:
    target = make_pex_binary()

    assert target[OrasRepositoriesField].value is None
    assert target[OrasTagsField].value == ("latest",)
    assert target[PexOciMediaType].value == "application/vnd.python.pex.v1"
    assert target[SkipOrasPublishField].value is False


def test_field_values() -> None:
    target = make_pex_binary(
        oci_repositories=["ghcr.io/my-org/my-app"], oci_tags=[], oci_media_type="application/vnd.me.app", skip_oras=True
    )

    assert target[OrasRepositoriesField].value == ("ghcr.io/my-org/my-app",)
    assert target[OrasTagsField].value == ()
    assert target[PexOciMediaType].value == "application/vnd.me.app"
    assert target[SkipOrasPublishField].value is True


def test_pex_binaries_moves_the_fields_onto_generated_targets(oras_rule_runner: RuleRunner) -> None:
    oras_rule_runner.write_files(
        {
            f"{APP_DIR}/BUILD": dedent(
                """\
                pex_binaries(
                    name="bins",
                    entry_points=["main.py", "tool.py"],
                    oci_repositories=["ghcr.io/my-org/my-app"],
                    oci_tags=["v1"],
                    overrides={"tool.py": {"skip_oras": True, "oci_media_type": "application/vnd.me.tool"}},
                )
                """
            ),
            f"{APP_DIR}/main.py": "",
            f"{APP_DIR}/tool.py": "",
        }
    )

    main = oras_rule_runner.get_target(Address(APP_DIR, target_name="bins", generated_name="main.py"))
    tool = oras_rule_runner.get_target(Address(APP_DIR, target_name="bins", generated_name="tool.py"))

    assert main[OrasRepositoriesField].value == tool[OrasRepositoriesField].value == ("ghcr.io/my-org/my-app",)
    assert main[OrasTagsField].value == tool[OrasTagsField].value == ("v1",)
    assert main[PexOciMediaType].value == "application/vnd.python.pex.v1"
    assert tool[PexOciMediaType].value == "application/vnd.me.tool"
    assert main[SkipOrasPublishField].value is False
    assert tool[SkipOrasPublishField].value is True
