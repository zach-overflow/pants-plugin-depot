from dataclasses import dataclass

from pants.core.goals.package import BuiltPackage, BuiltPackageArtifact, PackageFieldSet
from pants.engine.fs import RemovePrefix
from pants.engine.intrinsics import digest_to_snapshot, remove_prefix
from pants.engine.process import execute_process_or_raise
from pants.engine.rules import collect_rules, implicitly, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel

from maturin_pants_plugin.goals.maturin_common import (
    MATURIN_WHEELS_OUT_DIR,
    MaturinFieldSet,
    MaturinProcessRequest,
    construct_maturin_build_argv,
    get_maturin_sources,
)
from maturin_pants_plugin.subsystem import Maturin
from pants_plugin_developer_utils import CollectedRules


@dataclass(frozen=True)
class MaturinPackageFieldSet(PackageFieldSet, MaturinFieldSet):
    """`PackageFieldSet` subtype for the `maturin` pants plugin."""


@rule(desc="Builds the rust program and packages it into a Python wheel via `maturin`.", level=LogLevel.DEBUG)
async def build_maturin_package(field_set: MaturinPackageFieldSet, maturin: Maturin) -> BuiltPackage:
    sources = await get_maturin_sources(field_set)
    result = await execute_process_or_raise(
        **implicitly(
            MaturinProcessRequest(
                argv=construct_maturin_build_argv(maturin, field_set.cargo_toml.file_path),
                description=f"Build wheel(s) with maturin for {field_set.address}",
                input_digest=sources.snapshot.digest,
                output_directories=(MATURIN_WHEELS_OUT_DIR,),
            )
        )
    )
    wheels_digest = await remove_prefix(RemovePrefix(result.output_digest, MATURIN_WHEELS_OUT_DIR))
    wheels = await digest_to_snapshot(wheels_digest)
    return BuiltPackage(wheels.digest, tuple(BuiltPackageArtifact(relpath=path) for path in wheels.files))


def rules() -> CollectedRules:
    """Returns the `package`-goal-specific rules for the maturin pants plugin."""
    return (*collect_rules(), UnionRule(PackageFieldSet, MaturinPackageFieldSet))
