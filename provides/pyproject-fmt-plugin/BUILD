file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/pyproject-fmt-plugin")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin",
        "provides/pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin:pytyped-marker",
        "provides/pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin/goals",
        "provides/pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin/lockfile_resource:lockfile-resource-module",
    ],
    provides=python_artifact(name="pyproject-fmt-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
