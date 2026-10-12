resource(name="pytyped-marker", source="py.typed")
# `version.py` is generated from the `pants-plugin-developer-utils-vX.Y.Z` git tags at build time; it is never written to the tree.
scm_version(
    name="scm-version",
    tag_prefix="pants-plugin-developer-utils-v",
    generate_to="provides/pants-plugin-developer-utils/src/pants_plugin_developer_utils/version.py",
    template='__version__ = "{version}"\n',
)
python_sources(dependencies=[":pytyped-marker", ":scm-version"])
