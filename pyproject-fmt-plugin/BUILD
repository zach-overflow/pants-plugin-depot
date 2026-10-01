file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="pyproject-fmt-plugin")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin",
        "pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin:pytyped-marker",
        "pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin/goals",
        "pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin/lockfile_resource",
    ],
    provides=python_artifact(name="pyproject-fmt-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
