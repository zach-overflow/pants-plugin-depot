import re
import tomllib
from pathlib import Path

import pytest
from pants.engine.addresses import Address
from pants.engine.internals.native_engine import EMPTY_SNAPSHOT
from pants.engine.internals.scheduler import ExecutionError
from pants.engine.target import GeneratedSources
from pants.testutil.rule_runner import RuleRunner
from pants.util.contextutil import environment_as

from vcs_versioning_pants_plugin.codegen import GenerateScmVersionRequest, render_vcs_versioning_config
from vcs_versioning_pants_plugin.target_types import DEFAULT_TAG_REGEX, ScmVersionTarget
from vcs_versioning_pants_plugin_tests.conftest import GitRepo, generate, scm_version_build

# --------------------------------------------------------------------------------------
# Synthetic config rendering (no engine)
# --------------------------------------------------------------------------------------


def _target(**fields: str) -> ScmVersionTarget:
    values = {"generate_to": "src/pkg/version.py", "template": "{version}", **fields}
    return ScmVersionTarget(values, Address("src/pkg", target_name="scm-version"))


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
# Running vcs-versioning against a git repository (network: builds the tool venv)
# --------------------------------------------------------------------------------------


def test_tag_prefix_selects_each_packages_own_tag(scm_rule_runner: RuleRunner, git_repo: GitRepo) -> None:
    git_repo.commit("Add project files.")
    git_repo.tag("alpha-plugin-v1.2.3")
    git_repo.tag("beta-plugin-v4.5.6")
    scm_rule_runner.write_files(
        {
            "src/alpha/BUILD": scm_version_build("alpha", tag_prefix="alpha-plugin-v"),
            "src/beta/BUILD": scm_version_build("beta", tag_prefix="beta-plugin-v"),
        }
    )

    assert generate(scm_rule_runner, git_repo, Address("src/alpha", target_name="alpha")) == '__version__ = "1.2.3"\n'
    assert generate(scm_rule_runner, git_repo, Address("src/beta", target_name="beta")) == '__version__ = "4.5.6"\n'


def test_commits_after_the_tag_yield_a_dev_version(scm_rule_runner: RuleRunner, git_repo: GitRepo) -> None:
    git_repo.commit("Add project files.")
    git_repo.tag("alpha-plugin-v1.2.3")
    git_repo.tag("beta-plugin-v9.9.9")
    sha = git_repo.commit("Another change.")
    scm_rule_runner.write_files({"src/alpha/BUILD": scm_version_build("alpha", tag_prefix="alpha-plugin-v")})

    generated = generate(scm_rule_runner, git_repo, Address("src/alpha", target_name="alpha"))

    assert re.fullmatch(rf'__version__ = "1\.2\.4\.dev1\+g{sha}[0-9a-f]*"\n', generated), generated


def test_no_tag_with_the_prefix_falls_back_instead_of_failing(scm_rule_runner: RuleRunner, git_repo: GitRepo) -> None:
    sha = git_repo.commit("Add project files.")
    git_repo.tag("other-plugin-v9.9.9")
    scm_rule_runner.write_files({"src/alpha/BUILD": scm_version_build("alpha", tag_prefix="alpha-plugin-v")})

    generated = generate(scm_rule_runner, git_repo, Address("src/alpha", target_name="alpha"))

    assert re.fullmatch(rf'__version__ = "0\.1\.dev1\+g{sha}[0-9a-f]*"\n', generated), generated


@pytest.mark.parametrize(
    ("tag_regex", "tag", "expected_version"),
    [
        # The default regex, as Pants' `vcs_version` tests exercise it.
        (None, "v11.22.33", "11.22.33"),
        (None, "release-v11.22.33", "11.22.33"),
        (None, "1.2.3", "1.2.3"),
        (None, "v1.0.0-rc.1", "1.0.0rc1"),
        (r"^version_(?P<version>.*)$", "version_11.22.33", "11.22.33"),
    ],
)
def test_tag_regex_without_a_prefix(
    tag_regex: str | None, tag: str, expected_version: str, scm_rule_runner: RuleRunner, git_repo: GitRepo
) -> None:
    git_repo.commit("Add project files.")
    git_repo.tag(tag)
    fields = {} if tag_regex is None else {"tag_regex": tag_regex}
    scm_rule_runner.write_files({"src/pkg/BUILD": scm_version_build("pkg", **fields)})

    generated = generate(scm_rule_runner, git_repo, Address("src/pkg", target_name="pkg"))

    assert generated == f'__version__ = "{expected_version}"\n'


def test_no_git_worktree_is_an_error(scm_rule_runner: RuleRunner, tmp_path: Path) -> None:
    scm_rule_runner.write_files({"src/pkg/BUILD": scm_version_build("pkg")})
    target = scm_rule_runner.get_target(Address("src/pkg", target_name="pkg"))
    request = GenerateScmVersionRequest(EMPTY_SNAPSHOT, target)

    with (
        environment_as(GIT_DIR=str(tmp_path / "no-such-repo"), GIT_CONFIG_GLOBAL="/dev/null"),
        pytest.raises(ExecutionError, match="Cannot determine the version"),
    ):
        scm_rule_runner.request(GeneratedSources, [request])
