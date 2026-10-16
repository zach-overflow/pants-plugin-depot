# pyproject-fmt-pants-plugin

A [Pantsbuild](https://www.pantsbuild.org/) plugin for formatting `pyproject.toml` files with
[`pyproject-fmt`](https://pyproject-fmt.readthedocs.io/).

## Installation

Add the plugin to `pants.toml`:

```toml
[GLOBAL]
plugins = ["pyproject-fmt-pants-plugin==<version>"]
```

Then run `pyproject-fmt` through the `fmt` and `lint` goals:

```bash
pants fmt ::    # rewrite every pyproject.toml in place
pants lint ::   # fail when a pyproject.toml is not formatted
```

## How it works

`pyproject-fmt` is installed into its own Pants resolve from the bundled lockfile, independent of your
project's resolves. The plugin registers one `fmt` integration, which Pants also runs in check-only mode for
`lint`.

For each run Pants:

1. Selects the `pyproject.toml` files among the goal's inputs.
2. Includes the shared config file, if any (see below).
3. Runs `pyproject-fmt` once per file. `pyproject-fmt` stops after the first file it changes, so one process
   per file keeps every file in the batch formatted.

## Configuration

`pyproject-fmt` layers its settings in this order, later entries winning:

1. `[pyproject-fmt].args`, passed on the command line.
2. A shared `pyproject-fmt.toml` file. Pants includes the one in the build root automatically; point
   `[pyproject-fmt].config` at a file elsewhere instead.
3. The `[tool.pyproject-fmt]` table of each `pyproject.toml` file, which `pyproject-fmt` reads itself.

So a `pyproject-fmt.toml` file is optional: repo-wide settings can live in `pants.toml` alone.

```toml
[pyproject-fmt]
# https://pyproject-fmt.readthedocs.io/en/latest/configuration.html#command-line-interface
args = ["--column-width=120", "--indent=2", "--keep-full-version"]
```

| Option                                    | Default                   | Purpose                                                                           |
| :---------------------------------------- | :------------------------ | :-------------------------------------------------------------------------------- |
| `[pyproject-fmt].skip`                    | `false`                   | Skip `pyproject-fmt` during `pants fmt` and `pants lint`.                         |
| `[pyproject-fmt].args`                    | `[]`                      | Arguments always passed to `pyproject-fmt`, e.g. `--column-width=120`.            |
| `[pyproject-fmt].config`                  | unset                     | Path to a `pyproject-fmt.toml` file. Disables discovery.                          |
| `[pyproject-fmt].config_discovery`        | `true`                    | Pick up a `pyproject-fmt.toml` file from the build root.                          |
| `[pyproject-fmt].install_from_resolve`    | unset                     | Install `pyproject-fmt` from one of your own resolves instead of the lockfile.    |
| `[pyproject-fmt].interpreter_constraints` | `["CPython>=3.14,<3.15"]` | Interpreter that runs `pyproject-fmt`; independent of your project's constraints. |

`--config` accepts only a standalone `pyproject-fmt.toml`: a `pyproject.toml` fails on its `[project]` table.

## Supported versions

| Plugin | Pants  | Python |
| :----- | :----- | :----- |
| `0.x`  | `2.33` | `3.14` |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/pyproject-fmt-pants-plugin/). Release notes live in
the [changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/pyproject-fmt-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
