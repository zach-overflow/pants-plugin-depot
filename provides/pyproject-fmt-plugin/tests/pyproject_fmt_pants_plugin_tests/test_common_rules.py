from collections.abc import Iterable
from unittest.mock import create_autospec

import pytest
from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.pex import PexRequest, VenvPex
from pants.backend.python.util_rules.pex_requirements import EntireLockfile
from pants.engine.fs import EMPTY_SNAPSHOT
from pants.testutil.rule_runner import QueryRule, RuleRunner, run_rule_with_mocks

from pants_plugin_developer_utils.testing_utils import RuleRunnerFactory
from pyproject_fmt_pants_plugin.goals.common import (
    PyprojectFmtMode,
    RunPyprojectFmtRequest,
    common_partition_pyproject_toml_inputs,
    create_pyproject_fmt_venv_pex,
)
from pyproject_fmt_pants_plugin.subsystem import PyprojectFmt


class TestRunPyprojectFmtRequest:
    """Wrapper for unit tests of `RunPyprojectFmtRequest` methods."""

    @pytest.mark.parametrize(("mode", "expected"), [(PyprojectFmtMode.CHECK, True), (PyprojectFmtMode.FORMAT, False)])
    def test_is_check(self, mode: PyprojectFmtMode, expected: bool) -> None:
        request = RunPyprojectFmtRequest(mode=mode, snapshot=EMPTY_SNAPSHOT)
        assert request.is_check is expected

    @pytest.mark.parametrize(("mode", "expected"), [(PyprojectFmtMode.CHECK, False), (PyprojectFmtMode.FORMAT, True)])
    def test_is_format(self, mode: PyprojectFmtMode, expected: bool) -> None:
        request = RunPyprojectFmtRequest(mode=mode, snapshot=EMPTY_SNAPSHOT)
        assert request.is_format is expected


@pytest.mark.parametrize(
    ("skip", "files", "expected"),
    [
        (False, tuple(), []),
        (False, ("pyproject.toml", "bar/pyproject.toml"), [("bar/pyproject.toml", "pyproject.toml")]),
        (True, tuple(), []),
        (True, ("pyproject.toml", "bar/pyproject.toml"), []),
    ],
)
def test_common_partition_pyproject_toml_inputs(
    skip: bool, files: Iterable[str], expected: list[tuple[str, ...]]
) -> None:
    actual = common_partition_pyproject_toml_inputs(skip=skip, files=files)
    # `Partitions` are not comparable: each single partition holds a distinct `_EmptyMetadata` instance.
    assert [partition.elements for partition in actual] == expected


@pytest.fixture(scope="function")
def pyproject_fmt_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:
    return rule_runner_factory(rules=[*PyprojectFmt.rules(), QueryRule(PyprojectFmt, [])])


def test_create_pyproject_fmt_venv_pex(pyproject_fmt_rule_runner: RuleRunner) -> None:
    pyproject_fmt = pyproject_fmt_rule_runner.request(PyprojectFmt, [])
    expected = create_autospec(VenvPex, instance=True)
    pex_requests: list[PexRequest] = []

    def mock_create_venv_pex(pex_request: PexRequest) -> VenvPex:
        pex_requests.append(pex_request)
        return expected

    # Building the real pex resolves `pyproject-fmt` over the network, so `create_venv_pex` is mocked.
    actual = run_rule_with_mocks(
        create_pyproject_fmt_venv_pex,
        rule_args=[pyproject_fmt],
        mock_calls={"pants.backend.python.util_rules.pex.create_venv_pex": mock_create_venv_pex},
    )

    assert actual is expected
    [pex_request] = pex_requests
    assert pex_request.main == PyprojectFmt.default_main
    assert pex_request.interpreter_constraints == InterpreterConstraints(PyprojectFmt.default_interpreter_constraints)
    assert pex_request.requirements == EntireLockfile(PyprojectFmt.pex_requirements_for_default_lockfile())
