from textwrap import dedent

import pytest
from pants.backend.python import target_types_rules
from pants.backend.python.target_types import (
    PythonSourcesGeneratorTarget,
    PythonSourceTarget,
    PythonTestsGeneratorTarget,
    PythonTestTarget,
    PythonTestUtilsGeneratorTarget,
)
from pants.engine.addresses import Address
from pants.testutil.rule_runner import RuleRunner

from pants_plugin_developer_utils.testing_utils import RuleRunnerFactory
from ty_pants_plugin import skip_fields
from ty_pants_plugin.check import TyFieldSet
from ty_pants_plugin.skip_fields import SkipTyField


@pytest.fixture(scope="function")
def skip_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:
    return rule_runner_factory(
        rules=[*skip_fields.rules(), *target_types_rules.rules()],
        target_types=[
            PythonSourcesGeneratorTarget,
            PythonSourceTarget,
            PythonTestsGeneratorTarget,
            PythonTestTarget,
            PythonTestUtilsGeneratorTarget,
        ],
    )


@pytest.mark.parametrize(
    ("target_alias", "source_name"),
    [("python_sources", "app.py"), ("python_tests", "app_test.py"), ("python_test_utils", "conftest.py")],
)
def test_generator_targets_accept_skip_ty(skip_rule_runner: RuleRunner, target_alias: str, source_name: str) -> None:
    skip_rule_runner.write_files(
        {
            "project/BUILD": dedent(
                f"""\
                {target_alias}(name="skipped", skip_ty=True)
                {target_alias}(name="checked")
                """
            ),
            f"project/{source_name}": "",
        }
    )

    skipped = skip_rule_runner.get_target(Address("project", target_name="skipped", relative_file_path=source_name))
    checked = skip_rule_runner.get_target(Address("project", target_name="checked", relative_file_path=source_name))

    assert skipped.get(SkipTyField).value is True
    assert TyFieldSet.opt_out(skipped) is True
    assert not TyFieldSet.is_applicable(skipped)
    assert checked.get(SkipTyField).value is False
    assert TyFieldSet.opt_out(checked) is False
    assert TyFieldSet.is_applicable(checked)


@pytest.mark.parametrize("target_alias", ["python_source", "python_test"])
def test_single_file_targets_accept_skip_ty(skip_rule_runner: RuleRunner, target_alias: str) -> None:
    skip_rule_runner.write_files(
        {"project/BUILD": f'{target_alias}(name="skipped", source="app.py", skip_ty=True)\n', "project/app.py": ""}
    )

    skipped = skip_rule_runner.get_target(Address("project", target_name="skipped"))

    assert skipped.get(SkipTyField).value is True
    assert TyFieldSet.opt_out(skipped) is True
    assert not TyFieldSet.is_applicable(skipped)
