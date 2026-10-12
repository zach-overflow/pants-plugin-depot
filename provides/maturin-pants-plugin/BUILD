file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
# setuptools only accepts license files inside the project directory.
relocated_files(name="license", files_targets=["//:license"], src="", dest="provides/maturin-pants-plugin")

# Source of the bundled `maturin` tool lockfile. Regenerate with `pants generate-lockfiles --resolve=maturin`.
# The requirement MUST match `Maturin.default_requirements` in `src/maturin_pants_plugin/subsystem.py`.
python_requirement(name="maturin-tool", requirements=["maturin>=1.15.0,<2"], resolve="maturin")

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "provides/maturin-pants-plugin/src/maturin_pants_plugin",
        "provides/maturin-pants-plugin/src/maturin_pants_plugin:pytyped-marker",
        "provides/maturin-pants-plugin/src/maturin_pants_plugin:scm-version",
        "provides/maturin-pants-plugin/src/maturin_pants_plugin/goals",
        "provides/maturin-pants-plugin/src/maturin_pants_plugin/lockfile_resource:lockfile-resource-module",
    ],
    provides=python_artifact(name="maturin-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
