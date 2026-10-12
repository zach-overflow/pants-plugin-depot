from textwrap import dedent

import pytest
from pants.core.goals.fix import FixResult
from pants.engine.fs import EMPTY_SNAPSHOT
from pants.engine.internals.scheduler import ExecutionError
from pants.testutil.rule_runner import RuleRunner

from typos_pants_plugin.goals.fix import TyposFixRequest
from typos_pants_plugin_tests.conftest import read_digest, run_fix

TYPO_MD = "Teh quick brown fox.\nA sentance with a mistake.\n"
FIXED_MD = "The quick brown fox.\nA sentence with a mistake.\n"
TYPO_PY = dedent(
    """\
    def helo():
        return "wrold"
    """
)
FIXED_PY = dedent(
    """\
    def hello():
        return "world"
    """
)
CLEAN = "Nothing to see here.\n"


def test_fixes_typos(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files({"docs/a.md": TYPO_MD, "src/b.py": TYPO_PY, "clean.txt": CLEAN})

    [result] = run_fix(typos_rule_runner, ["docs/a.md", "src/b.py", "clean.txt"])

    assert result.did_change
    assert result.tool_name == "typos"
    assert result.input.files == ("clean.txt", "docs/a.md", "src/b.py")
    assert read_digest(typos_rule_runner, result.output.digest) == {
        "clean.txt": CLEAN,
        "docs/a.md": FIXED_MD,
        "src/b.py": FIXED_PY,
    }


def test_no_change_on_clean_files(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files({"clean.txt": CLEAN})

    [result] = run_fix(typos_rule_runner, ["clean.txt"])

    assert not result.did_change
    assert result.output == result.input


def test_ambiguous_typos_are_left_alone(typos_rule_runner: RuleRunner) -> None:
    """`typos` offers several corrections for `ba`, so it only writes the unambiguous `teh`."""
    typos_rule_runner.write_files({"a.md": "teh ba\n"})

    [result] = run_fix(typos_rule_runner, ["a.md"])

    assert result.did_change
    assert read_digest(typos_rule_runner, result.output.digest) == {"a.md": "the ba\n"}
    assert "`ba` should be `by`, `be`" in result.stdout


def test_misspelled_file_names_are_not_renamed(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files({"recieve.md": TYPO_MD})

    [result] = run_fix(typos_rule_runner, ["recieve.md"])

    assert result.did_change
    assert read_digest(typos_rule_runner, result.output.digest) == {"recieve.md": FIXED_MD}


def test_discovered_config_applies_to_files_beneath_it(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files(
        {"docs/_typos.toml": '[default.extend-words]\nteh = "teh"\n', "docs/a.md": "teh\n", "src/b.md": "teh\n"}
    )

    [result] = run_fix(typos_rule_runner, ["docs/a.md", "src/b.md"])

    assert read_digest(typos_rule_runner, result.output.digest) == {"docs/a.md": "teh\n", "src/b.md": "the\n"}


def test_config_excludes_are_respected(typos_rule_runner: RuleRunner) -> None:
    """`--force-exclude` applies `files.extend-exclude` to the explicitly listed files; they still come back."""
    typos_rule_runner.write_files(
        {"_typos.toml": '[files]\nextend-exclude = ["vendored/"]\n', "vendored/a.md": "teh\n", "b.md": "teh\n"}
    )

    [result] = run_fix(typos_rule_runner, ["vendored/a.md", "b.md"])

    assert read_digest(typos_rule_runner, result.output.digest) == {"vendored/a.md": "teh\n", "b.md": "the\n"}


def test_explicit_config(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-config=configs/typos.toml"])
    typos_rule_runner.write_files(
        {
            "configs/typos.toml": '[default.extend-words]\nteh = "teh"\n',
            "_typos.toml": '[default.extend-words]\nfox = "fox"\n',
            "a.md": "teh fox\n",
        }
    )

    [result] = run_fix(typos_rule_runner, ["a.md"])

    assert not result.did_change


def test_args_are_passed_through(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-args=['--exclude', '*.md']"])
    typos_rule_runner.write_files({"a.md": "teh\n", "b.txt": "teh\n"})

    [result] = run_fix(typos_rule_runner, ["a.md", "b.txt"])

    assert read_digest(typos_rule_runner, result.output.digest) == {"a.md": "teh\n", "b.txt": "the\n"}


def test_glob_pattern_selects_the_files(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-glob-pattern=['**/*.md']"])
    typos_rule_runner.write_files({"a.md": "teh\n", "b.txt": "teh\n"})

    [result] = run_fix(typos_rule_runner, ["a.md", "b.txt"])

    assert result.input.files == ("a.md",)
    assert read_digest(typos_rule_runner, result.output.digest) == {"a.md": "the\n"}


def test_skip_option(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-skip"])
    typos_rule_runner.write_files({"a.md": "teh\n"})

    assert run_fix(typos_rule_runner, ["a.md"]) == []


def test_usage_errors_fail_the_goal(typos_rule_runner: RuleRunner) -> None:
    """A file that is not in the sandbox makes `typos` exit 64; `fix` MUST NOT swallow that."""
    batch = TyposFixRequest.Batch(TyposFixRequest.tool_name, ("missing.md",), None, EMPTY_SNAPSHOT)

    with pytest.raises(ExecutionError, match="exit code 64"):
        typos_rule_runner.request(FixResult, [batch])
