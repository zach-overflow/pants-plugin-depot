from collections.abc import Callable
from textwrap import dedent

import pytest

from pants_plugin_developer_utils.testing_utils import rule_runner_factory  # noqa: F401

type TomlFactory = Callable[[str, str, str | None], tuple[str, str]]
"""The type alias for the `pyproject_toml_factory` fixture for dynamic mock `pyproject.toml` generation."""


@pytest.fixture(scope="function")
def pyproject_toml_factory() -> TomlFactory:
    """Factory fixture for dynamic generation of `pyproject.toml` filepaths and contents."""

    def _factory(filepath: str, project_name: str, tool_section: str | None = None) -> tuple[str, str]:
        contents = dedent(
            f"""\
            [project]
            name = "{project_name}"
            version = "0.0.1"
            requires-python = ">=3.12"
            dependencies = ["bar", "alice", "bob", "buffalo>=2.0,<3", "httpx2", "cowsay", ""]
            description = "Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo."
            """
        )
        if tool_section:
            contents += f"\n{tool_section}"
        return (filepath, contents)

    return _factory


@pytest.fixture(scope="function")
def dedicated_pyproject_fmt_config() -> tuple[str, str]:
    """Fixture for creating a mock `pyproject-fmt.toml` file. Config discovery only looks in the build root."""
    return (
        "pyproject-fmt.toml",
        dedent(
            """\
            column_width = 60
            indent = 2
            """
        ),
    )
