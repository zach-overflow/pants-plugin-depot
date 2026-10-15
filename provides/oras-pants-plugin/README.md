# oras-pants-plugin

A [Pantsbuild](https://www.pantsbuild.org/) plugin that wraps the outputs of `package`-able targets, such as
`pex_binary`, as [OCI artifacts](https://oras.land/docs/concepts/artifact) and publishes them to OCI registries
with [`oras`](https://oras.land/). Any registry that stores OCI artifacts works: GitHub Container Registry,
Docker Hub, Artifact Registry, ECR, ACR, Harbor, a local `registry:2`, and so on.

## Installation

Add the plugin to `pants.toml` and enable its backend:

```toml
[GLOBAL]
plugins = ["oras-pants-plugin==<version>"]
backend_packages.add = ["pants.backend.python", "oras_pants_plugin"]

[oras.registries.ghcr]
address = "ghcr.io/my-org"
default = true
```

Wrap the targets to publish in an `oci_artifact` target, like the builtin `archive` target does:

```python
# src/app/BUILD
pex_binary(name="app", entry_point="main.py")

oci_artifact(
    name="app-artifact",
    packages=[":app"],
    oci_repository="app",
    oci_tags=["1.2.0", "latest"],
    oci_artifact_type="application/vnd.python.pex.v1",
)
```

Build it, or build and push it:

```bash
pants package src/app:app-artifact   # writes the OCI image layout to dist/src.app/app-artifact/
pants publish src/app:app-artifact   # copies it to ghcr.io/my-org/app:1.2.0 and :latest
```

Pull it back anywhere with `oras pull ghcr.io/my-org/app:1.2.0`, which restores `src.app/app.pex`.

## How it works

`oras` is downloaded as a static binary; nothing is installed into a Pants resolve.

`pants package` builds every `packages` target as `pants package` would, then runs `oras push --oci-layout` to
write one [OCI image layout](https://github.com/opencontainers/image-spec/blob/main/image-layout.md) directory
to `output_path` under `--distdir`. Every file or directory the `packages` targets produce becomes one layer,
titled with its own `--distdir`-relative path (a `packed` or `loose` layout PEX is a directory, pushed as a
gzipped tar layer that `oras pull` unpacks again). The artifact is tagged with every `oci_tags` entry and the
manifest's `artifactType` is `oci_artifact_type`.

`pants publish` packages the target the same way, then runs one `oras cp --from-oci-layout` per registry, in the
foreground so `oras` can show progress. The copy addresses the layout's manifest by digest, so the published
artifact has exactly the digest `pants package` reported. A target without `oci_repository`, that resolves to no
registry, with `skip_oras=True`, or run with `[oras].skip = true` is skipped before it is packaged. Each copy is
reported as published, failed or skipped like every other publisher; `--publish-output` writes the same as JSON,
with the `registry`, `repository`, `tags` and `digest` of each copy.

### `oci_artifact` fields

| Field               | Purpose                                                                                                                                                                                                                                                       |
| :------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `packages`          | Addresses of targets `pants package` can build, e.g. `[":app"]`. Each output becomes a layer.                                                                                                                                                                 |
| `output_path`       | Where `pants package` writes the layout directory, relative to `--distdir`. Default: `<spec path with dots>/<target name>`.                                                                                                                                   |
| `oci_tags`          | Tags applied in the layout and in every registry. Default: `["latest"]`. `[]` leaves the artifact untagged, addressable by digest only.                                                                                                                      |
| `oci_artifact_type` | The `artifactType` of the manifest, passed as `--artifact-type`, e.g. `application/vnd.python.pex.v1`. Default: `oras`' `application/vnd.unknown.artifact.v1`.                                                                                               |
| `oci_registries`    | Registry addresses (`ghcr.io/my-org`, `localhost:5000`) or `@aliases` of `[oras].registries` entries to publish to. Default: every `[oras].registries` entry with `default = true`.                                                                           |
| `oci_repository`    | The repository within each registry, e.g. `team/app`; the published reference is `<registry>/<oci_repository>:<tag>`. Unset skips the target in `pants publish`.                                                                                             |
| `skip_oras`         | If true, the target is skipped by `pants publish`.                                                                                                                                                                                                            |

## Configuration

| Option                  | Default         | Purpose                                                                                                                                                                                                  |
| :---------------------- | :-------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[oras].registries`     | `{}`            | Registries by alias: `{"alias": {"address": "host[:port][/prefix]", "default": bool}}`. An entry aliased `default` is a default too.                                                                     |
| `[oras].skip`           | `false`         | Skip `oras` during `pants publish`.                                                                                                                                                                      |
| `[oras].args`           | `[]`            | Extra arguments for every `oras cp`, e.g. `--to-plain-http` or `--to-insecure`. The registry is the copy's destination, so its flags are the `--to-*` ones. They follow the plugin's own flags, so a repeated flag overrides it. |
| `[oras].config`         | unset           | A registry authentication file in the `~/.docker/config.json` format, passed as `--to-registry-config`. Relative paths are resolved from the build root.                                                 |
| `[oras].extra_env_vars` | `[]`            | Extra environment variables for `oras cp`, as `NAME=value` or `NAME` to copy from Pants' environment, e.g. `HTTPS_PROXY` or `SSL_CERT_FILE`.                                                             |
| `[oras].version`        | bundled default | `oras` release to download.                                                                                                                                                                              |
| `[oras].known_versions` | bundled default | Checksums of downloadable releases; extend to use another version.                                                                                                                                       |

### Credentials

`oras` reads the credentials that `docker login` or `oras login` store in `$DOCKER_CONFIG/config.json` or
`~/.docker/config.json`, and runs the credential helpers configured there. `PATH`, `HOME` and `DOCKER_CONFIG`
are always passed to `oras cp`, so logging in once is enough:

```bash
oras login ghcr.io          # or: docker login ghcr.io
pants publish src/app:app-artifact
```

In CI, pass the token to a login step before `pants publish`, or point `[oras].config` at an auth file. Avoid
`--to-username`/`--to-password` in `[oras].args`: `pants.toml` is committed.

### Publishing into a directory

`oras cp` can write to an OCI image layout directory instead of a registry, which is handy for inspecting what
would be pushed. With `--to-oci-layout`, the registry reference becomes a directory path in the sandbox, so
combine it with `--keep-sandboxes=always` to look at the result:

```bash
pants --oras-args="['--to-oci-layout']" --keep-sandboxes=always publish src/app:app-artifact
```

The layout `pants package` writes to `dist/` is the same artifact; `oras discover`, `oras manifest fetch` and
`oras pull` all accept it with `--oci-layout`:

```bash
oras manifest fetch --oci-layout dist/src.app/app-artifact:1.2.0 | jq
```

### Using a different `oras` version

Add the release's checksums and sizes to `known_versions` and set `version`:

```toml
[oras]
version = "1.3.5"
known_versions.add = [
  "1.3.5|linux_arm64 |<sha256>|<size>",
  "1.3.5|linux_x86_64|<sha256>|<size>",
  "1.3.5|macos_arm64 |<sha256>|<size>",
  "1.3.5|macos_x86_64|<sha256>|<size>",
]
```

Compute each line with `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`, where `$URL` is the
`oras_<version>_<os>_<arch>.tar.gz` asset of the
[GitHub release](https://github.com/oras-project/oras/releases) (`linux`/`darwin`, `amd64`/`arm64`). The
release's `oras_<version>_checksums.txt` lists the same checksums.

## Supported versions

| Plugin | Pants  | Python | `oras`     |
| :----- | :----- | :----- | :--------- |
| `0.x`  | `2.33` | `3.14` | `>=1.3,<2` |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on. The
packages being wrapped may target any Python version.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/oras-pants-plugin/). Release notes live in the
[changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/oras-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
