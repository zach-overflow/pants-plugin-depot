from pants.backend.python.dependency_inference.module_mapper import (
    FirstPartyPythonMappingImpl,
    ModuleProvider,
    ModuleProviderType,
)
from pants.engine.addresses import Address
from pants.testutil.rule_runner import RuleRunner

from setuptools_scm_pants_plugin.module_mapper import ScmVersionMappingMarker
from setuptools_scm_pants_plugin_tests.conftest import scm_version_build


def test_generated_module_is_mapped_for_dependency_inference(scm_rule_runner: RuleRunner) -> None:
    scm_rule_runner.write_files(
        {
            "src/pkg/BUILD": scm_version_build("pkg"),
            "src/other/BUILD": 'scm_version(name="data", generate_to="src/other/version.txt", template="{version}")',
        }
    )

    mapping = scm_rule_runner.request(FirstPartyPythonMappingImpl, [ScmVersionMappingMarker()])

    # Only `.py` outputs become importable modules; the source root `src` is stripped.
    assert mapping == FirstPartyPythonMappingImpl.create(
        {
            "python-default": {
                "pkg.version": [ModuleProvider(Address("src/pkg", target_name="pkg"), ModuleProviderType.IMPL)]
            }
        }
    )
