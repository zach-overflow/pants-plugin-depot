resource(name="pytyped-marker", source="py.typed")
vcs_version(
    name="scm-version", generate_to="src/pyproject_fmt_pants_plugin/_scm_version.py", template='version = "{version}"'
)
# Scoped to `_version.py`: the generated version changes on every commit, which would otherwise invalidate
# the cache of every test that imports anything from this package.
python_sources(overrides={"_version.py": {"dependencies": [":scm-version"]}})
