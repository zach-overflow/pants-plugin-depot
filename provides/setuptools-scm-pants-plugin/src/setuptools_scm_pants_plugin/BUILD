resource(name="pytyped-marker", source="py.typed")
# `version.py` is generated from the `setuptools-scm-pants-plugin-vX.Y.Z` git tags at build time; it is never written to the tree.
scm_version(
    name="scm-version",
    tag_prefix="setuptools-scm-pants-plugin-v",
    generate_to="provides/setuptools-scm-pants-plugin/src/setuptools_scm_pants_plugin/version.py",
    template='__version__ = "{version}"\n',
)
python_sources(dependencies=[":pytyped-marker", ":scm-version", "./lockfile_resource:lockfile-resource-module"])
