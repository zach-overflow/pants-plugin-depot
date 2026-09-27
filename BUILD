file(name="pyproject", source="pyproject.toml")
file(name="readme", source="README.md")
file(name="license", source="LICENSE")

pants_requirements(name="pants")
# `pantsbuild.pants.testutil` 2.33 requires `pytest<9`.
python_requirement(name="pytest", requirements=["pytest>=8.4,<9"])

# With `generate_setup=False`, setuptools reads `pyproject.toml` directly (version via setuptools-scm).
python_distribution(
    name="plugin-whl",
    dependencies=[
        ":license",
        ":pyproject",
        ":readme",
        "src/pyproject_fmt_pants_plugin",
        "src/pyproject_fmt_pants_plugin:pytyped-marker",
        "src/pyproject_fmt_pants_plugin:scm-version",
        "src/pyproject_fmt_pants_plugin/goals",
    ],
    provides=python_artifact(name="pyproject-fmt-pants-plugin"),
    sdist=False,
    wheel=True,
    generate_setup=False,
)
