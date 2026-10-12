file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/pants-plugin-developer-utils")

# `pytest` is the only third-party requirement in the shared resolve; every plugin's tests resolve to it.
python_requirements(name="reqs", source="pyproject.toml")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/pants-plugin-developer-utils/src/pants_plugin_developer_utils",
        "provides/pants-plugin-developer-utils/src/pants_plugin_developer_utils:pytyped-marker",
        "provides/pants-plugin-developer-utils/src/pants_plugin_developer_utils:scm-version",
        "provides/pants-plugin-developer-utils/src/pants_plugin_developer_utils/testing_utils",
    ],
    provides=python_artifact(name="pants-plugin-developer-utils"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
