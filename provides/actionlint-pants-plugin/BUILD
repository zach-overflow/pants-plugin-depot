file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/actionlint-pants-plugin")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/actionlint-pants-plugin/src/actionlint_pants_plugin",
        "provides/actionlint-pants-plugin/src/actionlint_pants_plugin:pytyped-marker",
        "provides/actionlint-pants-plugin/src/actionlint_pants_plugin:scm-version",
        "provides/actionlint-pants-plugin/src/actionlint_pants_plugin/goals",
    ],
    provides=python_artifact(name="actionlint-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
