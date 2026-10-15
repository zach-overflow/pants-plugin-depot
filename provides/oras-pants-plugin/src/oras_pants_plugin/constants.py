from enum import StrEnum, unique
from typing import Final

ALL_DEFAULT_REGISTRIES: Final[str] = "<all default registries>"
"""Placeholder `oci_registries` entry standing for every `[oras].registries` entry marked `default = true`."""


OCI_LAYOUT_INDEX_FILENAME: Final[str] = "index.json"
"""The file of an OCI image layout listing its manifests and their tags."""


@unique
class SandboxDir(StrEnum):
    """Commonly used sandbox directory names during `package` runs on `oci_artifact(s)`."""

    ORAS_INPUT_DIRNAME = "__oras__"
    """Sandbox directory the downloaded `oras` binary is mounted in, out of the way of the artifact's files."""

    OCI_LAYOUT_OUT_DIRNAME = "__oci_layout__"
    """Sandbox directory `oras push` writes the layout to. Prevents collisions with a file of the same name."""
