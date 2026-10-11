import os

from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    AsyncFieldMixin,
    BoolField,
    Dependencies,
    MultipleSourcesField,
    StringField,
    StringSequenceField,
    Target,
    generate_multiple_sources_field_help_message,
)
from pants.util.strutil import help_text

from pants_plugin_developer_utils import CollectedTargetTypes


class MaturinWheelSourcesField(MultipleSourcesField):
    """Every file `maturin build` needs from the crate directory: manifests, rust sources and the python shim package."""

    default = ("Cargo.toml", "Cargo.lock", "pyproject.toml", "build.rs", "src/**/*.rs", "tests/**/*.rs", "python/**")
    uses_source_roots = False
    help = generate_multiple_sources_field_help_message(
        "Example: `sources=['Cargo.toml', 'Cargo.lock', 'pyproject.toml', 'src/**/*.rs', 'python/**/*.py']`"
    )


class MaturinManifestField(StringField, AsyncFieldMixin):
    """
    Base class of the fields naming the crate's `Cargo.toml` and the wheel's `pyproject.toml`.
    A plain string rather than a `SingleSourceField`: `pants --changed-since` only consults a target's first
    `SourcesField`, which must stay `sources` so that edits to rust files mark the target as changed.
    `AsyncFieldMixin` keeps the owning address around, like `OutputPathField` does.
    """

    value: str

    @property
    def file_path(self) -> str:
        """The repo-relative path of the manifest, like `SingleSourceField.file_path`."""
        return os.path.normpath(os.path.join(self.address.spec_path, self.value))


class CargoTomlField(MaturinManifestField):
    """Field naming the `Cargo.toml` of the rust crate packaged in the wheel."""

    alias = "cargo_toml"
    default = "Cargo.toml"
    help = help_text(
        """
        Path of the crate's `Cargo.toml`, relative to the BUILD file. Passed to `maturin build` as `--manifest-path`.
        The file MUST be matched by `sources`; the default globs include it.
        """
    )


class PyProjectTomlField(MaturinManifestField):
    """Field naming the `pyproject.toml` of the wheel project."""

    alias = "pyproject_toml"
    default = "pyproject.toml"
    help = help_text(
        """
        Path of the wheel project's `pyproject.toml`, relative to the BUILD file. It MUST be in the same directory
        as `cargo_toml`, which is where `maturin` looks for it, and MUST be matched by `sources`; the default globs
        include it.
        """
    )


class MaturinWheelDependenciesField(Dependencies):
    """Targets whose files `maturin build` needs in its sandbox."""

    help = help_text(
        """
        Addresses of targets whose files `maturin build` needs, e.g. `file` targets for a README or LICENSE
        referenced from `pyproject.toml`, or `python_sources` for the python package of a mixed rust/python
        project. Files are placed in the sandbox at their repo-relative paths.
        """
    )


class MaturinRepositoriesField(StringSequenceField):
    """Registries that `maturin upload` publishes the wheels to."""

    alias = "repositories"
    help = help_text(
        """
        List of registries to upload the wheels to with `maturin upload` during `pants publish`.

        Entries prefixed with `@` name a repository section of your `.pypirc`, such as `@pypi` or `@testpypi`,
        and are passed as `--repository`. Any other entry is passed verbatim as `--repository-url`.

        Leave unset to skip this target during `pants publish`.
        """
    )


class SkipMaturinUploadField(BoolField):
    """Opt a `maturin_wheel` target out of `pants publish`."""

    alias = "skip_maturin_upload"
    default = False
    help = "If true, don't upload this target's wheels with `maturin upload` during `pants publish`."


class MaturinWheelTarget(Target):
    """Similar to pantsbuilds' builtin `python_distribution` target, but for a maturin build backend."""

    alias = "maturin_wheel"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        MaturinWheelSourcesField,
        CargoTomlField,
        PyProjectTomlField,
        MaturinWheelDependenciesField,
        MaturinRepositoriesField,
        SkipMaturinUploadField,
    )
    help = help_text(
        """
        A rust crate packaged into a Python wheel with `maturin`.

        Similar to pantsbuilds' `python_distribution` target, but specialized for the maturin build backend rather
        than setuptools, and only producing `*.whl` outputs. `pants package` runs `maturin build` and writes the
        wheels to `dist/`. `pants publish` runs `maturin upload` against each entry of `repositories`.

        `pyproject.toml` MUST sit beside `Cargo.toml`. Everything the build needs comes from `sources` and
        `dependencies`.

        See also: https://www.maturin.rs/index.html
        """
    )


def target_types() -> CollectedTargetTypes:
    return tuple([MaturinWheelTarget])
