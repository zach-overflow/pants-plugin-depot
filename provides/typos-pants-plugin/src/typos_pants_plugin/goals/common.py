"""Rules and helpers shared by the `fix` and `lint` goal integrations of `typos`."""

import os.path
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import TYPE_CHECKING, Any

from pants.core.util_rules import config_files
from pants.core.util_rules.config_files import find_config_file
from pants.core.util_rules.external_tool import download_external_tool
from pants.core.util_rules.partitions import Partitions
from pants.engine.fs import MergeDigests, Snapshot
from pants.engine.intrinsics import merge_digests
from pants.engine.platform import Platform
from pants.engine.process import Process
from pants.engine.rules import collect_rules, concurrently, rule
from pants.source.filespec import FilespecMatcher
from pants.util.logging import LogLevel
from pants.util.strutil import pluralize

from typos_pants_plugin.subsystem import Typos

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules

TOOL_INPUT_DIR = "__typos_tool"
"""Sandbox directory the downloaded `typos` release is mounted in, as an immutable input shared across runs."""

TYPOS_FOUND_EXIT_CODE = 2
"""The exit code `typos` reserves for having found typos; other non-zero codes are usage, config or I/O errors."""


@unique
class TyposMode(StrEnum):
    """How `typos` runs: `LINT` reports every typo, `FIX` writes the unambiguous corrections back."""

    LINT = "lint"
    FIX = "fix"


@dataclass(frozen=True)
class TyposProcessRequest:
    """The inputs of one `typos` run over the files of a goal batch."""

    snapshot: Snapshot
    files: tuple[str, ...]
    mode: TyposMode


@dataclass(frozen=True)
class TyposPartitionRequest:
    """The files a goal was given, to be narrowed to the ones `typos` checks. Shared by `fix` and `lint`."""

    files: tuple[str, ...]


@rule
async def partition_typos_inputs(request: TyposPartitionRequest, typos: Typos) -> Partitions[str, Any]:
    """Selects the files matching `[typos].glob_pattern` as one partition, or none when nothing is to be run."""
    if typos.skip:
        return Partitions()
    matched_filepaths = FilespecMatcher(
        includes=[
            (glob[2:] if glob.startswith(r"\\!") else glob) for glob in typos.glob_pattern if not glob.startswith("!")
        ],
        excludes=[glob[1:] for glob in typos.glob_pattern if glob.startswith("!")],
    ).matches(request.files)
    # An empty file list would make `typos` fall back to scanning the whole sandbox.
    return Partitions.single_partition(sorted(matched_filepaths)) if matched_filepaths else Partitions()


def generate_argv(typos: Typos, *, exe: str, mode: TyposMode, files: Iterable[str]) -> tuple[str, ...]:
    """
    The `typos` command line for one batch.

    `--force-exclude` makes `typos` honor its `files.extend-exclude` globs for explicitly listed files too.
    `fix` skips file name checks: `typos --write-changes` renames misspelled files, which Pants cannot write
    back, whereas `lint` still reports them.
    """
    argv = [exe, "--force-exclude"]
    if typos.config:
        argv.extend(["--config", typos.config])
    if typos.config or not typos.config_discovery:
        argv.append("--isolated")
    if mode is TyposMode.FIX:
        argv.extend(["--write-changes", "--no-check-filenames"])
    argv.extend(typos.args)
    argv.extend(files)
    return tuple(argv)


@rule(desc="Set up the `typos` process", level=LogLevel.DEBUG)
async def setup_typos_process(request: TyposProcessRequest, typos: Typos, platform: Platform) -> Process:
    downloaded_typos, config_files_found = await concurrently(
        download_external_tool(typos.get_request(platform)),
        find_config_file(typos.config_request(request.snapshot.dirs)),
    )
    input_digest = await merge_digests(MergeDigests((request.snapshot.digest, config_files_found.snapshot.digest)))
    mode_flags = " --write-changes" if request.mode is TyposMode.FIX else ""
    return Process(
        argv=generate_argv(
            typos, exe=os.path.join(TOOL_INPUT_DIR, downloaded_typos.exe), mode=request.mode, files=request.files
        ),
        input_digest=input_digest,
        immutable_input_digests={TOOL_INPUT_DIR: downloaded_typos.digest},
        output_files=request.files if request.mode is TyposMode.FIX else (),
        description=f"Run typos{mode_flags} on {pluralize(len(request.files), 'file')}.",
        level=LogLevel.DEBUG,
    )


def rules() -> CollectedRules:
    return (*collect_rules(), *config_files.rules())
