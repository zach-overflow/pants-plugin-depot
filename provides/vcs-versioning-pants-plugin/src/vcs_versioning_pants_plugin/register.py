"""Backend entry point: Pants loads this module when `vcs_versioning_pants_plugin` is in `backend_packages`."""

from typing import TYPE_CHECKING

from vcs_versioning_pants_plugin.codegen import rules as codegen_rules
from vcs_versioning_pants_plugin.module_mapper import rules as module_mapper_rules
from vcs_versioning_pants_plugin.subsystem import rules as subsystem_rules
from vcs_versioning_pants_plugin.target_types import ScmVersionTarget

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules, CollectedTargetTypes


def rules() -> CollectedRules:
    """Return every rule this backend registers with the Pants engine."""
    return (*codegen_rules(), *module_mapper_rules(), *subsystem_rules())


def target_types() -> CollectedTargetTypes:
    """Return every target type this backend registers with the Pants engine."""
    return (ScmVersionTarget,)
