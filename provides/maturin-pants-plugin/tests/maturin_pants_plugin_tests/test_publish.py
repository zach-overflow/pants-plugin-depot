from typing import Any

import pytest
from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact
from pants.core.goals.publish import (
    CheckSkipResult,
    PublishFieldSet,
    PublishOutputData,
    PublishPackages,
    PublishProcesses,
    PublishRequest,
)
from pants.engine.fs import EMPTY_DIGEST, Snapshot
from pants.engine.process import InteractiveProcess, Process, ProcessCacheScope
from pants.engine.unions import UnionRule
from pants.testutil.rule_runner import run_rule_with_mocks
from pants.util.frozendict import FrozenDict

from maturin_pants_plugin.goals.maturin_common import (
    MATURIN_UPLOAD_ENV_VAR_NAMES,
    MaturinProcessRequest,
    construct_maturin_upload_argv,
)
from maturin_pants_plugin.goals.package import MaturinPackageFieldSet
from maturin_pants_plugin.goals.publish import (
    MaturinCheckSkipRequest,
    MaturinPublishFieldSet,
    MaturinPublishRequest,
    check_if_skip_maturin_upload,
    maturin_upload,
)
from maturin_pants_plugin.target_types import MaturinWheelTarget
from maturin_pants_plugin_tests.conftest import CRATE_ADDRESS, make_maturin

_REPOSITORIES = ("@pypi", "https://upload.example.com/legacy/")
_WHEELS = ("a.whl", "b.whl")


def _check_skip_request(target_kwargs: dict[str, Any]) -> MaturinCheckSkipRequest:
    target = MaturinWheelTarget(target_kwargs, CRATE_ADDRESS)
    return MaturinCheckSkipRequest(
        package_fs=MaturinPackageFieldSet.create(target), publish_fs=MaturinPublishFieldSet.create(target)
    )


def test_field_set() -> None:
    target = MaturinWheelTarget({"repositories": ["@pypi"]}, CRATE_ADDRESS)
    assert MaturinPublishFieldSet.is_applicable(target)
    field_set = MaturinPublishFieldSet.create(target)
    package_fs = MaturinPackageFieldSet.create(target)

    skip_request = field_set.check_skip_request(package_fs)

    assert isinstance(skip_request, MaturinCheckSkipRequest)
    assert skip_request.publish_fs is field_set
    assert skip_request.package_fs is package_fs
    assert skip_request.address == CRATE_ADDRESS
    assert field_set.get_output_data() == PublishOutputData({"publisher": "maturin", "target": CRATE_ADDRESS})
    assert MaturinPublishFieldSet.rules() == (
        UnionRule(PublishFieldSet, MaturinPublishFieldSet),
        UnionRule(PublishRequest, MaturinPublishRequest),
    )


@pytest.mark.parametrize(
    ("skip_option", "target_kwargs", "expected_reason"),
    [
        (True, {"repositories": ["@pypi"]}, "(by `[maturin].skip = True`)"),
        (
            False,
            {"repositories": ["@pypi"], "skip_maturin_upload": True},
            f"(by `skip_maturin_upload` on {CRATE_ADDRESS})",
        ),
        (False, {}, f"(no `repositories` specified for {CRATE_ADDRESS})"),
        (False, {"repositories": []}, f"(no `repositories` specified for {CRATE_ADDRESS})"),
    ],
)
def test_check_if_skip_maturin_upload_skips(
    skip_option: bool, target_kwargs: dict[str, Any], expected_reason: str
) -> None:
    actual = run_rule_with_mocks(
        check_if_skip_maturin_upload, rule_args=[_check_skip_request(target_kwargs), make_maturin(skip=skip_option)]
    )

    assert actual.skip_publish
    assert actual.skip_package
    assert actual.skipped_packages == (
        PublishPackages(
            names=(CRATE_ADDRESS.spec,),
            description=expected_reason,
            data=PublishOutputData({"publisher": "maturin", "target": CRATE_ADDRESS}),
        ),
    )


def test_check_if_skip_maturin_upload_does_not_skip() -> None:
    actual = run_rule_with_mocks(
        check_if_skip_maturin_upload, rule_args=[_check_skip_request({"repositories": ["@pypi"]}), make_maturin()]
    )

    assert actual == CheckSkipResult.no_skip()


def test_maturin_upload_without_wheels() -> None:
    field_set = MaturinPublishFieldSet.create(MaturinWheelTarget({"repositories": ["@pypi"]}, CRATE_ADDRESS))
    request = MaturinPublishRequest(field_set=field_set, packages=(BuiltPackage(EMPTY_DIGEST, ()),))

    actual = run_rule_with_mocks(maturin_upload, rule_args=[request, make_maturin()])

    assert actual == PublishProcesses()


def test_maturin_upload() -> None:
    """One interactive `maturin upload` process per repository, each uploading every built wheel."""
    maturin = make_maturin(skip_existing=True)
    field_set = MaturinPublishFieldSet.create(MaturinWheelTarget({"repositories": list(_REPOSITORIES)}, CRATE_ADDRESS))
    packages = (
        BuiltPackage(EMPTY_DIGEST, (BuiltPackageArtifact("a.whl"),)),
        BuiltPackage(EMPTY_DIGEST, (BuiltPackageArtifact("b.whl"), BuiltPackageArtifact(None, ("built it",)))),
    )
    request = MaturinPublishRequest(field_set=field_set, packages=packages)
    merged_digest = Snapshot.create_for_testing(list(_WHEELS), []).digest
    process_requests: list[MaturinProcessRequest] = []

    def mock_setup_maturin_process(process_request: MaturinProcessRequest) -> Process:
        process_requests.append(process_request)
        return Process(
            argv=("maturin", *process_request.argv),
            description=process_request.description,
            env={"MATURIN_PYPI_TOKEN": "token"},
        )

    actual = run_rule_with_mocks(
        maturin_upload,
        rule_args=[request, maturin],
        mock_calls={
            "pants.engine.intrinsics.merge_digests": lambda _merge_digests: merged_digest,
            "maturin_pants_plugin.goals.maturin_common.setup_maturin_process": mock_setup_maturin_process,
        },
    )

    assert process_requests == [
        MaturinProcessRequest(
            argv=construct_maturin_upload_argv(maturin, repository, _WHEELS),
            description=repository,
            input_digest=merged_digest,
            extra_env_var_names=MATURIN_UPLOAD_ENV_VAR_NAMES,
            cache_scope=ProcessCacheScope.PER_SESSION,
        )
        for repository in _REPOSITORIES
    ]
    assert len(actual) == len(_REPOSITORIES)
    for publish, repository in zip(actual, _REPOSITORIES, strict=True):
        assert publish.names == _WHEELS
        assert publish.description == repository
        assert publish.data == PublishOutputData({"repository": repository})
        assert isinstance(publish.process, InteractiveProcess)
        assert publish.process.process.argv == ("maturin", *construct_maturin_upload_argv(maturin, repository, _WHEELS))
        assert publish.process.process.env == FrozenDict({"MATURIN_PYPI_TOKEN": "token"})
