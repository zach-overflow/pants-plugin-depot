# maturin-pants-plugin

![PyPI Version](https://img.shields.io/pypi/v/maturin-pants-plugin?style=flat&logo=python&logoColor=white&logoSize=auto&color=rgb(162%2C%200%2C%20255))

A [Pantsbuild](https://www.pantsbuild.org/) plugin for building and publishing Rust-backed Python wheels with
[`maturin`](https://www.maturin.rs/).

> **Status:** alpha. `pants package` and `pants publish` work for `maturin_wheel` targets; only `*.whl` outputs are
> supported.

## Installation

Add the plugin to `pants.toml`. The plugin needs the Python backend too:

```toml
[GLOBAL]
plugins = ["maturin-pants-plugin==<version>"]
backend_packages.add = ["pants.backend.python"]
```

`cargo`, `rustc` and the interpreters listed in `[maturin].interpreter` MUST be on the `PATH` of the shell that runs
Pants: the plugin passes `PATH`, `HOME`, `CARGO_HOME` and `RUSTUP_HOME` into the build sandbox.

## Usage

Declare a `maturin_wheel` target in the directory holding the crate's `Cargo.toml` and `pyproject.toml`:

```python
maturin_wheel(
    name="wheel",
    # Files `maturin build` needs that are not matched by the default `sources` globs.
    dependencies=[":readme", "python/my_pkg"],
    # Registries for `pants publish`. `@name` is a `.pypirc` section, anything else a `--repository-url`.
    repositories=["@pypi"],
)

file(name="readme", source="README.md")
```

By default `sources` covers `Cargo.toml`, `Cargo.lock`, `pyproject.toml`, `build.rs`, `src/**/*.rs`, `tests/**/*.rs`
and `python/**`. `cargo_toml` and `pyproject_toml` default to the files of those names next to the BUILD file; both
MUST be matched by `sources`, and `pyproject.toml` MUST sit beside `Cargo.toml`.

```shell
pants package path/to/crate:wheel   # runs `maturin build`, writes dist/<name>-<version>-<tags>.whl
pants publish path/to/crate:wheel   # runs `maturin upload` once per entry of `repositories`
```

`maturin upload` reads credentials from `MATURIN_PYPI_TOKEN`, or `MATURIN_USERNAME` and `MATURIN_PASSWORD`, or your
`~/.pypirc`. Targets without `repositories`, or with `skip_maturin_upload=True`, are skipped by `pants publish`
without being built.

### Options

Configure the `[maturin]` section of `pants.toml`. Run `pants help-advanced maturin` for the full list.

| Option                        | Default                                      | Effect                                           |
| :---------------------------- | :------------------------------------------- | :----------------------------------------------- |
| `bindings`                    | `pyo3`                                       | `maturin build --bindings`                       |
| `compatibility`               | `pypi`                                       | `maturin build --compatibility`                  |
| `interpreter`                 | `["python3.12", "python3.13", "python3.14"]` | One `--interpreter` per entry; `[]` omits it     |
| `jobs`                        | unset                                        | `maturin build --jobs`                           |
| `profile_guided_optimization` | `false`                                      | `maturin build --pgo`                            |
| `release`                     | `true`                                       | `maturin build --release`                        |
| `skip`                        | `false`                                      | Skip every `maturin_wheel` during `pants publish` |
| `skip_existing`               | `false`                                      | `maturin upload --skip-existing`                 |
| `extra_env_vars`              | `[]`                                         | Extra `NAME` or `NAME=value` entries for maturin |

Cargo's `target/` directory lives in a Pants named cache, so repeated builds are incremental.

### Regenerating the tool lockfile

The plugin ships a lockfile for the `maturin` tool itself. It is generated through the `maturin` resolve declared in
the repo's `pants.toml` and the `maturin-tool` requirement in `provides/maturin-pants-plugin/BUILD`:

```shell
pants generate-lockfiles --resolve=maturin
```

## Supported versions

| Plugin | Pants  | Python |
| :----- | :----- | :----- |
| `0.x`  | `2.33` | `3.14` |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/maturin-pants-plugin/). Release notes live in the
[changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/maturin-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
