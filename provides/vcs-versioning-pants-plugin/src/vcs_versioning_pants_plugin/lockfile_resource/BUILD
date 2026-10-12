# Pants reads the `.metadata` sidecar of a `resource://` lockfile unconditionally, so both files MUST ship.
resources(
    name="default-vcs-versioning-lockfile",
    sources=["vcs_versioning_lockfile.json", "vcs_versioning_lockfile.json.metadata"],
)
python_sources(name="lockfile-resource-module", dependencies=[":default-vcs-versioning-lockfile"])
