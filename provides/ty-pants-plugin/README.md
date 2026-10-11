# ty-pants-plugin

A [Pantsbuild](https://www.pantsbuild.org/) plugin for type checking Python code with
[`ty`](https://docs.astral.sh/ty/), the Rust-based type checker from Astral.

## Installation

Add the plugin to `pants.toml` and enable its backend:

```toml
[GLOBAL]
plugins = ["ty-pants-plugin==<version>"]
backend_packages.add = ["ty_pants_plugin"]
```

Then run `ty` through the `check` goal:

```bash
pants check ::
```

## How it works

`ty` is downloaded as a static binary; nothing is installed into a Pants resolve. For each run Pants:

1. Partitions the requested targets by resolve and interpreter constraints, like the builtin mypy backend.
2. Builds a virtual environment from the partition's third-party requirements and passes it to `ty` with
   `--python`, so third-party imports resolve against the versions in your lockfile.
3. Passes every Pants source root of the targets' transitive closure with `--extra-search-path`, so
   first-party imports resolve across source roots.
4. Derives `--python-version` from the partition's interpreter constraints, unless `[ty].args` or the
   config file already sets it.
5. Runs `ty check` on the requested files only. Dependencies are present for import resolution but are not
   themselves reported on.

## Configuration

`ty` reads `ty.toml`, or the `[tool.ty]` table of `pyproject.toml`, from the directory it runs in and its
ancestors. Pants runs it from the build root, so only a config in the build root takes effect. Pants
includes that file automatically. Point `[ty].config` at a `ty.toml` elsewhere to override discovery.

| Option                         | Default                   | Purpose                                                                |
| :----------------------------- | :------------------------ | :--------------------------------------------------------------------- |
| `[ty].skip`                    | `false`                   | Skip `ty` during `pants check`.                                        |
| `[ty].args`                    | `[]`                      | Extra arguments for `ty check`, e.g. `--output-format concise`.        |
| `[ty].config`                  | unset                     | Path to a `ty.toml`. Disables discovery.                               |
| `[ty].config_discovery`        | `true`                    | Pick up `ty.toml` or `pyproject.toml` from the build root.             |
| `[ty].version`                 | bundled default           | `ty` release to download.                                              |
| `[ty].known_versions`          | bundled default           | Checksums of downloadable releases; extend to use another version.     |
| `[ty].interpreter_constraints` | `["CPython>=3.10,<3.16"]` | Fallback constraints for the environment, when the code declares none. |

To opt a target out, set `skip_ty=True` on any `python_source`, `python_sources`, `python_test`,
`python_tests` or `python_test_utils` target.

### Using a different `ty` version

Add the release's checksums and sizes to `known_versions` and set `version`:

```toml
[ty]
version = "0.0.90"
known_versions.add = [
  "0.0.90|linux_arm64 |<sha256>|<size>",
  "0.0.90|linux_x86_64|<sha256>|<size>",
  "0.0.90|macos_arm64 |<sha256>|<size>",
  "0.0.90|macos_x86_64|<sha256>|<size>",
]
```

Compute each line with `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`, where `$URL` is the
`ty-<target>.tar.gz` asset of the [GitHub release](https://github.com/astral-sh/ty/releases).

## Supported versions

| Plugin | Pants  | Python | `ty`           |
| :----- | :----- | :----- | :------------- |
| `0.x`  | `2.33` | `3.14` | `>=0.0.80,<1`  |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on. The
code being checked may target any Python version `ty` supports.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/ty-pants-plugin/). Release notes live in the
[changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/ty-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
