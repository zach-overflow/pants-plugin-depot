from collections.abc import Iterable

import pytest
from pants.engine.fs import PathGlobs, Snapshot
from pants.engine.process import FallibleProcessResult, Process
from pants.testutil.rule_runner import RuleRunner, run_rule_with_mocks

from typos_pants_plugin.goals.common import (
    TOOL_INPUT_DIR,
    TyposMode,
    TyposPartitionRequest,
    TyposProcessRequest,
    generate_argv,
    partition_typos_inputs,
)
from typos_pants_plugin_tests.conftest import TyposFactory, read_digest

# --------------------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("skip", "glob_pattern", "files", "expected"),
    [
        (False, ["**/*"], (), []),
        (
            False,
            ["**/*"],
            ("README.md", "src/app.py", ".github/ci.yml"),
            [(".github/ci.yml", "README.md", "src/app.py")],
        ),
        (False, ["**/*.md"], ("README.md", "src/app.py", "docs/guide.md"), [("README.md", "docs/guide.md")]),
        (False, ["**/*", "!**/*.json", "!3rdparty/**"], ("a.md", "lock.json", "3rdparty/x.md"), [("a.md",)]),
        (False, ["**/*", "!**/*.md"], ("a.md", "b.md"), []),
        (False, [r"\\!literal.md", "**/*.py"], ("!literal.md", "app.py"), [("!literal.md", "app.py")]),
        (True, ["**/*"], (), []),
        (True, ["**/*"], ("README.md", "src/app.py"), []),
    ],
)
def test_partition_typos_inputs(
    *,
    skip: bool,
    glob_pattern: list[str],
    files: Iterable[str],
    expected: list[tuple[str, ...]],
    typos_factory: TyposFactory,
) -> None:
    typos = typos_factory(skip=skip, glob_pattern=glob_pattern)

    actual = run_rule_with_mocks(partition_typos_inputs, rule_args=[TyposPartitionRequest(tuple(files)), typos])

    # `Partitions` are not comparable: each single partition holds a distinct `_EmptyMetadata` instance.
    assert [partition.elements for partition in actual] == expected


def test_generate_argv_lint_minimal(typos_factory: TyposFactory) -> None:
    argv = generate_argv(typos_factory(), exe="./typos", mode=TyposMode.LINT, files=("a.md", "b.py"))

    assert argv == ("./typos", "--force-exclude", "a.md", "b.py")


def test_generate_argv_fix_minimal(typos_factory: TyposFactory) -> None:
    argv = generate_argv(typos_factory(), exe="./typos", mode=TyposMode.FIX, files=("a.md",))

    assert argv == ("./typos", "--force-exclude", "--write-changes", "--no-check-filenames", "a.md")


def test_generate_argv_full(typos_factory: TyposFactory) -> None:
    typos = typos_factory(config="cfg/typos.toml", args=["--locale", "en-gb", "--format", "brief"])

    argv = generate_argv(typos, exe="tool/typos", mode=TyposMode.FIX, files=("src/a.py",))

    assert argv == (
        "tool/typos",
        "--force-exclude",
        "--config",
        "cfg/typos.toml",
        "--isolated",
        "--write-changes",
        "--no-check-filenames",
        "--locale",
        "en-gb",
        "--format",
        "brief",
        "src/a.py",
    )


def test_generate_argv_without_discovery_isolates(typos_factory: TyposFactory) -> None:
    argv = generate_argv(typos_factory(config_discovery=False), exe="./typos", mode=TyposMode.LINT, files=("a.md",))

    assert argv == ("./typos", "--force-exclude", "--isolated", "a.md")


# --------------------------------------------------------------------------------------
# Process setup: downloads `typos` over the network.
# --------------------------------------------------------------------------------------


def _snapshot(rule_runner: RuleRunner, files: dict[str, str]) -> Snapshot:
    rule_runner.write_files(files)
    return rule_runner.request(Snapshot, [PathGlobs(files)])


@pytest.mark.parametrize("mode", list(TyposMode))
def test_setup_typos_process(typos_rule_runner: RuleRunner, mode: TyposMode) -> None:
    snapshot = _snapshot(typos_rule_runner, {"docs/a.md": "Teh fox\n", "src/b.py": "x = 1\n"})

    process = typos_rule_runner.request(
        Process, [TyposProcessRequest(snapshot=snapshot, files=snapshot.files, mode=mode)]
    )

    assert process.argv[0] == f"{TOOL_INPUT_DIR}/./typos"
    assert process.argv[-2:] == ("docs/a.md", "src/b.py")
    assert set(process.immutable_input_digests) == {TOOL_INPUT_DIR}
    assert process.output_files == (("docs/a.md", "src/b.py") if mode is TyposMode.FIX else ())
    assert process.description == f"Run typos{' --write-changes' if mode is TyposMode.FIX else ''} on 2 files."
    assert set(read_digest(typos_rule_runner, process.input_digest)) == {"docs/a.md", "src/b.py"}


def test_setup_typos_process_includes_discovered_config_files(typos_rule_runner: RuleRunner) -> None:
    """Config files in the checked files' directories and their ancestors ride along; unrelated ones do not."""
    files = {
        "_typos.toml": "[files]\n",
        "docs/pyproject.toml": '[tool.typos.default.extend-words]\nteh = "teh"\n',
        "docs/guides/.typos.toml": "[default]\n",
        "docs/guides/a.md": "Teh fox\n",
        "other/typos.toml": "[default]\n",
        "src/pyproject.toml": '[project]\nname = "no-typos-table"\n',
        "src/b.py": "x = 1\n",
    }
    typos_rule_runner.write_files(files)
    snapshot = typos_rule_runner.request(Snapshot, [PathGlobs(["docs/guides/a.md", "src/b.py"])])

    process = typos_rule_runner.request(
        Process, [TyposProcessRequest(snapshot=snapshot, files=snapshot.files, mode=TyposMode.LINT)]
    )

    assert set(read_digest(typos_rule_runner, process.input_digest)) == {
        "_typos.toml",
        "docs/pyproject.toml",
        "docs/guides/.typos.toml",
        "docs/guides/a.md",
        "src/b.py",
    }


def test_setup_typos_process_with_explicit_config(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-config=configs/typos.toml"])
    snapshot = _snapshot(
        typos_rule_runner, {"configs/typos.toml": "[default]\n", "_typos.toml": "[default]\n", "a.md": "Teh\n"}
    )

    process = typos_rule_runner.request(
        Process, [TyposProcessRequest(snapshot=snapshot, files=("a.md",), mode=TyposMode.LINT)]
    )

    assert process.argv[1:] == ("--force-exclude", "--config", "configs/typos.toml", "--isolated", "a.md")
    # `_typos.toml` is only present because it was part of the request snapshot, not because of discovery.
    assert set(read_digest(typos_rule_runner, process.input_digest)) == {"configs/typos.toml", "_typos.toml", "a.md"}


def test_setup_typos_process_runs(typos_rule_runner: RuleRunner) -> None:
    snapshot = _snapshot(typos_rule_runner, {"a.md": "Teh quick brown fox\n"})
    process = typos_rule_runner.request(
        Process, [TyposProcessRequest(snapshot=snapshot, files=snapshot.files, mode=TyposMode.LINT)]
    )

    result = typos_rule_runner.request(FallibleProcessResult, [process])

    assert result.exit_code == 2
    assert "`Teh` should be `The`" in result.stdout.decode()
    assert "a.md:1:1" in result.stdout.decode()
