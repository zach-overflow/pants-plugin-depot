# Defined in `etc/pants-macros/_internal_pants_macros.py`; see `pants plugin_wheel --help`.
plugin_wheel()

# Source of the bundled `vcs-versioning` tool lockfile. Regenerate with
# `pants generate-lockfiles --resolve=vcs-versioning`.
# The requirement MUST match `VcsVersioning.default_requirements` in `src/vcs_versioning_pants_plugin/subsystem.py`.
python_requirement(name="vcs-versioning-tool", requirements=["vcs-versioning>=2.5,<3"], resolve="vcs-versioning")
