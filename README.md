# pants-plugin-depot

A collection of [Pantsbuild](https://www.pantsbuild.org/) plugins. Each plugin is its own Python
distribution with its own version, changelog and PyPI project.

## Plugins

| Plugin                                         | PyPI                                                                           | What it does                                                                              |
| :--------------------------------------------- | :----------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------- |
| [`pyproject-fmt-plugin`](pyproject-fmt-plugin) | [`pyproject-fmt-pants-plugin`](https://pypi.org/project/pyproject-fmt-pants-plugin/) | Formats `pyproject.toml` files with [`pyproject-fmt`](https://pyproject-fmt.readthedocs.io/). |

See each plugin's README for installation and supported versions.

## Contributing and Development Info

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Releases

Each plugin is released on its own, under a `<plugin-name>-vX.Y.Z` tag. Release notes live in each plugin's
`CHANGELOG.md` and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Bug Reports / Feature Requests

Open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
