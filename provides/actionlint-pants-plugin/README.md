# actionlint-pants-plugin

![PyPI Version](https://img.shields.io/pypi/v/actionlint-pants-plugin?style=flat&logo=python&logoColor=white&logoSize=auto&color=rgb(162%2C%200%2C%20255))

A [Pantsbuild](https://www.pantsbuild.org/) plugin that lints GitHub Actions workflow files with
[`actionlint`](https://github.com/rhysd/actionlint): workflow syntax, `${{ }}` expressions, action inputs,
runner labels, and the shell scripts in `run:` steps.

## Installation

Add the plugin to `pants.toml`. Pants ignores dot-directories by default, so `.github/` MUST be made visible too:

```toml
[GLOBAL]
plugins = ["actionlint-pants-plugin==<version>"]
pants_ignore.add = ["!.github/"]
```

Declare the workflow targets next to the workflow files:

```python
# .github/workflows/BUILD
github_workflow_sources()
```

Then run `actionlint` through the `lint` goal:

```bash
pants lint .github/workflows::   # or `pants lint ::`
```

## How it works

`actionlint` is downloaded as a static binary; nothing is installed into a Pants resolve. The plugin registers
a `github_workflow_sources` target generator, which yields one `github_workflow_source` target per `*.yml` or
`*.yaml` file next to the `BUILD` file, and a `pants lint` integration over those targets. For each run Pants:

1. Puts the workflow files, their `dependencies` and the config file (see below) into a sandbox, together
   with an empty `.git` directory: `actionlint` only reads its config and validates local `uses: ./...`
   references inside a git repository, and a sandbox is not one.
2. Downloads `shellcheck` through Pants' `[shellcheck]` subsystem and passes it as `-shellcheck`, so `run:`
   steps are checked as they would be with `shellcheck` on the `PATH`. Set `[actionlint].shellcheck = false`
   to opt out. The `pyflakes` integration is always disabled, as Pants ships no `pyflakes` tool.
3. Runs `actionlint -color` once per batch on the workflow files. The linter fails when `actionlint` does.

### Target fields

| Field             | Target                     | Purpose                                                                                                                                                                                                                                                                                 |
| :---------------- | :------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sources`         | `github_workflow_sources`  | Globs of workflow files, relative to the `BUILD` file. Default: `["*.yaml", "*.yml"]`.                                                                                                                                                                                                  |
| `source`          | `github_workflow_source`   | One workflow file.                                                                                                                                                                                                                                                                      |
| `dependencies`    | both                       | Targets the workflow uses: the `files` target holding a local action's `action.yml`, a reusable workflow, a script a step runs. `actionlint` validates the inputs of a local action whose `action.yml` is present, and `pants --changed-since` re-lints the workflow when a dependency changes. |
| `skip_actionlint` | both                       | If true, the file is excluded from `pants lint`.                                                                                                                                                                                                                                        |
| `overrides`       | `github_workflow_sources`  | Per-file values for the fields above, e.g. `overrides={"release.yml": {"skip_actionlint": True}}`.                                                                                                                                                                                      |

## Configuration

`actionlint` reads `.github/actionlint.yaml` or `.github/actionlint.yml` from the repository root
([reference](https://github.com/rhysd/actionlint/blob/main/docs/config.md)). Pants includes that file
automatically. Point `[actionlint].config` at a config file elsewhere to pass it as `-config-file`, which
takes precedence over the repository config.

| Option                          | Default         | Purpose                                                                                                                                         |
| :------------------------------ | :-------------- | :---------------------------------------------------------------------------------------------------------------------------------------------- |
| `[actionlint].skip`             | `false`         | Skip `actionlint` during `pants lint`.                                                                                                          |
| `[actionlint].args`             | `[]`            | Extra arguments for `actionlint`, e.g. `-ignore 'SC2086:.+'` or `-oneline`. They follow the plugin's own flags, so a repeated flag overrides it. |
| `[actionlint].config`           | unset           | Path to an `actionlint` config file, passed as `-config-file`. Disables discovery.                                                              |
| `[actionlint].config_discovery` | `true`          | Include `.github/actionlint.yaml` or `.github/actionlint.yml` from the build root.                                                               |
| `[actionlint].shellcheck`       | `true`          | Run `shellcheck` on `run:` steps. The binary is the `[shellcheck].version` release; the other `[shellcheck]` options do not apply.              |
| `[actionlint].version`          | bundled default | `actionlint` release to download.                                                                                                               |
| `[actionlint].known_versions`   | bundled default | Checksums of downloadable releases; extend to use another version.                                                                              |

### Using a different `actionlint` version

Add the release's checksums and sizes to `known_versions` and set `version`:

```toml
[actionlint]
version = "1.7.13"
known_versions.add = [
  "1.7.13|linux_arm64 |<sha256>|<size>",
  "1.7.13|linux_x86_64|<sha256>|<size>",
  "1.7.13|macos_arm64 |<sha256>|<size>",
  "1.7.13|macos_x86_64|<sha256>|<size>",
]
```

Compute each line with `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`, where `$URL` is the
`actionlint_<version>_<os>_<arch>.tar.gz` asset of the
[GitHub release](https://github.com/rhysd/actionlint/releases) (`linux`/`darwin`, `amd64`/`arm64`).

## Supported versions

| Plugin | Pants  | Python | `actionlint` |
| :----- | :----- | :----- | :----------- |
| `0.x`  | `2.33` | `3.14` | `>=1.7,<2`   |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/actionlint-pants-plugin/). Release notes live in the
[changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/actionlint-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
