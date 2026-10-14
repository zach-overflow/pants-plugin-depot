# oras-pants-plugin

A [Pantsbuild](https://www.pantsbuild.org/) plugin that publishes the output of `pex_binary` targets to OCI
registries as [OCI artifacts](https://oras.land/docs/concepts/artifact) with [`oras`](https://oras.land/). Any
registry that stores OCI artifacts works: GitHub Container Registry, Docker Hub, Artifact Registry, ECR, ACR,
Harbor, a local `registry:2`, and so on.

## Installation

Add the plugin to `pants.toml` and enable its backend next to the Python backend:

```toml
[GLOBAL]
plugins = ["oras-pants-plugin==<version>"]
backend_packages.add = ["pants.backend.python", "oras_pants_plugin"]
```

Tell a `pex_binary` target where to push:

```python
# src/app/BUILD
pex_binary(
    name="app",
    entry_point="main.py",
    oci_repositories=["ghcr.io/my-org/app"],
    oci_tags=["1.2.0", "latest"],
)
```

Then build and push it through the `publish` goal:

```bash
pants publish src/app:app
```

Pull it back anywhere with `oras pull ghcr.io/my-org/app:1.2.0`, which restores `app.pex`.

## How it works

`oras` is downloaded as a static binary; nothing is installed into a Pants resolve. For every `pex_binary`
target that lists `oci_repositories`, `pants publish`:

1. Packages the target as `pants package` would. A target without `oci_repositories`, with `skip_oras=True`,
   or run with `[oras].skip = true` is skipped before it is packaged.
2. Runs one `oras push` per `oci_repositories` entry, in the foreground so `oras` can show progress. Every
   artifact `pants package` produced for the target (the PEX, plus any `scie` executables) becomes a layer of
   one OCI artifact, which is tagged with every `oci_tags` entry at once. The manifest's `artifactType` is the
   target's `oci_media_type`.
3. Reports each push as published, failed or skipped, like every other publisher. `--publish-output` writes the
   same as JSON, with the `repository` and `tags` of each push.

A `packed` or `loose` layout PEX is a directory, which `oras` pushes as a gzipped tar layer and `oras pull`
unpacks again. The layer media types are left to `oras`.

### Target fields

| Field              | Target                       | Purpose                                                                                                                                                                       |
| :----------------- | :--------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `oci_repositories` | `pex_binary`, `pex_binaries` | `<registry>/<repository>` references to push to, such as `ghcr.io/my-org/app` or `localhost:5000/app`. One push per entry. A reference MUST NOT carry a tag or digest.        |
| `oci_tags`         | `pex_binary`, `pex_binaries` | Tags applied to the artifact in every repository. Default: `["latest"]`. `[]` pushes the artifact untagged, addressable by digest only.                                       |
| `oci_media_type`   | `pex_binary`, `pex_binaries` | The `artifactType` of the pushed manifest, passed as `--artifact-type`. Default: `application/vnd.python.pex.v1`.                                                             |
| `skip_oras`        | `pex_binary`, `pex_binaries` | If true, the target is skipped by `pants publish`.                                                                                                                            |
| `overrides`        | `pex_binaries`               | Per-binary values for the fields above, e.g. `overrides={"tool.py": {"skip_oras": True}}`. On `pex_binaries` the fields apply to every generated `pex_binary`.               |

## Configuration

| Option                     | Default         | Purpose                                                                                                                                        |
| :------------------------- | :-------------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
| `[oras].skip`              | `false`         | Skip `oras` during `pants publish`.                                                                                                            |
| `[oras].args`              | `[]`            | Extra arguments for every `oras push`, e.g. `--plain-http` or `--registry-config /path/to/auth.json`. They follow the plugin's own flags, so a repeated flag overrides it. |
| `[oras].extra_env_vars`    | `[]`            | Extra environment variables for `oras`, as `NAME=value` or `NAME` to copy from Pants' environment, e.g. `HTTPS_PROXY` or `SSL_CERT_FILE`.     |
| `[oras].version`           | bundled default | `oras` release to download.                                                                                                                    |
| `[oras].known_versions`    | bundled default | Checksums of downloadable releases; extend to use another version.                                                                             |

### Credentials

`oras` reads the credentials that `docker login` or `oras login` store in `$DOCKER_CONFIG/config.json` or
`~/.docker/config.json`, and runs the credential helpers configured there. `PATH`, `HOME` and `DOCKER_CONFIG`
are always passed to `oras`, so logging in once is enough:

```bash
oras login ghcr.io          # or: docker login ghcr.io
pants publish src/app:app
```

In CI, pass the token to a login step before `pants publish`, or point `[oras].args` at an auth file with
`--registry-config`. Avoid `--username`/`--password` in `pants.toml`: the file is committed.

### Pushing to a directory

`oras` can write to an [OCI image layout](https://github.com/opencontainers/image-spec/blob/main/image-layout.md)
directory instead of a registry, which is handy for inspecting what would be pushed:

```bash
pants --oras-args="['--oci-layout-path', '/tmp/app-layout']" publish src/app:app
```

The reference in `oci_repositories` is kept as the tag name inside the layout.

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

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on. The PEX
being published may target any Python version.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/oras-pants-plugin/). Release notes live in the
[changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/oras-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
