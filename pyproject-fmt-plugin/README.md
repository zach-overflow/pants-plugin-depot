# pyproject-fmt-pants-plugin

A [Pantsbuild](https://www.pantsbuild.org/) plugin for formatting `pyproject.toml` files with
[`pyproject-fmt`](https://pyproject-fmt.readthedocs.io/).

> **Status:** project skeleton. The backend registers with Pants, but it provides no goals yet.

## Installation

Add the plugin to `pants.toml` and enable its backend:

```toml
[GLOBAL]
plugins = ["pyproject-fmt-pants-plugin==<version>"]
backend_packages.add = ["pyproject_fmt_pants_plugin"]
```

## Supported versions

| Plugin | Pants  | Python |
| :----- | :----- | :----- |
| `0.x`  | `2.33` | `3.14` |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/pyproject-fmt-pants-plugin/). Release notes live in
the [changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/pyproject-fmt-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
