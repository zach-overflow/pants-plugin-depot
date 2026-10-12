# Pants reads the `.metadata` sidecar of a `resource://` lockfile unconditionally, so both files MUST ship.
resources(
    name="default-setuptools-scm-lockfile",
    sources=["setuptools_scm_lockfile.json", "setuptools_scm_lockfile.json.metadata"],
)
python_sources(name="lockfile-resource-module", dependencies=[":default-setuptools-scm-lockfile"])
