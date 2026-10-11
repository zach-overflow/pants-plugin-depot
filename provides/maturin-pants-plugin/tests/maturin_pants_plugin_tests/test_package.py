import os
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact
from pants.core.target_types import FileTarget
from pants.engine.addresses import Address
from pants.engine.fs import Digest, DigestContents, RemovePrefix, Snapshot
from pants.engine.process import ProcessResult
from pants.testutil.rule_runner import RuleRunner, run_rule_with_mocks

from maturin_pants_plugin.goals.maturin_common import (
    MATURIN_WHEELS_OUT_DIR,
    MaturinProcessRequest,
    MaturinSources,
    construct_maturin_build_argv,
)
from maturin_pants_plugin.goals.package import MaturinPackageFieldSet, build_maturin_package
from maturin_pants_plugin.target_types import MaturinWheelTarget
from maturin_pants_plugin_tests.conftest import CRATE_ADDRESS, CRATE_DIR, make_maturin

_WHEEL = "hello_maturin-0.1.0-py3-none-any.whl"


def _cargo_on_path() -> bool:
    return any((Path(entry) / "cargo").is_file() for entry in os.environ.get("PATH", "").split(os.pathsep) if entry)


def test_field_set_applies_to_maturin_wheel_targets_only() -> None:
    wheel = MaturinWheelTarget({}, CRATE_ADDRESS)
    readme = FileTarget({"source": "README.md"}, Address(CRATE_DIR, target_name="readme"))

    assert MaturinPackageFieldSet.is_applicable(wheel)
    assert not MaturinPackageFieldSet.is_applicable(readme)


def test_build_maturin_package() -> None:
    """The build process gets the hydrated sources, and the wheels come back flat, without the sandbox out dir."""
    maturin = make_maturin()
    field_set = MaturinPackageFieldSet.create(MaturinWheelTarget({}, CRATE_ADDRESS))
    sources = Snapshot.create_for_testing([f"{CRATE_DIR}/Cargo.toml", f"{CRATE_DIR}/pyproject.toml"], [CRATE_DIR])
    output_digest = Snapshot.create_for_testing([f"{MATURIN_WHEELS_OUT_DIR}/{_WHEEL}"], [MATURIN_WHEELS_OUT_DIR]).digest
    wheels = Snapshot.create_for_testing([_WHEEL], [])
    process_result = create_autospec(ProcessResult, instance=True)
    process_result.output_digest = output_digest
    process_requests: list[MaturinProcessRequest] = []
    remove_prefixes: list[RemovePrefix] = []

    def mock_execute_process_or_raise(request: MaturinProcessRequest) -> ProcessResult:
        process_requests.append(request)
        return process_result

    def mock_remove_prefix(remove_prefix: RemovePrefix) -> Digest:
        remove_prefixes.append(remove_prefix)
        return wheels.digest

    actual = run_rule_with_mocks(
        build_maturin_package,
        rule_args=[field_set, maturin],
        mock_calls={
            "maturin_pants_plugin.goals.maturin_common.get_maturin_sources": lambda _field_set: MaturinSources(sources),
            "pants.engine.process.fallible_to_exec_result_or_raise": mock_execute_process_or_raise,
            "pants.engine.intrinsics.remove_prefix": mock_remove_prefix,
            "pants.engine.intrinsics.digest_to_snapshot": lambda _digest: wheels,
        },
    )

    assert actual == BuiltPackage(wheels.digest, (BuiltPackageArtifact(relpath=_WHEEL),))
    assert process_requests == [
        MaturinProcessRequest(
            argv=construct_maturin_build_argv(maturin, f"{CRATE_DIR}/Cargo.toml"),
            description=f"Build wheel(s) with maturin for {CRATE_ADDRESS}",
            input_digest=sources.digest,
            output_directories=(MATURIN_WHEELS_OUT_DIR,),
        )
    ]
    assert remove_prefixes == [RemovePrefix(output_digest, MATURIN_WHEELS_OUT_DIR)]


@pytest.mark.skipif(not _cargo_on_path(), reason="`cargo` is not on PATH")
def test_build_maturin_package_end_to_end(maturin_rule_runner: RuleRunner, bin_crate_files: dict[str, str]) -> None:
    """Builds the fake crate for real: resolves the `maturin` pex (network) and runs `cargo` from `PATH`."""
    maturin_rule_runner.write_files(bin_crate_files)
    target = maturin_rule_runner.get_target(CRATE_ADDRESS)

    built = maturin_rule_runner.request(BuiltPackage, [MaturinPackageFieldSet.create(target)])

    [artifact] = built.artifacts
    assert artifact.relpath is not None
    assert artifact.relpath.startswith("hello_maturin-0.1.0-py3-none-")
    assert artifact.relpath.endswith(".whl")
    contents = maturin_rule_runner.request(DigestContents, [built.digest])
    assert [file_content.path for file_content in contents] == [artifact.relpath]
