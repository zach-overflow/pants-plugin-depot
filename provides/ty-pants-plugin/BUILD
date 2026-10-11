file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/ty-pants-plugin")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/ty-pants-plugin/src/ty_pants_plugin",
        "provides/ty-pants-plugin/src/ty_pants_plugin:pytyped-marker",
    ],
    provides=python_artifact(name="ty-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
