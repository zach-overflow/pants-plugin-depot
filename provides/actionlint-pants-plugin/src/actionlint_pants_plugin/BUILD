resource(name="pytyped-marker", source="py.typed")
# `version.py` is generated from the `actionlint-pants-plugin-vX.Y.Z` git tags at build time; it is never written to the tree.
scm_version(
    name="scm-version",
    tag_prefix="actionlint-pants-plugin-v",
    generate_to="provides/actionlint-pants-plugin/src/actionlint_pants_plugin/version.py",
    template='__version__ = "{version}"\n',
)
python_sources(dependencies=[":pytyped-marker", ":scm-version"])
