from typing import Any
from unittest.mock import create_autospec

import pytest
from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.pex import PexRequest, VenvPex, VenvPexProcess
from pants.backend.python.util_rules.pex_requirements import EntireLockfile
from pants.engine.env_vars import EnvironmentVars, EnvironmentVarsRequest
from pants.engine.process import Process, ProcessCacheScope
from pants.testutil.rule_runner import RuleRunner, engine_error, run_rule_with_mocks

from maturin_pants_plugin.goals.maturin_common import (
    MATURIN_CARGO_TARGET_CACHE,
    MATURIN_CARGO_TARGET_CACHE_PATH,
    MATURIN_WHEELS_OUT_DIR,
    InvalidMaturinWheelError,
    MaturinFieldSet,
    MaturinProcessRequest,
    MaturinSources,
    construct_maturin_build_argv,
    construct_maturin_upload_argv,
    create_maturin_venv_pex,
    setup_maturin_process,
)
from maturin_pants_plugin.subsystem import Maturin
from maturin_pants_plugin_tests.conftest import CRATE_ADDRESS, CRATE_DIR, make_maturin

_BUILD_ARGV_PREFIX = (
    "build",
    "--out",
    MATURIN_WHEELS_OUT_DIR,
    "--target-dir",
    MATURIN_CARGO_TARGET_CACHE_PATH,
    "--manifest-path",
    f"{CRATE_DIR}/Cargo.toml",
)


@pytest.mark.parametrize(
    ("overrides", "expected_suffix"),
    [
        (
            {},
            (
                "--bindings",
                "pyo3",
                "--compatibility",
                "pypi",
                "--interpreter",
                "python3.12",
                "--interpreter",
                "python3.13",
                "--interpreter",
                "python3.14",
                "--release",
            ),
        ),
        # An empty `interpreter` list omits the flag entirely instead of passing a bare `--interpreter`.
        ({"interpreter": []}, ("--bindings", "pyo3", "--compatibility", "pypi", "--release")),
        (
            {"bindings": "bin", "compatibility": "manylinux2014", "interpreter": ["python3.14"], "jobs": 4},
            (
                "--bindings",
                "bin",
                "--compatibility",
                "manylinux2014",
                "--interpreter",
                "python3.14",
                "--jobs",
                "4",
                "--release",
            ),
        ),
        (
            {"interpreter": [], "profile_guided_optimization": True, "release": False},
            ("--bindings", "pyo3", "--compatibility", "pypi", "--pgo"),
        ),
    ],
)
def test_construct_maturin_build_argv(overrides: dict[str, Any], expected_suffix: tuple[str, ...]) -> None:
    actual = construct_maturin_build_argv(make_maturin(**overrides), f"{CRATE_DIR}/Cargo.toml")

    assert actual == (*_BUILD_ARGV_PREFIX, *expected_suffix)


@pytest.mark.parametrize(
    ("repository", "skip_existing", "expected"),
    [
        ("@pypi", False, ("upload", "--non-interactive", "--repository", "pypi", "a.whl", "b.whl")),
        (
            "https://upload.example.com/legacy/",
            True,
            (
                "upload",
                "--non-interactive",
                "--repository-url",
                "https://upload.example.com/legacy/",
                "--skip-existing",
                "a.whl",
                "b.whl",
            ),
        ),
    ],
)
def test_construct_maturin_upload_argv(*, repository: str, skip_existing: bool, expected: tuple[str, ...]) -> None:
    actual = construct_maturin_upload_argv(make_maturin(skip_existing=skip_existing), repository, ("a.whl", "b.whl"))

    assert actual == expected


def test_get_maturin_sources(maturin_rule_runner: RuleRunner, bin_crate_files: dict[str, str]) -> None:
    """The sandbox holds the crate's own files plus the files of its dependencies, at repo-relative paths."""
    maturin_rule_runner.write_files(bin_crate_files)
    target = maturin_rule_runner.get_target(CRATE_ADDRESS)

    actual = maturin_rule_runner.request(MaturinSources, [MaturinFieldSet.create(target)])

    assert actual.snapshot.files == (
        f"{CRATE_DIR}/Cargo.lock",
        f"{CRATE_DIR}/Cargo.toml",
        f"{CRATE_DIR}/README.md",
        f"{CRATE_DIR}/pyproject.toml",
        f"{CRATE_DIR}/src/main.rs",
    )


def test_get_maturin_sources_requires_the_manifests_in_sources(
    maturin_rule_runner: RuleRunner, bin_crate_files: dict[str, str]
) -> None:
    bin_crate_files[f"{CRATE_DIR}/BUILD"] = 'maturin_wheel(name="whl", sources=["src/**/*.rs"])\n'
    maturin_rule_runner.write_files(bin_crate_files)
    target = maturin_rule_runner.get_target(CRATE_ADDRESS)

    with engine_error(InvalidMaturinWheelError, contains=f"{CRATE_DIR}/Cargo.toml, {CRATE_DIR}/pyproject.toml"):
        maturin_rule_runner.request(MaturinSources, [MaturinFieldSet.create(target)])


def test_get_maturin_sources_requires_pyproject_beside_cargo(
    maturin_rule_runner: RuleRunner, bin_crate_files: dict[str, str]
) -> None:
    bin_crate_files[f"{CRATE_DIR}/BUILD"] = 'maturin_wheel(name="whl", pyproject_toml="../pyproject.toml")\n'
    maturin_rule_runner.write_files(bin_crate_files)
    target = maturin_rule_runner.get_target(CRATE_ADDRESS)

    with engine_error(InvalidMaturinWheelError, contains="must be in the same directory"):
        maturin_rule_runner.request(MaturinSources, [MaturinFieldSet.create(target)])


def test_create_maturin_venv_pex(maturin_rule_runner: RuleRunner) -> None:
    maturin = maturin_rule_runner.request(Maturin, [])
    expected: VenvPex = create_autospec(VenvPex, instance=True)
    pex_requests: list[PexRequest] = []

    def mock_create_venv_pex(pex_request: PexRequest) -> VenvPex:
        pex_requests.append(pex_request)
        return expected

    # Building the real pex resolves `maturin` over the network, so `create_venv_pex` is mocked.
    actual = run_rule_with_mocks(
        create_maturin_venv_pex,
        rule_args=[maturin],
        mock_calls={"pants.backend.python.util_rules.pex.create_venv_pex": mock_create_venv_pex},
    )

    assert actual is expected
    [pex_request] = pex_requests
    assert pex_request.main == Maturin.default_main
    assert pex_request.requirements == EntireLockfile(Maturin.pex_requirements_for_default_lockfile())
    assert pex_request.interpreter_constraints == InterpreterConstraints(Maturin.default_interpreter_constraints)


def test_setup_maturin_process() -> None:
    maturin = make_maturin(extra_env_vars=["RUSTFLAGS=-C target-cpu=native", "CARGO_NET_OFFLINE"])
    request = MaturinProcessRequest(
        argv=("build",),
        description="build it",
        output_directories=(MATURIN_WHEELS_OUT_DIR,),
        extra_env_var_names=("MATURIN_PYPI_TOKEN",),
        cache_scope=ProcessCacheScope.PER_SESSION,
    )
    venv_pex = create_autospec(VenvPex, instance=True)
    env = EnvironmentVars({"PATH": "/usr/bin", "HOME": "/home/me"})
    expected = Process(argv=("maturin", "build"), description="build it")
    env_requests: list[EnvironmentVarsRequest] = []
    pex_processes: list[VenvPexProcess] = []

    def mock_environment_vars_subset(env_request: EnvironmentVarsRequest) -> EnvironmentVars:
        env_requests.append(env_request)
        return env

    def mock_setup_venv_pex_process(pex_process: VenvPexProcess) -> Process:
        pex_processes.append(pex_process)
        return expected

    actual = run_rule_with_mocks(
        setup_maturin_process,
        rule_args=[request, maturin],
        mock_calls={
            "maturin_pants_plugin.goals.maturin_common.create_maturin_venv_pex": lambda: venv_pex,
            "pants.core.util_rules.env_vars.environment_vars_subset": mock_environment_vars_subset,
            "pants.backend.python.util_rules.pex.setup_venv_pex_process": mock_setup_venv_pex_process,
        },
    )

    assert actual is expected
    [env_request] = env_requests
    assert tuple(env_request.requested) == (
        "PATH",
        "HOME",
        "CARGO_HOME",
        "RUSTUP_HOME",
        "RUSTFLAGS=-C target-cpu=native",
        "CARGO_NET_OFFLINE",
        "MATURIN_PYPI_TOKEN",
    )
    [pex_process] = pex_processes
    assert pex_process.venv_pex is venv_pex
    assert pex_process.argv == ("build",)
    assert pex_process.description == "build it"
    assert pex_process.extra_env == env
    assert pex_process.output_directories == (MATURIN_WHEELS_OUT_DIR,)
    assert pex_process.cache_scope is ProcessCacheScope.PER_SESSION
    assert pex_process.append_only_caches == MATURIN_CARGO_TARGET_CACHE


def test_setup_maturin_process_without_output_directories() -> None:
    """`VenvPexProcess` wants `None` rather than an empty tuple when nothing is captured."""
    pex_processes: list[VenvPexProcess] = []

    def mock_setup_venv_pex_process(pex_process: VenvPexProcess) -> Process:
        pex_processes.append(pex_process)
        return Process(argv=("maturin",), description="upload")

    run_rule_with_mocks(
        setup_maturin_process,
        rule_args=[MaturinProcessRequest(argv=("upload",), description="upload"), make_maturin()],
        mock_calls={
            "maturin_pants_plugin.goals.maturin_common.create_maturin_venv_pex": lambda: create_autospec(
                VenvPex, instance=True
            ),
            "pants.core.util_rules.env_vars.environment_vars_subset": lambda _request: EnvironmentVars({}),
            "pants.backend.python.util_rules.pex.setup_venv_pex_process": mock_setup_venv_pex_process,
        },
    )

    [pex_process] = pex_processes
    assert pex_process.output_directories is None
    assert pex_process.cache_scope is ProcessCacheScope.SUCCESSFUL
