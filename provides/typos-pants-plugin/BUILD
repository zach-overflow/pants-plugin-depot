file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/typos-pants-plugin")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/typos-pants-plugin/src/typos_pants_plugin",
        "provides/typos-pants-plugin/src/typos_pants_plugin:pytyped-marker",
        "provides/typos-pants-plugin/src/typos_pants_plugin:scm-version",
        "provides/typos-pants-plugin/src/typos_pants_plugin/goals",
    ],
    provides=python_artifact(name="typos-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
