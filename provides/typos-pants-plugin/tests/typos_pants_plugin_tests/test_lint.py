from pants.testutil.rule_runner import RuleRunner

from typos_pants_plugin_tests.conftest import run_lint

TYPO_MD = "Teh quick brown fox.\n"


def test_reports_typos(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files({"docs/a.md": TYPO_MD, "clean.txt": "Nothing to see here.\n"})

    [result] = run_lint(typos_rule_runner, ["docs/a.md", "clean.txt"])

    assert result.exit_code == 2
    assert result.linter_name == "typos"
    assert result.partition_description is None
    assert "`Teh` should be `The`" in result.stdout
    assert "docs/a.md:1:1" in result.stdout
    assert "clean.txt" not in result.stdout


def test_passes_on_clean_files(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files({"clean.txt": "Nothing to see here.\n"})

    [result] = run_lint(typos_rule_runner, ["clean.txt"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert not result.stdout


def test_reports_ambiguous_typos_and_file_names(typos_rule_runner: RuleRunner) -> None:
    """Everything `fix` leaves behind is still a lint failure."""
    typos_rule_runner.write_files({"recieve.md": "ba\n"})

    [result] = run_lint(typos_rule_runner, ["recieve.md"])

    assert result.exit_code == 2
    assert "`recieve` should be `receive`" in result.stdout
    assert "`ba` should be `by`, `be`" in result.stdout


def test_args_are_passed_through(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-args=['--format', 'brief']"])
    typos_rule_runner.write_files({"a.md": TYPO_MD})

    [result] = run_lint(typos_rule_runner, ["a.md"])

    assert result.exit_code == 2
    assert result.stdout == "a.md:1:1: error: `Teh` should be `The`\n"


def test_discovered_config_applies_to_files_beneath_it(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files(
        {
            "docs/pyproject.toml": '[tool.typos.default.extend-words]\nteh = "teh"\n',
            "docs/a.md": "teh\n",
            "src/b.md": "teh\n",
        }
    )

    [result] = run_lint(typos_rule_runner, ["docs/a.md", "src/b.md"])

    assert result.exit_code == 2
    assert "src/b.md:1:1" in result.stdout
    assert "docs/a.md" not in result.stdout


def test_disabled_discovery_isolates_typos(typos_rule_runner: RuleRunner) -> None:
    """Without discovery, even a `pyproject.toml` that is itself being checked configures nothing."""
    files = {"pyproject.toml": '[tool.typos.default.extend-words]\nteh = "teh"\n', "a.md": "teh\n"}
    typos_rule_runner.write_files(files)

    [discovered] = run_lint(typos_rule_runner, files)
    typos_rule_runner.set_options(["--no-typos-config-discovery"])
    [isolated] = run_lint(typos_rule_runner, files)

    assert discovered.exit_code == 0, discovered.stdout + discovered.stderr
    assert isolated.exit_code == 2
    assert "a.md:1:1" in isolated.stdout


def test_explicit_config(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-config=configs/typos.toml"])
    typos_rule_runner.write_files(
        {"configs/typos.toml": '[default.extend-words]\nteh = "teh"\n', "_typos.toml": "[default]\n", "a.md": "teh\n"}
    )

    [result] = run_lint(typos_rule_runner, ["a.md"])

    assert result.exit_code == 0, result.stdout + result.stderr


def test_config_errors_fail_the_linter(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.write_files({"_typos.toml": "not = toml = [\n", "a.md": "teh\n"})

    [result] = run_lint(typos_rule_runner, ["a.md"])

    assert result.exit_code == 78
    assert "TOML parse error" in result.stderr


def test_glob_pattern_selects_the_files(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-glob-pattern=['**/*.md']"])
    typos_rule_runner.write_files({"a.md": "teh\n", "b.txt": "teh\n"})

    [result] = run_lint(typos_rule_runner, ["a.md", "b.txt"])

    assert result.exit_code == 2
    assert "a.md:1:1" in result.stdout
    assert "b.txt" not in result.stdout


def test_skip_option(typos_rule_runner: RuleRunner) -> None:
    typos_rule_runner.set_options(["--typos-skip"])
    typos_rule_runner.write_files({"a.md": "teh\n"})

    assert run_lint(typos_rule_runner, ["a.md"]) == []
