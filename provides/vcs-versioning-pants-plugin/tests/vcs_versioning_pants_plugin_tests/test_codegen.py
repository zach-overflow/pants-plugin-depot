import tomllib
from dataclasses import dataclass, field
from pathlib import PurePath
from unittest.mock import create_autospec

import pytest
from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.backend.python.util_rules.pex import PexRequest, VenvPex, VenvPexProcess
from pants.core.util_rules.system_binaries import GitBinary
from pants.engine.addresses import Address
from pants.engine.environment import ChosenLocalEnvironmentName, EnvironmentName
from pants.engine.fs import CreateDigest, FileContent, Snapshot
from pants.engine.internals.native_engine import EMPTY_SNAPSHOT
from pants.engine.process import ProcessCacheScope, ProcessResult
from pants.engine.target import GeneratedSources
from pants.testutil.rule_runner import run_rule_with_mocks
from pants.vcs.git import GitWorktree, GitWorktreeRequest, MaybeGitWorktree

from vcs_versioning_pants_plugin.codegen import (
    SYNTHETIC_CONFIG_PATH,
    GenerateScmVersionRequest,
    ScmVersioningError,
    generate_python_from_scm_version,
    render_vcs_versioning_config,
)
from vcs_versioning_pants_plugin.subsystem import VcsVersioning
from vcs_versioning_pants_plugin.target_types import DEFAULT_TAG_REGEX, ScmVersionTarget
from vcs_versioning_pants_plugin_tests.conftest import TOOL_INTERPRETER_CONSTRAINTS

ADDRESS = Address("src/pkg", target_name="pkg")
GENERATE_TO = "src/pkg/version.py"
WORKTREE = PurePath("/checkout")
ENVIRONMENT = ChosenLocalEnvironmentName(EnvironmentName(None))


def _target(**fields: str) -> ScmVersionTarget:
    values = {"generate_to": GENERATE_TO, "template": '__version__ = "{version}"\n', **fields}
    return ScmVersionTarget(values, ADDRESS)


# --------------------------------------------------------------------------------------
# Synthetic config rendering (no engine)
# --------------------------------------------------------------------------------------


def test_render_config_uses_the_tag_table_not_the_deprecated_tag_regex() -> None:
    config = tomllib.loads(render_vcs_versioning_config(_target(tag_prefix="my-plugin-v")))

    # Round-tripping through a TOML parser proves the regex escapes (`\w`, `\d`, `\+`) survive rendering.
    assert config == {"tool": {"vcs-versioning": {"tag": {"prefix": "my-plugin-v", "regex": DEFAULT_TAG_REGEX}}}}


def test_render_config_includes_schemes_only_when_set() -> None:
    config = tomllib.loads(
        render_vcs_versioning_config(
            _target(
                tag_regex=r"^version_(?P<version>.*)$", version_scheme="no-guess-dev", local_scheme="no-local-version"
            )
        )
    )

    assert config["tool"]["vcs-versioning"] == {
        "version_scheme": "no-guess-dev",
        "local_scheme": "no-local-version",
        "tag": {"regex": r"^version_(?P<version>.*)$"},
    }


# --------------------------------------------------------------------------------------
# The codegen rule, with git, the pex build and the process execution mocked
# --------------------------------------------------------------------------------------


def _git_worktree() -> MaybeGitWorktree:
    """A worktree at `WORKTREE`. Nothing invokes the binary: the rule only reads the worktree path."""
    return MaybeGitWorktree(
        GitWorktree(GitBinary("/usr/bin/git", fingerprint="unused"), worktree=WORKTREE, gitdir=WORKTREE / ".git")
    )


@dataclass
class CodegenRun:
    """What the codegen rule returned and everything it asked the engine for, in call order."""

    venv_pex: VenvPex
    config_snapshot: Snapshot
    output_snapshot: Snapshot
    generated: GeneratedSources | None = None
    git_requests: list[tuple[GitWorktreeRequest, EnvironmentName]] = field(default_factory=list)
    pex_requests: list[tuple[PexRequest, EnvironmentName]] = field(default_factory=list)
    config_digests: list[CreateDigest] = field(default_factory=list)
    processes: list[tuple[VenvPexProcess, EnvironmentName]] = field(default_factory=list)
    output_digests: list[CreateDigest] = field(default_factory=list)


def run_codegen(target: ScmVersionTarget, vcs_versioning: VcsVersioning, *, stdout: bytes) -> CodegenRun:
    """Run the codegen rule for `target` with vcs-versioning's process mocked to print `stdout`."""
    venv_pex: VenvPex = create_autospec(VenvPex, instance=True)
    process_result: ProcessResult = create_autospec(ProcessResult, instance=True, stdout=stdout)
    run = CodegenRun(
        venv_pex=venv_pex,
        config_snapshot=Snapshot.create_for_testing([SYNTHETIC_CONFIG_PATH], []),
        output_snapshot=Snapshot.create_for_testing([GENERATE_TO], ["src", "src/pkg"]),
    )

    def mock_get_git_worktree(request: GitWorktreeRequest, environment: EnvironmentName) -> MaybeGitWorktree:
        run.git_requests.append((request, environment))
        return _git_worktree()

    def mock_create_venv_pex(pex_request: PexRequest, environment: EnvironmentName) -> VenvPex:
        run.pex_requests.append((pex_request, environment))
        return venv_pex

    def mock_create_digest(create_digest: CreateDigest) -> object:
        run.config_digests.append(create_digest)
        return run.config_snapshot.digest

    def mock_execute_process(process: VenvPexProcess, environment: EnvironmentName) -> ProcessResult:
        run.processes.append((process, environment))
        return process_result

    def mock_digest_to_snapshot(create_digest: CreateDigest) -> Snapshot:
        run.output_digests.append(create_digest)
        return run.output_snapshot

    run.generated = run_rule_with_mocks(
        generate_python_from_scm_version,
        rule_args=[GenerateScmVersionRequest(EMPTY_SNAPSHOT, target), vcs_versioning, ENVIRONMENT],
        mock_calls={
            "pants.vcs.git.get_git_worktree": mock_get_git_worktree,
            "pants.backend.python.util_rules.pex.create_venv_pex": mock_create_venv_pex,
            "pants.engine.intrinsics.create_digest": mock_create_digest,
            "pants.engine.intrinsics.execute_process": mock_execute_process,
            "pants.engine.intrinsics.digest_to_snapshot": mock_digest_to_snapshot,
        },
    )
    return run


def test_generates_the_template_from_the_tools_stdout(vcs_versioning: VcsVersioning) -> None:
    run = run_codegen(_target(), vcs_versioning, stdout=b"1.2.3.dev4+gabc1234\n")

    assert run.output_digests == [CreateDigest([FileContent(GENERATE_TO, b'__version__ = "1.2.3.dev4+gabc1234"\n')])]
    assert run.generated == GeneratedSources(run.output_snapshot)


def test_runs_the_tool_in_the_worktree_with_the_synthetic_config(vcs_versioning: VcsVersioning) -> None:
    target = _target(tag_prefix="alpha-plugin-v", version_scheme="no-guess-dev")

    run = run_codegen(target, vcs_versioning, stdout=b"1.2.3")

    assert run.git_requests == [(GitWorktreeRequest(), ENVIRONMENT.val)]
    assert run.config_digests == [
        CreateDigest([FileContent(SYNTHETIC_CONFIG_PATH, render_vcs_versioning_config(target).encode())])
    ]
    [(process, environment)] = run.processes
    assert environment == ENVIRONMENT.val
    assert process.venv_pex is run.venv_pex
    assert process.argv == ("--root", str(WORKTREE), "--config", SYNTHETIC_CONFIG_PATH)
    assert process.input_digest == run.config_snapshot.digest
    assert process.description == f"Run vcs-versioning for {ADDRESS.spec}"
    # Git state changes between sessions, so the result must not outlive one.
    assert process.cache_scope == ProcessCacheScope.PER_SESSION


def test_builds_the_tool_for_its_own_interpreter_constraints(vcs_versioning: VcsVersioning) -> None:
    run = run_codegen(_target(), vcs_versioning, stdout=b"1.2.3")

    [(pex_request, environment)] = run.pex_requests
    assert environment == ENVIRONMENT.val
    assert pex_request.main == VcsVersioning.default_main
    assert pex_request.interpreter_constraints == InterpreterConstraints(TOOL_INTERPRETER_CONSTRAINTS)


def test_no_git_worktree_is_an_error(vcs_versioning: VcsVersioning) -> None:
    def mock_get_git_worktree(_request: GitWorktreeRequest, _environment: EnvironmentName) -> MaybeGitWorktree:
        return MaybeGitWorktree(failure_reason="no git repository at /checkout")

    with pytest.raises(ScmVersioningError, match=rf"version for the {ADDRESS} target: no git repository at /checkout"):
        run_rule_with_mocks(
            generate_python_from_scm_version,
            rule_args=[GenerateScmVersionRequest(EMPTY_SNAPSHOT, _target()), vcs_versioning, ENVIRONMENT],
            mock_calls={"pants.vcs.git.get_git_worktree": mock_get_git_worktree},
        )
