resource(name="pytyped-marker", source="py.typed")
# `version.py` is generated from the `pyproject-fmt-plugin-vX.Y.Z` git tags at build time; it is never written to the tree.
scm_version(
    name="scm-version",
    tag_prefix="pyproject-fmt-plugin-v",
    generate_to="provides/pyproject-fmt-plugin/src/pyproject_fmt_pants_plugin/version.py",
    template='__version__ = "{version}"\n',
)
python_sources(dependencies=[":pytyped-marker", ":scm-version", "./lockfile_resource:lockfile-resource-module"])
