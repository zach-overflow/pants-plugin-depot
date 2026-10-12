import json
import re
from importlib import resources

from vcs_versioning_pants_plugin.subsystem import VcsVersioning

LOCKFILE_PACKAGE = "vcs_versioning_pants_plugin.lockfile_resource"


def _normalize(requirement: str) -> tuple[str, list[str]]:
    """Split a requirement into its name and sorted specifiers, so specifier order does not matter."""
    match = re.fullmatch(r"([A-Za-z0-9_.-]+)(.*)", requirement)
    assert match is not None, requirement
    name, specifiers = match.groups()
    return name, sorted(specifier.strip() for specifier in specifiers.split(","))


def test_options_scope_does_not_shadow_pants_subsystem() -> None:
    assert VcsVersioning.options_scope == "vcs-versioning"


def test_default_lockfile_ships_with_its_metadata_sidecar() -> None:
    package, lockfile = VcsVersioning.default_lockfile_resource
    assert package == LOCKFILE_PACKAGE
    files = resources.files(package)

    assert (files / lockfile).is_file()
    assert (files / f"{lockfile}.metadata").is_file()


def test_default_lockfile_matches_default_requirements() -> None:
    package, lockfile = VcsVersioning.default_lockfile_resource
    metadata = json.loads((resources.files(package) / f"{lockfile}.metadata").read_text())

    assert [_normalize(req) for req in metadata["generated_with_requirements"]] == [
        _normalize(req) for req in VcsVersioning.default_requirements
    ]
    assert metadata["resolve"] == "vcs-versioning"
