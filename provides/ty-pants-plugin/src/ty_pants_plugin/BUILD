resource(name="pytyped-marker", source="py.typed")
# `version.py` is generated from the `ty-pants-plugin-vX.Y.Z` git tags at build time; it is never written to the tree.
scm_version(
    name="scm-version",
    tag_prefix="ty-pants-plugin-v",
    generate_to="provides/ty-pants-plugin/src/ty_pants_plugin/version.py",
    template='__version__ = "{version}"\n',
)
python_sources(dependencies=[":pytyped-marker", ":scm-version"])
