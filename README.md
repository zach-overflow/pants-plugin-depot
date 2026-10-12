# pants-plugin-depot

A collection of [Pantsbuild](https://www.pantsbuild.org/) plugins. Each plugin lives in its own directory
under [`provides/`](provides) and is its own Python distribution with its own version, changelog and PyPI
project.

## Plugins

| Plugin                                                                  | PyPI                                                                                     | What it does                                                                                                                            |
| :---------------------------------------------------------------------- | :--------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------- |
| [`maturin-pants-plugin`](provides/maturin-pants-plugin)                 | [`maturin-pants-plugin`](https://pypi.org/project/maturin-pants-plugin/)                 | Builds and publishes Rust-backed Python wheels with [`maturin`](https://www.maturin.rs/).                                               |
| [`pants-plugin-developer-utils`](provides/pants-plugin-developer-utils) | [`pants-plugin-developer-utils`](https://pypi.org/project/pants-plugin-developer-utils/) | Type aliases and pytest fixtures for writing and testing Pants plugins.                                                                 |
| [`pyproject-fmt-plugin`](provides/pyproject-fmt-plugin)                 | [`pyproject-fmt-pants-plugin`](https://pypi.org/project/pyproject-fmt-pants-plugin/)     | Formats `pyproject.toml` files with [`pyproject-fmt`](https://pyproject-fmt.readthedocs.io/).                                           |
| [`setuptools-scm-pants-plugin`](provides/setuptools-scm-pants-plugin)   | [`setuptools-scm-pants-plugin`](https://pypi.org/project/setuptools-scm-pants-plugin/)   | Generates version modules from git tags with [`setuptools-scm`](https://setuptools-scm.readthedocs.io/), with per-package tag prefixes. |
| [`ty-pants-plugin`](provides/ty-pants-plugin)                           | [`ty-pants-plugin`](https://pypi.org/project/ty-pants-plugin/)                           | Type checks Python code with [`ty`](https://docs.astral.sh/ty/).                                                                        |

See each plugin's README for installation and supported versions.

## Contributing and Development Info

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Releases

Each plugin is released on its own, under a `<plugin-name>-vX.Y.Z` tag. Release notes live in each plugin's
`CHANGELOG.md` and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Bug Reports / Feature Requests

Open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
