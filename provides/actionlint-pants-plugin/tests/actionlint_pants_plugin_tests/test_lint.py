from textwrap import dedent

from pants.testutil.rule_runner import RuleRunner

from actionlint_pants_plugin.goals.lint import generate_argv
from actionlint_pants_plugin_tests.conftest import WORKFLOWS_DIR, ActionlintFactory, run_lint, workflow_address

GENERATOR_BUILD = "github_workflow_sources()\n"

VALID_WORKFLOW = dedent(
    """\
    on: push
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - run: echo "hello"
    """
)

MISSING_RUNS_ON_WORKFLOW = dedent(
    """\
    on: push
    jobs:
      build:
        steps:
          - run: echo "hello"
    """
)

UNQUOTED_VARIABLE_WORKFLOW = dedent(
    """\
    on: push
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - run: echo $GREETING
    """
)

SELF_HOSTED_RUNNER_WORKFLOW = dedent(
    """\
    on: push
    jobs:
      build:
        runs-on: my-runner
        steps:
          - run: echo "hello"
    """
)

SELF_HOSTED_RUNNER_CONFIG = dedent(
    """\
    self-hosted-runner:
      labels:
        - my-runner
    """
)

LOCAL_ACTION_WORKFLOW = dedent(
    """\
    on: push
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - uses: ./.github/actions/hello
            with:
              nonexistent: value
    """
)

LOCAL_ACTION_METADATA = dedent(
    """\
    name: hello
    description: Says hello.
    inputs:
      name:
        description: Who to greet.
        default: world
    runs:
      using: composite
      steps:
        - run: echo "hello ${{ inputs.name }}"
          shell: bash
    """
)


def _workflow_files(**workflows: str) -> dict[str, str]:
    return {
        f"{WORKFLOWS_DIR}/BUILD": GENERATOR_BUILD,
        **{f"{WORKFLOWS_DIR}/{name}": body for name, body in workflows.items()},
    }


# --------------------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------------------


def test_generate_argv_minimal(actionlint_factory: ActionlintFactory) -> None:
    argv = generate_argv(
        actionlint_factory(), exe="./actionlint", shellcheck_exe="tool/shellcheck", files=("b.yml", "a.yml")
    )

    assert argv == ("./actionlint", "-color", "-pyflakes=", "-shellcheck=tool/shellcheck", "a.yml", "b.yml")


def test_generate_argv_without_shellcheck(actionlint_factory: ActionlintFactory) -> None:
    argv = generate_argv(actionlint_factory(), exe="./actionlint", shellcheck_exe=None, files=("a.yml",))

    assert argv == ("./actionlint", "-color", "-pyflakes=", "-shellcheck=", "a.yml")


def test_generate_argv_full(actionlint_factory: ActionlintFactory) -> None:
    actionlint = actionlint_factory(config="cfg/actionlint.yaml", args=["-oneline", "-ignore", "SC2086:.+"])

    argv = generate_argv(actionlint, exe="tool/actionlint", shellcheck_exe="tool/shellcheck", files=("a.yml",))

    assert argv == (
        "tool/actionlint",
        "-color",
        "-pyflakes=",
        "-shellcheck=tool/shellcheck",
        "-config-file",
        "cfg/actionlint.yaml",
        "-oneline",
        "-ignore",
        "SC2086:.+",
        "a.yml",
    )


# --------------------------------------------------------------------------------------
# Integration: these download `actionlint` and `shellcheck` over the network.
# --------------------------------------------------------------------------------------


def test_passes_on_valid_workflow(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(_workflow_files(**{"ci.yml": VALID_WORKFLOW}))

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.linter_name == "actionlint"
    assert result.partition_description is None
    assert result.stdout == ""


def test_reports_workflow_problems(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(_workflow_files(**{"ci.yml": MISSING_RUNS_ON_WORKFLOW}))

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 1
    assert '"runs-on" section is missing in job "build"' in result.stdout


def test_multiple_workflows_share_one_run(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(
        _workflow_files(**{"ok.yml": VALID_WORKFLOW, "bad.yml": MISSING_RUNS_ON_WORKFLOW})
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ok.yml"), workflow_address("bad.yml")])

    assert result.exit_code == 1
    assert "bad.yml" in result.stdout
    assert "ok.yml" not in result.stdout


def test_shellcheck_reports_run_step_issues(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(_workflow_files(**{"ci.yml": UNQUOTED_VARIABLE_WORKFLOW}))

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 1
    assert "SC2086" in result.stdout
    assert "[shellcheck]" in result.stdout


def test_shellcheck_can_be_disabled(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.set_options(["--no-actionlint-shellcheck"])
    actionlint_rule_runner.write_files(_workflow_files(**{"ci.yml": UNQUOTED_VARIABLE_WORKFLOW}))

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 0, result.stdout + result.stderr


def test_args_are_passed_through(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.set_options(["--actionlint-args=['-ignore', 'SC2086:.+']"])
    actionlint_rule_runner.write_files(_workflow_files(**{"ci.yml": UNQUOTED_VARIABLE_WORKFLOW}))

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 0, result.stdout + result.stderr


def test_unknown_runner_label_fails_without_config(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(_workflow_files(**{"ci.yml": SELF_HOSTED_RUNNER_WORKFLOW}))

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 1
    assert 'label "my-runner" is unknown' in result.stdout


def test_discovered_config_applies(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(
        {
            **_workflow_files(**{"ci.yml": SELF_HOSTED_RUNNER_WORKFLOW}),
            ".github/actionlint.yaml": SELF_HOSTED_RUNNER_CONFIG,
        }
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 0, result.stdout + result.stderr


def test_disabled_discovery_ignores_the_config(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.set_options(["--no-actionlint-config-discovery"])
    actionlint_rule_runner.write_files(
        {
            **_workflow_files(**{"ci.yml": SELF_HOSTED_RUNNER_WORKFLOW}),
            ".github/actionlint.yaml": SELF_HOSTED_RUNNER_CONFIG,
        }
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 1
    assert 'label "my-runner" is unknown' in result.stdout


def test_explicit_config_wins_over_the_discovered_one(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.set_options(["--actionlint-config=configs/actionlint.yaml"])
    actionlint_rule_runner.write_files(
        {
            **_workflow_files(**{"ci.yml": SELF_HOSTED_RUNNER_WORKFLOW}),
            "configs/actionlint.yaml": SELF_HOSTED_RUNNER_CONFIG,
            ".github/actionlint.yaml": "self-hosted-runner:\n  labels: []\n",
        }
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 0, result.stdout + result.stderr


def test_config_errors_fail_the_linter(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(
        {**_workflow_files(**{"ci.yml": VALID_WORKFLOW}), ".github/actionlint.yaml": "self-hosted-runner: [\n"}
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 3
    assert "could not parse config file" in result.stderr


def test_dependencies_let_actionlint_validate_local_actions(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(
        {
            f"{WORKFLOWS_DIR}/BUILD": 'github_workflow_sources(dependencies=[".github/actions/hello:action"])\n',
            f"{WORKFLOWS_DIR}/ci.yml": LOCAL_ACTION_WORKFLOW,
            ".github/actions/hello/BUILD": 'files(name="action", sources=["action.yml"])\n',
            ".github/actions/hello/action.yml": LOCAL_ACTION_METADATA,
        }
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 1
    assert 'input "nonexistent" is not defined in action' in result.stdout


def test_local_actions_outside_the_dependencies_are_not_validated(actionlint_rule_runner: RuleRunner) -> None:
    """`actionlint` deliberately ignores a local action it cannot find, so an undeclared one is unchecked."""
    actionlint_rule_runner.write_files(
        {
            **_workflow_files(**{"ci.yml": LOCAL_ACTION_WORKFLOW}),
            ".github/actions/hello/BUILD": 'files(name="action", sources=["action.yml"])\n',
            ".github/actions/hello/action.yml": LOCAL_ACTION_METADATA,
        }
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ci.yml")])

    assert result.exit_code == 0, result.stdout + result.stderr


def test_skip_option(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.set_options(["--actionlint-skip"])
    actionlint_rule_runner.write_files(_workflow_files(**{"ci.yml": MISSING_RUNS_ON_WORKFLOW}))

    assert run_lint(actionlint_rule_runner, [workflow_address("ci.yml")]) == []


def test_skip_field_excludes_the_file(actionlint_rule_runner: RuleRunner) -> None:
    actionlint_rule_runner.write_files(
        {
            f"{WORKFLOWS_DIR}/BUILD": 'github_workflow_sources(overrides={"bad.yml": {"skip_actionlint": True}})\n',
            f"{WORKFLOWS_DIR}/ok.yml": VALID_WORKFLOW,
            f"{WORKFLOWS_DIR}/bad.yml": MISSING_RUNS_ON_WORKFLOW,
        }
    )

    [result] = run_lint(actionlint_rule_runner, [workflow_address("ok.yml"), workflow_address("bad.yml")])

    assert result.exit_code == 0, result.stdout + result.stderr
