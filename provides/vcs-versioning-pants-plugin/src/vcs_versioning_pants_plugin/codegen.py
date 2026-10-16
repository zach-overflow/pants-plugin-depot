"""
Generates the version module of a `scm_version` target, or the version file of a `scm_version_file` target, by running
vcs-versioning against the git worktree.
"""

import json
from typing import TYPE_CHECKING, cast

from pants.backend.python.subsystems.python_tool_base import get_lockfile_interpreter_constraints
from pants.backend.python.target_types import PythonSourceField
from pants.backend.python.util_rules.pex import PexRequest, VenvPexProcess, create_venv_pex
from pants.core.target_types import FileSourceField
from pants.engine.environment import ChosenLocalEnvironmentName, EnvironmentName
from pants.engine.fs import CreateDigest, FileContent
from pants.engine.internals.selectors import concurrently
from pants.engine.intrinsics import create_digest, digest_to_snapshot, execute_process
from pants.engine.process import ProcessCacheScope
from pants.engine.rules import collect_rules, implicitly, rule
from pants.engine.target import GeneratedSources, GenerateSourcesRequest, Target
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel
from pants.util.strutil import softwrap
from pants.vcs.git import GitWorktreeRequest, get_git_worktree

from vcs_versioning_pants_plugin.subsystem import VcsVersioning
from vcs_versioning_pants_plugin.target_types import (
    ScmVersionDummySourceField,
    ScmVersionFileDummySourceField,
    ScmVersionGenerateToField,
    ScmVersionLocalSchemeField,
    ScmVersionTagPrefixField,
    ScmVersionTagRegexField,
    ScmVersionTemplateField,
    ScmVersionVersionSchemeField,
)

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules

SYNTHETIC_CONFIG_PATH = "pyproject.synthetic.toml"


class ScmVersioningError(Exception):
    """Raised when no git worktree is available to derive a version from."""


class GenerateScmVersionRequest(GenerateSourcesRequest):
    """Codegen request turning a `scm_version` target into a Python source file."""

    input = ScmVersionDummySourceField
    output = PythonSourceField


class GenerateScmVersionFileRequest(GenerateSourcesRequest):
    """Codegen request turning a `scm_version_file` target into a `file`-typed asset."""

    input = ScmVersionFileDummySourceField
    output = FileSourceField


def _toml_string(value: str) -> str:
    # A JSON string literal is also a valid TOML basic string: both escape `"`, `\` and control characters
    # with the same `\x` / `\uXXXX` sequences.
    return json.dumps(value, ensure_ascii=False)


def render_vcs_versioning_config(target: Target) -> str:
    """
    Render the synthetic `pyproject.toml` handed to vcs-versioning.

    Only the target's fields are honoured; any `[tool.vcs-versioning]` table in the repo is ignored. The file
    lives in the sandbox so vcs-versioning cannot write a version file into the workspace.
    """
    lines = ["[tool.vcs-versioning]"]
    if version_scheme := target[ScmVersionVersionSchemeField].value:
        lines.append(f"version_scheme = {_toml_string(version_scheme)}")
    if local_scheme := target[ScmVersionLocalSchemeField].value:
        lines.append(f"local_scheme = {_toml_string(local_scheme)}")
    # vcs-versioning 2 (setuptools-scm 10) deprecates the top-level `tag_regex` in favour of the `tag` table.
    lines.extend(["", "[tool.vcs-versioning.tag]"])
    if tag_prefix := target[ScmVersionTagPrefixField].value:
        lines.append(f"prefix = {_toml_string(tag_prefix)}")
    if tag_regex := target[ScmVersionTagRegexField].value:
        lines.append(f"regex = {_toml_string(tag_regex)}")
    return "\n".join(lines) + "\n"


async def _generate_version_file(
    target: Target, vcs_versioning: VcsVersioning, local_environment_name: ChosenLocalEnvironmentName
) -> GeneratedSources:
    """Runs vcs-versioning for `target` and renders its `template` into `generate_to`; shared by both generators."""
    # A MaybeGitWorktree is uncacheable, so this rule runs every time its result is needed. The process below
    # caches at session scope, so the result always reflects the current git state.
    maybe_git_worktree = await get_git_worktree(
        **implicitly({GitWorktreeRequest(): GitWorktreeRequest, local_environment_name.val: EnvironmentName})
    )
    if not maybe_git_worktree.git_worktree:
        raise ScmVersioningError(
            softwrap(
                f"""
                Cannot determine the version for the {target.address} target: {maybe_git_worktree.failure_reason}.
                """
            )
        )

    input_digest_get = create_digest(
        CreateDigest([FileContent(SYNTHETIC_CONFIG_PATH, render_vcs_versioning_config(target).encode())])
    )
    # Pin the tool to the interpreters its lockfile was generated for (the bundled one covers CPython 3.14
    # only), instead of letting `[python].interpreter_constraints` pick one the lockfile cannot serve.
    interpreter_constraints = await get_lockfile_interpreter_constraints(vcs_versioning)
    vcs_versioning_pex_get = create_venv_pex(
        **implicitly(
            {
                vcs_versioning.to_pex_request(interpreter_constraints=interpreter_constraints): PexRequest,
                local_environment_name.val: EnvironmentName,
            }
        )
    )
    vcs_versioning_pex, input_digest = await concurrently(vcs_versioning_pex_get, input_digest_get)

    argv = ["--root", str(maybe_git_worktree.git_worktree.worktree), "--config", SYNTHETIC_CONFIG_PATH]
    result = await execute_process(
        **implicitly(
            {
                VenvPexProcess(
                    vcs_versioning_pex,
                    argv=argv,
                    input_digest=input_digest,
                    description=f"Run vcs-versioning for {target.address.spec}",
                    level=LogLevel.INFO,
                    cache_scope=ProcessCacheScope.PER_SESSION,
                ): VenvPexProcess,
                local_environment_name.val: EnvironmentName,
            }
        )
    )
    version = result.stdout.decode().strip()
    # Both fields always have a value, but `StringField.value` is typed `str | None`.
    generate_to = cast(str, target[ScmVersionGenerateToField].value)
    template = cast(str, target[ScmVersionTemplateField].value)
    output_snapshot = await digest_to_snapshot(
        **implicitly(CreateDigest([FileContent(generate_to, template.format(version=version).encode())]))
    )
    return GeneratedSources(output_snapshot)


@rule(desc="Generate a version module from git tags with vcs-versioning", level=LogLevel.DEBUG)
async def generate_python_from_scm_version(
    request: GenerateScmVersionRequest,
    vcs_versioning: VcsVersioning,
    local_environment_name: ChosenLocalEnvironmentName,
) -> GeneratedSources:
    return await _generate_version_file(request.protocol_target, vcs_versioning, local_environment_name)


@rule(desc="Generate a version file from git tags with vcs-versioning", level=LogLevel.DEBUG)
async def generate_file_from_scm_version(
    request: GenerateScmVersionFileRequest,
    vcs_versioning: VcsVersioning,
    local_environment_name: ChosenLocalEnvironmentName,
) -> GeneratedSources:
    return await _generate_version_file(request.protocol_target, vcs_versioning, local_environment_name)


def rules() -> CollectedRules:
    return (
        *collect_rules(),
        UnionRule(GenerateSourcesRequest, GenerateScmVersionRequest),
        UnionRule(GenerateSourcesRequest, GenerateScmVersionFileRequest),
    )
