from collections.abc import Iterable
from unittest.mock import create_autospec

import pytest
from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.pex import PexRequest, VenvPex
from pants.backend.python.util_rules.pex_requirements import EntireLockfile
from pants.testutil.rule_runner import QueryRule, RuleRunner, run_rule_with_mocks

from pants_plugin_developer_utils.testing_utils import RuleRunnerFactory
from pyproject_fmt_pants_plugin.goals.common import (
    common_partition_pyproject_toml_inputs,
    create_pyproject_fmt_venv_pex,
    get_pyproject_fmt_argv,
)
from pyproject_fmt_pants_plugin.subsystem import PyprojectFmt


@pytest.mark.parametrize(
    ("skip", "files", "expected"),
    [
        (False, (), []),
        (False, ("pyproject.toml", "bar/pyproject.toml"), [("bar/pyproject.toml", "pyproject.toml")]),
        (True, (), []),
        (True, ("pyproject.toml", "bar/pyproject.toml"), []),
    ],
)
def test_common_partition_pyproject_toml_inputs(
    *, skip: bool, files: Iterable[str], expected: list[tuple[str, ...]]
) -> None:
    actual = common_partition_pyproject_toml_inputs(skip=skip, files=files)
    # `Partitions` are not comparable: each single partition holds a distinct `_EmptyMetadata` instance.
    assert [partition.elements for partition in actual] == expected


@pytest.mark.parametrize(
    ("extra_args", "shared_config_filepath", "expected"),
    [
        ((), None, ()),
        ((), "pyproject-fmt.toml", ("--config", "pyproject-fmt.toml")),
        (("--column-width=60", "--indent=4"), None, ("--column-width=60", "--indent=4")),
        (
            ("--column-width=60",),
            "conf/pyproject-fmt.toml",
            ("--config", "conf/pyproject-fmt.toml", "--column-width=60"),
        ),
    ],
)
def test_get_pyproject_fmt_argv(
    extra_args: tuple[str, ...], shared_config_filepath: str | None, expected: tuple[str, ...]
) -> None:
    assert get_pyproject_fmt_argv(extra_args=extra_args, shared_config_filepath=shared_config_filepath) == expected


@pytest.fixture(scope="function")
def pyproject_fmt_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:
    return rule_runner_factory(rules=[*PyprojectFmt.rules(), QueryRule(PyprojectFmt, [])])


def test_create_pyproject_fmt_venv_pex(pyproject_fmt_rule_runner: RuleRunner) -> None:
    pyproject_fmt = pyproject_fmt_rule_runner.request(PyprojectFmt, [])
    expected: VenvPex = create_autospec(VenvPex, instance=True)
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
