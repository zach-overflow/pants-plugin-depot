import subprocess  # noqa: TID251 -- test-only: drives a throwaway git repo, like Pants' own vcs_versioning_test
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from pants.backend.python import target_types_rules
from pants.backend.python.dependency_inference.module_mapper import FirstPartyPythonMappingImpl
from pants.engine.addresses import Address
from pants.engine.fs import DigestContents
from pants.engine.internals.native_engine import EMPTY_SNAPSHOT
from pants.engine.target import GeneratedSources
from pants.testutil.rule_runner import QueryRule, RuleRunner
from pants.util.contextutil import environment_as
from pants.vcs import git

from pants_plugin_developer_utils.testing_utils import (
    RuleRunnerFactory,
    rule_runner_factory,  # noqa: F401
)
from vcs_versioning_pants_plugin import codegen, module_mapper, subsystem
from vcs_versioning_pants_plugin.codegen import GenerateScmVersionRequest
from vcs_versioning_pants_plugin.module_mapper import ScmVersionMappingMarker
from vcs_versioning_pants_plugin.target_types import ScmVersionTarget


@pytest.fixture(scope="function")
def scm_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:  # noqa: F811
    """
    Integration `RuleRunner`: builds the real vcs-versioning venv from the bundled lockfile (network).

    One runner per git scenario: the vcs-versioning process caches per session, so re-requesting a target after
    changing the git state returns the stale version.
    """
    rule_runner = rule_runner_factory(
        rules=[
            *codegen.rules(),
            *module_mapper.rules(),
            *subsystem.rules(),
            *target_types_rules.rules(),
            # Global in a real Pants run, but a `RuleRunner` registers only what it is given.
            *git.rules(),
            QueryRule(GeneratedSources, [GenerateScmVersionRequest]),
            QueryRule(FirstPartyPythonMappingImpl, [ScmVersionMappingMarker]),
        ],
        target_types=[ScmVersionTarget],
    )
    rule_runner.set_options(
        # Mirror `[python].pip_version` in `pants.toml`: Pants' default pip predates CPython 3.14.
        ["--python-pip-version=latest", "--python-enable-resolves=True", "--source-root-patterns=['src']"],
        env_inherit={"PATH", "PYENV_ROOT", "HOME"},
    )
    return rule_runner


@dataclass(frozen=True)
class GitRepo:
    """A throwaway git repository outside the `RuleRunner` build root."""

    worktree: Path

    @property
    def gitdir(self) -> Path:
        return self.worktree / ".git"

    @contextmanager
    def env(self) -> Generator[None]:
        """
        Point git at this repository.

        Pants' `get_git_worktree` runs `git rev-parse --show-toplevel` unsandboxed in the current directory, so
        the engine request must run inside this context too, not only the setup commands.
        """
        with environment_as(GIT_DIR=str(self.gitdir), GIT_WORK_TREE=str(self.worktree), GIT_CONFIG_GLOBAL="/dev/null"):
            yield

    def git(self, *args: str) -> str:
        with self.env():
            return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message: str) -> str:
        """Commit a change to `README` and return the abbreviated commit hash."""
        (self.worktree / "README").write_text(message)
        self.git("add", ".")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "--short", "HEAD")

    def tag(self, name: str) -> None:
        self.git("tag", name)


@pytest.fixture(scope="function")
def git_repo(tmp_path: Path) -> GitRepo:
    repo = GitRepo(tmp_path / "worktree")
    repo.worktree.mkdir()
    repo.git("init", "-q")
    repo.git("config", "user.email", "you@example.com")
    repo.git("config", "user.name", "Test User")
    return repo


def scm_version_build(name: str, **fields: str) -> str:
    """Render a `scm_version` target with `generate_to="src/<name>/version.py"` and the given extra fields."""
    lines = [
        "scm_version(",
        f"    name={name!r},",
        f'    generate_to="src/{name}/version.py",',
        "    template='__version__ = \"{version}\"\\n',",
        *(f"    {field}={value!r}," for field, value in fields.items()),
        ")",
    ]
    return "\n".join(lines) + "\n"


def generate(rule_runner: RuleRunner, repo: GitRepo, address: Address) -> str:
    """Run the codegen for `address` against `repo` and return the generated file's contents."""
    target = rule_runner.get_target(address)
    with repo.env():
        generated = rule_runner.request(GeneratedSources, [GenerateScmVersionRequest(EMPTY_SNAPSHOT, target)])
    assert generated.snapshot.files == (f"src/{address.target_name}/version.py",)
    contents = rule_runner.request(DigestContents, [generated.snapshot.digest])
    assert len(contents) == 1
    return contents[0].content.decode()
