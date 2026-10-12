resource(name="pytyped-marker", source="py.typed")
# `version.py` is generated from the `tach-pants-plugin-vX.Y.Z` git tags at build time; it is never written to the tree.
scm_version(
    name="scm-version",
    tag_prefix="tach-pants-plugin-v",
    generate_to="provides/tach-pants-plugin/src/tach_pants_plugin/version.py",
    template='__version__ = "{version}"\n',
)
python_sources(dependencies=[":pytyped-marker", "./tach_lockfile_resource:tach-lockfile-resource-module"])
