from collections.abc import Iterable
from textwrap import dedent

import pytest
from pants.core.goals.check import CheckResult, CheckResults
from pants.engine.addresses import Address
from pants.engine.target import Target
from pants.testutil.rule_runner import RuleRunner

from ty_pants_plugin.check import TyFieldSet, TyPartitions, TyRequest, generate_argv, python_version_configured
from ty_pants_plugin_tests.conftest import make_ty, set_ty_options

GOOD_FILE = dedent(
    """\
    def add(x: int, y: int) -> int:
        return x + y


    result: int = add(1, 2)
    """
)

BAD_FILE = dedent(
    """\
    def add(x: int, y: int) -> int:
        return x + y


    result: str = add(1, 2)
    """
)


def _targets(rule_runner: RuleRunner, *addresses: Address) -> list[Target]:
    return [rule_runner.get_target(address) for address in addresses]


def _run_ty(rule_runner: RuleRunner, targets: Iterable[Target]) -> tuple[CheckResult, ...]:
    field_sets = [TyFieldSet.create(target) for target in targets]
    return rule_runner.request(CheckResults, [TyRequest(field_sets)]).results


# --------------------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------------------


def test_generate_argv_minimal() -> None:
    argv = generate_argv(
        make_ty(), exe="./ty-x/ty", venv_dir="/caches/venv", source_roots=(), python_version=None, files=("a.py",)
    )

    assert argv == ("./ty-x/ty", "check", "--color=always", "--python=/caches/venv", "a.py")


def test_generate_argv_full() -> None:
    ty = make_ty(args=["--output-format", "concise"], config="cfg/ty.toml")

    argv = generate_argv(
        ty,
        exe="./ty-x/ty",
        venv_dir="/caches/venv",
        source_roots=("src/python", "."),
        python_version="3.12",
        files=("src/python/a.py", "b.py"),
    )

    assert argv == (
        "./ty-x/ty",
        "check",
        "--color=always",
        "--python=/caches/venv",
        "--extra-search-path=src/python",
        "--extra-search-path=.",
        "--python-version=3.12",
        "--config-file=cfg/ty.toml",
        "--output-format",
        "concise",
        "src/python/a.py",
        "b.py",
    )


@pytest.mark.parametrize(
    ("args", "config_contents", "expected"),
    [
        ([], [], False),
        (["--output-format=concise"], [b"[rules]\nunused-ignore-comment = 'warn'\n"], False),
        (["--python-version=3.12"], [], True),
        (["--python-version", "3.12"], [], True),
        (["--target-version=3.12"], [], True),
        (["--config", "environment.python-version='3.12'"], [], True),
        ([], [b"[environment]\npython-version = '3.12'\n"], True),
        ([], [b"[tool.ty.environment]\npython-version = '3.12'\n"], True),
    ],
)
def test_python_version_configured(args: list[str], config_contents: list[bytes], expected: bool) -> None:
    assert python_version_configured(make_ty(args=args), config_contents) is expected


# --------------------------------------------------------------------------------------
# Partitioning
# --------------------------------------------------------------------------------------


def test_partitions_by_interpreter_constraints(ty_rule_runner: RuleRunner) -> None:
    ty_rule_runner.write_files(
        {
            "project/BUILD": dedent(
                """\
                python_sources(name="py314", sources=["a.py"], interpreter_constraints=["CPython==3.14.*"])
                python_sources(name="py312", sources=["b.py"], interpreter_constraints=["CPython==3.12.*"])
                python_sources(name="also314", sources=["c.py"], interpreter_constraints=["CPython==3.14.*"])
                """
            ),
            "project/a.py": "",
            "project/b.py": "",
            "project/c.py": "",
        }
    )
    targets = _targets(
        ty_rule_runner,
        Address("project", target_name="py314", relative_file_path="a.py"),
        Address("project", target_name="py312", relative_file_path="b.py"),
        Address("project", target_name="also314", relative_file_path="c.py"),
    )

    partitions = ty_rule_runner.request(TyPartitions, [TyRequest(TyFieldSet.create(t) for t in targets)])

    assert {
        partition.description(): sorted(str(fs.address) for fs in partition.field_sets) for partition in partitions
    } == {
        "['CPython==3.12.*']": ["project/b.py:py312"],
        "['CPython==3.14.*']": ["project/a.py:py314", "project/c.py:also314"],
    }


# --------------------------------------------------------------------------------------
# Integration: these download `ty` and resolve requirements over the network.
# --------------------------------------------------------------------------------------


def test_passing_source(ty_rule_runner: RuleRunner) -> None:
    ty_rule_runner.write_files({"project/BUILD": "python_sources()\n", "project/good.py": GOOD_FILE})
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="good.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 0, result.stdout + result.stderr
    assert result.partition_description == "['CPython<3.15,>=3.14']"


def test_failing_source(ty_rule_runner: RuleRunner) -> None:
    ty_rule_runner.write_files({"project/BUILD": "python_sources()\n", "project/bad.py": BAD_FILE})
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="bad.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 1
    assert "invalid-assignment" in result.stdout
    assert "project/bad.py" in result.stdout


def test_multiple_targets_share_one_run(ty_rule_runner: RuleRunner) -> None:
    ty_rule_runner.write_files(
        {"project/BUILD": "python_sources()\n", "project/good.py": GOOD_FILE, "project/bad.py": BAD_FILE}
    )
    targets = _targets(
        ty_rule_runner,
        Address("project", relative_file_path="good.py"),
        Address("project", relative_file_path="bad.py"),
    )

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 1
    assert "project/bad.py" in result.stdout
    assert "project/good.py" not in result.stdout


def test_only_requested_files_are_reported(ty_rule_runner: RuleRunner) -> None:
    """A dependency is present so imports resolve, but its own diagnostics are not reported."""
    ty_rule_runner.write_files(
        {
            "project/BUILD": dedent(
                """\
                python_sources(name="app", sources=["app.py"], dependencies=[":helpers"])
                python_sources(name="helpers", sources=["helpers.py"])
                """
            ),
            "project/app.py": "from project.helpers import add\n\nresult: int = add(1, 2)\n",
            "project/helpers.py": BAD_FILE,
        }
    )
    targets = _targets(ty_rule_runner, Address("project", target_name="app", relative_file_path="app.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 0, result.stdout + result.stderr


def test_first_party_imports_resolve_across_source_roots(ty_rule_runner: RuleRunner) -> None:
    set_ty_options(ty_rule_runner, "--source-root-patterns=['src/python', 'lib']")
    ty_rule_runner.write_files(
        {
            "src/python/app/BUILD": 'python_sources(dependencies=["lib/shared"])\n',
            "src/python/app/main.py": "from shared.math import add\n\nresult: int = add(1, 2)\n",
            "lib/shared/BUILD": "python_sources()\n",
            "lib/shared/__init__.py": "",
            "lib/shared/math.py": GOOD_FILE,
        }
    )
    targets = _targets(ty_rule_runner, Address("src/python/app", relative_file_path="main.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 0, result.stdout + result.stderr


def test_unresolved_first_party_import_fails(ty_rule_runner: RuleRunner) -> None:
    ty_rule_runner.write_files(
        {
            "project/BUILD": "python_sources()\n",
            "project/app.py": "from project.missing import add\n\nresult: int = add(1, 2)\n",
        }
    )
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="app.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 1
    assert "unresolved-import" in result.stdout


@pytest.mark.parametrize("has_requirement", [True, False])
def test_third_party_imports_resolve_from_the_requirements_venv(
    ty_rule_runner: RuleRunner, has_requirement: bool
) -> None:
    # Without inference the `python_requirement` is only a dependency when `dependencies` names it.
    set_ty_options(ty_rule_runner, "--no-python-infer-imports")
    dependencies = '["//:packaging"]' if has_requirement else "[]"
    ty_rule_runner.write_files(
        {
            "BUILD": 'python_requirement(name="packaging", requirements=["packaging==25.0"])\n',
            "project/BUILD": f"python_sources(dependencies={dependencies})\n",
            "project/app.py": 'from packaging.version import Version\n\nversion: Version = Version("1.0")\n',
        }
    )
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="app.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    if has_requirement:
        assert result.exit_code == 0, result.stdout + result.stderr
    else:
        assert result.exit_code == 1
        assert "unresolved-import" in result.stdout


@pytest.mark.parametrize(
    ("config_path", "config_contents"),
    [
        ("ty.toml", '[rules]\ninvalid-assignment = "ignore"\n'),
        ("pyproject.toml", '[tool.ty.rules]\ninvalid-assignment = "ignore"\n'),
    ],
)
def test_config_discovery(ty_rule_runner: RuleRunner, config_path: str, config_contents: str) -> None:
    ty_rule_runner.write_files(
        {config_path: config_contents, "project/BUILD": "python_sources()\n", "project/bad.py": BAD_FILE}
    )
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="bad.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 0, result.stdout + result.stderr


def test_explicit_config(ty_rule_runner: RuleRunner) -> None:
    set_ty_options(ty_rule_runner, "--ty-config=configs/ty.toml")
    ty_rule_runner.write_files(
        {
            "configs/ty.toml": '[rules]\ninvalid-assignment = "ignore"\n',
            "project/BUILD": "python_sources()\n",
            "project/bad.py": BAD_FILE,
        }
    )
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="bad.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 0, result.stdout + result.stderr


def test_args_are_passed_through(ty_rule_runner: RuleRunner) -> None:
    set_ty_options(ty_rule_runner, "--ty-args=['--exit-zero']")
    ty_rule_runner.write_files({"project/BUILD": "python_sources()\n", "project/bad.py": BAD_FILE})
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="bad.py"))

    [result] = _run_ty(ty_rule_runner, targets)

    assert result.exit_code == 0
    assert "invalid-assignment" in result.stdout


def test_skip_option(ty_rule_runner: RuleRunner) -> None:
    set_ty_options(ty_rule_runner, "--ty-skip")
    ty_rule_runner.write_files({"project/BUILD": "python_sources()\n", "project/bad.py": BAD_FILE})
    targets = _targets(ty_rule_runner, Address("project", relative_file_path="bad.py"))

    results = _run_ty(ty_rule_runner, targets)

    assert results == ()
