from pants.backend.python import target_types_rules
from pants.testutil.rule_runner import RuleRunner
from pants.vcs import git

from vcs_versioning_pants_plugin import register


def test_backend_registers_with_the_engine() -> None:
    # The codegen rule builds a pex and inspects git, which `pants.backend.python` and Pants' core provide in
    # a real run; a `RuleRunner` only registers what it is given.
    rule_runner = RuleRunner(
        rules=[*register.rules(), *target_types_rules.rules(), *git.rules()], target_types=register.target_types()
    )

    assert rule_runner.build_root
