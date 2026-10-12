from textwrap import dedent

import pytest
from pants.backend.python.util_rules import pex
from pants.core.goals.fix import FixResult
from pants.core.util_rules import config_files
from pants.engine.fs import Digest, DigestContents, PathGlobs, Snapshot
from pants.testutil.rule_runner import QueryRule, RuleRunner

from pants_plugin_developer_utils.testing_utils import RuleRunnerFactory
from pyproject_fmt_pants_plugin.goals import common, fmt
from pyproject_fmt_pants_plugin.goals.fmt import PyprojectFmtRequest
from pyproject_fmt_pants_plugin_tests.conftest import TomlFactory


@pytest.fixture(scope="function")
def fmt_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:
    """Integration `RuleRunner`: builds the real `pyproject-fmt` pex (network) and runs it on the written files."""
    rule_runner = rule_runner_factory(
        rules=[
            *fmt.rules(),
            *common.rules(),
            *pex.rules(),
            *config_files.rules(),
            QueryRule(FixResult, [PyprojectFmtRequest.Batch]),
            QueryRule(Snapshot, [PathGlobs]),
            QueryRule(DigestContents, [Digest]),
        ]
    )
    # Mirror `[python].pip_version` in `pants.toml`: Pants' default pip predates CPython 3.14.
    rule_runner.set_options(["--python-pip-version=latest"], env_inherit={"PATH", "PYENV_ROOT", "HOME"})
    return rule_runner


@pytest.fixture(scope="function")
def pyproject_contents_with_fmt_section() -> str:
    """Fake `pyproject.toml` contents containing a `[tool.pyproject-fmt]` section."""
    return dedent(
        """\
        [project]
        name = "with-fmt-section"
        version = "0.0.1"
        requires-python = ">=3.12"
        dependencies = ["bar", "alice", "bob", "buffalo>=2.0,<3", "httpx2", "cowsay", ""]
        description = "Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo."

        [tool.pyproject-fmt]
        column_width = 120
        max_supported_python = "3.15"
        """
    )


_FORMATTED_WITH_DEFAULTS = dedent(
    """\
    [project]
    name = "{name}"
    version = "0.0.1"
    description = "Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo."
    requires-python = ">=3.12"
    classifiers = [
      "Programming Language :: Python :: 3 :: Only",
      "Programming Language :: Python :: 3.12",
      "Programming Language :: Python :: 3.13",
      "Programming Language :: Python :: 3.14",
      "Programming Language :: Python :: 3.15",
    ]
    dependencies = [ "", "alice", "bar", "bob", "buffalo>=2,<3", "cowsay", "httpx2" ]
    """
)
"""`pyproject_toml_factory` output formatted with `pyproject-fmt` defaults (`column_width = 120`)."""

_FORMATTED_WITH_STANDALONE_CONFIG = dedent(
    """\
    [project]
    name = "{name}"
    version = "0.0.1"
    description = \"\"\"\\
      Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo \\
      buffalo.\\
      \"\"\"
    requires-python = ">=3.12"
    classifiers = [
      "Programming Language :: Python :: 3 :: Only",
      "Programming Language :: Python :: 3.12",
      "Programming Language :: Python :: 3.13",
      "Programming Language :: Python :: 3.14",
      "Programming Language :: Python :: 3.15",
    ]
    dependencies = [
      "",
      "alice",
      "bar",
      "bob",
      "buffalo>=2,<3",
      "cowsay",
      "httpx2",
    ]
    """
)
"""`pyproject_toml_factory` output formatted with the `dedicated_pyproject_fmt_config` (`column_width = 60`)."""


def _add_mock_file(mock_files: dict[str, str], entry: tuple[str, str]) -> None:
    filepath, contents = entry
    mock_files[filepath] = contents


@pytest.mark.parametrize("has_standalone_config", [False, True])
@pytest.mark.parametrize("has_nested_project", [False, True])
def test_run_pyproject_fmt_formatting_no_tool_section(
    fmt_rule_runner: RuleRunner,
    dedicated_pyproject_fmt_config: tuple[str, str],
    pyproject_toml_factory: TomlFactory,
    has_standalone_config: bool,
    has_nested_project: bool,
) -> None:
    """Validates the `pants fmt` runs `pyproject-fmt` formatting, without any `[tool.pyproject-fmt]` sections."""
    projects = {"pyproject.toml": "root-project"}
    if has_nested_project:
        projects["nested/thing/pyproject.toml"] = "nested-project"

    src_files: dict[str, str] = dict()
    if has_standalone_config:
        _add_mock_file(mock_files=src_files, entry=dedicated_pyproject_fmt_config)
    for filepath, project_name in projects.items():
        _add_mock_file(mock_files=src_files, entry=pyproject_toml_factory(filepath, project_name, None))
    fmt_rule_runner.write_files(src_files)

    snapshot = fmt_rule_runner.request(Snapshot, [PathGlobs(["**/pyproject.toml"])])
    batch = PyprojectFmtRequest.Batch("", snapshot.files, partition_metadata=None, snapshot=snapshot)
    result = fmt_rule_runner.request(FixResult, [batch])

    assert result.did_change
    assert result.input == snapshot
    template = _FORMATTED_WITH_STANDALONE_CONFIG if has_standalone_config else _FORMATTED_WITH_DEFAULTS
    output = fmt_rule_runner.request(DigestContents, [result.output.digest])
    assert {file.path: file.content.decode() for file in output} == {
        filepath: template.format(name=project_name) for filepath, project_name in projects.items()
    }
