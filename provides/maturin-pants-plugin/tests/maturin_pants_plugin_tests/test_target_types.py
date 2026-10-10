from pants.engine.target import SourcesField

from maturin_pants_plugin.target_types import (
    CargoTomlField,
    MaturinRepositoriesField,
    MaturinWheelSourcesField,
    MaturinWheelTarget,
    PyProjectTomlField,
    SkipMaturinUploadField,
)
from maturin_pants_plugin_tests.conftest import CRATE_ADDRESS, CRATE_DIR


def test_field_defaults() -> None:
    target = MaturinWheelTarget({}, CRATE_ADDRESS)

    assert target[CargoTomlField].file_path == f"{CRATE_DIR}/Cargo.toml"
    assert target[PyProjectTomlField].file_path == f"{CRATE_DIR}/pyproject.toml"
    assert target[MaturinWheelSourcesField].globs == (
        "Cargo.toml",
        "Cargo.lock",
        "pyproject.toml",
        "build.rs",
        "src/**/*.rs",
        "tests/**/*.rs",
        "python/**",
    )
    assert target[MaturinRepositoriesField].value is None
    assert target[SkipMaturinUploadField].value is False


def test_explicit_field_values() -> None:
    target = MaturinWheelTarget(
        {"cargo_toml": "rust/Cargo.toml", "pyproject_toml": "rust/pyproject.toml", "repositories": ["@pypi"]},
        CRATE_ADDRESS,
    )

    assert target[CargoTomlField].file_path == f"{CRATE_DIR}/rust/Cargo.toml"
    assert target[PyProjectTomlField].file_path == f"{CRATE_DIR}/rust/pyproject.toml"
    assert (
        MaturinWheelTarget({"cargo_toml": "../Cargo.toml"}, CRATE_ADDRESS)[CargoTomlField].file_path
        == "crates/Cargo.toml"
    )
    assert target[MaturinRepositoriesField].value == ("@pypi",)


def test_rust_sources_own_changed_files() -> None:
    """`--changed-since` matches changed files against the first `SourcesField` only, so it must be the rust one."""
    target = MaturinWheelTarget({}, CRATE_ADDRESS)

    assert isinstance(target.get(SourcesField), MaturinWheelSourcesField)
