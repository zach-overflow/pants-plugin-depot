from dataclasses import dataclass
from typing import TYPE_CHECKING

from pants.core.goals.package import PackageFieldSet
from pants.core.goals.publish import (
    CheckSkipRequest,
    CheckSkipResult,
    PublishFieldSet,
    PublishOutputData,
    PublishPackages,
    PublishProcesses,
    PublishRequest,
)
from pants.engine.fs import MergeDigests
from pants.engine.intrinsics import merge_digests
from pants.engine.process import InteractiveProcess, ProcessCacheScope
from pants.engine.rules import collect_rules, concurrently, implicitly, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel

from maturin_pants_plugin.goals.maturin_common import (
    MATURIN_UPLOAD_ENV_VAR_NAMES,
    MaturinFieldSet,
    MaturinProcessRequest,
    construct_maturin_upload_argv,
    setup_maturin_process,
)
from maturin_pants_plugin.subsystem import Maturin
from maturin_pants_plugin.target_types import (
    CargoTomlField,
    MaturinRepositoriesField,
    MaturinWheelSourcesField,
    PyProjectTomlField,
    SkipMaturinUploadField,
)

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules


class MaturinPublishRequest(PublishRequest["MaturinPublishFieldSet"]):
    """`PublishRequest` carrying the wheels `pants package` built for a `maturin_wheel` target."""


@dataclass(frozen=True)
class MaturinPublishFieldSet(PublishFieldSet[MaturinPublishRequest], MaturinFieldSet):
    """`PublishFieldSet` subtype for the `maturin` pants plugin."""

    publish_request_type = MaturinPublishRequest
    required_fields = (MaturinWheelSourcesField, CargoTomlField, PyProjectTomlField, MaturinRepositoriesField)

    repositories: MaturinRepositoriesField
    skip_maturin_upload: SkipMaturinUploadField

    def check_skip_request(self, package_fs: PackageFieldSet) -> MaturinCheckSkipRequest | None:
        return MaturinCheckSkipRequest(package_fs=package_fs, publish_fs=self)

    def get_output_data(self) -> PublishOutputData:
        return PublishOutputData({"publisher": "maturin", **super().get_output_data()})


class MaturinCheckSkipRequest(CheckSkipRequest[MaturinPublishFieldSet]):
    """Asks whether a `maturin_wheel` target's upload, and therefore its build, can be skipped up front."""


@rule(desc="Checks whether `maturin upload` is skipped for a `maturin_wheel` target.", level=LogLevel.DEBUG)
async def check_if_skip_maturin_upload(request: MaturinCheckSkipRequest, maturin: Maturin) -> CheckSkipResult:
    if maturin.skip:
        reason = f"(by `[{Maturin.options_scope}].skip = True`)"
    elif request.publish_fs.skip_maturin_upload.value:
        reason = f"(by `{request.publish_fs.skip_maturin_upload.alias}` on {request.address})"
    elif not request.publish_fs.repositories.value:
        reason = f"(no `{request.publish_fs.repositories.alias}` specified for {request.address})"
    else:
        return CheckSkipResult.no_skip()
    return CheckSkipResult.skip(
        names=[request.address.spec], description=reason, data=request.publish_fs.get_output_data()
    )


@rule(desc="Publishes wheels built via `maturin build` to python package registries.", level=LogLevel.DEBUG)
async def maturin_upload(request: MaturinPublishRequest, maturin: Maturin) -> PublishProcesses:
    dists = tuple(artifact.relpath for pkg in request.packages for artifact in pkg.artifacts if artifact.relpath)
    if not dists:
        return PublishProcesses()

    wheels_digest = await merge_digests(MergeDigests(pkg.digest for pkg in request.packages))
    repositories: tuple[str, ...] = request.field_set.repositories.value or ()
    processes = await concurrently(
        setup_maturin_process(
            MaturinProcessRequest(
                argv=construct_maturin_upload_argv(maturin, repository, dists),
                description=repository,
                input_digest=wheels_digest,
                extra_env_var_names=MATURIN_UPLOAD_ENV_VAR_NAMES,
                # Publishing must run every time: the engine asserts this scope for non-interactive publish processes.
                cache_scope=ProcessCacheScope.PER_SESSION,
            ),
            **implicitly(),
        )
        for repository in repositories
    )
    return PublishProcesses(
        PublishPackages(
            names=dists,
            process=InteractiveProcess.from_process(process),
            description=process.description,
            data=PublishOutputData({"repository": process.description}),
        )
        for process in processes
    )


def rules() -> CollectedRules:
    """Returns the `publish`-goal-specific rules for the maturin pants plugin."""
    return (*collect_rules(), *MaturinPublishFieldSet.rules(), UnionRule(CheckSkipRequest, MaturinCheckSkipRequest))
