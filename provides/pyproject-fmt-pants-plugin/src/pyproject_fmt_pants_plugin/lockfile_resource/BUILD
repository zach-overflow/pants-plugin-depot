# Pants reads the `.metadata` sidecar of a `resource://` lockfile unconditionally, so both files MUST ship.
resources(
    name="default-pyproject-fmt-lockfile",
    sources=["pyproject_fmt_lockfile.json", "pyproject_fmt_lockfile.json.metadata"],
)
python_sources(name="lockfile-resource-module", dependencies=[":default-pyproject-fmt-lockfile"])
