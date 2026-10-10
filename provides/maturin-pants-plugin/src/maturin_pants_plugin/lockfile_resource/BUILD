# Pants reads the `.metadata` sidecar of a `resource://` lockfile unconditionally, so both files MUST ship.
resources(name="default-maturin-lockfile", sources=["maturin_lockfile.json", "maturin_lockfile.json.metadata"])
python_sources(name="lockfile-resource-module", dependencies=[":default-maturin-lockfile"])
