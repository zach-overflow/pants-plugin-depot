file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/vcs-versioning-pants-plugin")

# Source of the bundled `vcs-versioning` tool lockfile. Regenerate with
# `pants generate-lockfiles --resolve=vcs-versioning`.
# The requirement MUST match `VcsVersioning.default_requirements` in `src/vcs_versioning_pants_plugin/subsystem.py`.
python_requirement(name="vcs-versioning-tool", requirements=["vcs-versioning>=2.5,<3"], resolve="vcs-versioning")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/vcs-versioning-pants-plugin/src/vcs_versioning_pants_plugin",
        "provides/vcs-versioning-pants-plugin/src/vcs_versioning_pants_plugin:pytyped-marker",
        "provides/vcs-versioning-pants-plugin/src/vcs_versioning_pants_plugin:scm-version",
        "provides/vcs-versioning-pants-plugin/src/vcs_versioning_pants_plugin/lockfile_resource:lockfile-resource-module",
    ],
    provides=python_artifact(name="vcs-versioning-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
