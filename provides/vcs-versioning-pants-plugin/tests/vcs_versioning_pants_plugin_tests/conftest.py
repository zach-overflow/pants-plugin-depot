import pytest
from pants.backend.python.dependency_inference.module_mapper import FirstPartyPythonMappingImpl
from pants.testutil.rule_runner import QueryRule, RuleRunner

from pants_plugin_developer_utils.testing_utils import (
    RuleRunnerFactory,
    rule_runner_factory,  # ruff: ignore[F401]
)
from vcs_versioning_pants_plugin import module_mapper
from vcs_versioning_pants_plugin.module_mapper import ScmVersionMappingMarker
from vcs_versioning_pants_plugin.subsystem import VcsVersioning
from vcs_versioning_pants_plugin.target_types import ScmVersionFileTarget, ScmVersionTarget

TOOL_INTERPRETER_CONSTRAINTS = ("CPython==3.14.*",)
"""The `[vcs-versioning].interpreter_constraints` that `scm_rule_runner` sets."""


@pytest.fixture(scope="function")
def scm_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:  # ruff: ignore[F811]
    """Engine-backed runner for what needs neither git nor the network: option parsing and the module mapping."""
    rule_runner = rule_runner_factory(
        rules=[
            *module_mapper.rules(),
            *VcsVersioning.rules(),
            QueryRule(FirstPartyPythonMappingImpl, [ScmVersionMappingMarker]),
            QueryRule(VcsVersioning, []),
        ],
        target_types=[ScmVersionTarget, ScmVersionFileTarget],
    )
    rule_runner.set_options(
        [
            "--source-root-patterns=['src']",
            # The module mapping keys modules by resolve name, which only exists with resolves enabled.
            "--python-enable-resolves=True",
            # Explicit, so `get_lockfile_interpreter_constraints` answers from the option instead of loading the
            # bundled lockfile through the engine.
            f"--vcs-versioning-interpreter-constraints={list(TOOL_INTERPRETER_CONSTRAINTS)!r}",
        ]
    )
    return rule_runner


@pytest.fixture(scope="function")
def vcs_versioning(scm_rule_runner: RuleRunner) -> VcsVersioning:
    """The `[vcs-versioning]` subsystem as `scm_rule_runner` configures it."""
    return scm_rule_runner.request(VcsVersioning, [])


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
