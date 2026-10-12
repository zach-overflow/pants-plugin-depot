file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/setuptools-scm-pants-plugin")

# Source of the bundled `setuptools-scm` tool lockfile. Regenerate with
# `pants generate-lockfiles --resolve=setuptools-scm`.
# The requirement MUST match `SetuptoolsScm.default_requirements` in `src/setuptools_scm_pants_plugin/subsystem.py`.
python_requirement(name="setuptools-scm-tool", requirements=["setuptools-scm>=10.3.4,<11"], resolve="setuptools-scm")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/setuptools-scm-pants-plugin/src/setuptools_scm_pants_plugin",
        "provides/setuptools-scm-pants-plugin/src/setuptools_scm_pants_plugin:pytyped-marker",
        "provides/setuptools-scm-pants-plugin/src/setuptools_scm_pants_plugin:scm-version",
        "provides/setuptools-scm-pants-plugin/src/setuptools_scm_pants_plugin/lockfile_resource:lockfile-resource-module",
    ],
    provides=python_artifact(name="setuptools-scm-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
