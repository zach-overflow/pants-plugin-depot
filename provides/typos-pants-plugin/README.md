# typos-pants-plugin

A [Pantsbuild](https://www.pantsbuild.org/) plugin that checks and corrects spelling in source code with
[`typos`](https://github.com/crate-ci/typos), the Rust-based spell checker built for code.

## Installation

Add the plugin to `pants.toml` and enable its backend:

```toml
[GLOBAL]
plugins = ["typos-pants-plugin==<version>"]
backend_packages.add = ["typos_pants_plugin"]
```

Then run `typos` through the `lint` and `fix` goals:

```bash
pants lint ::   # report every typo
pants fix ::    # write the unambiguous corrections back
```

## How it works

`typos` is downloaded as a static binary; nothing is installed into a Pants resolve. The plugin registers
two goal integrations that share one process setup:

- **`pants lint`** runs `typos` in check mode and reports every typo it finds, including misspelled file
  names and typos with several candidate corrections. The linter fails when `typos` does.
- **`pants fix`** runs `typos --write-changes` and writes the corrected files back to the workspace. `typos`
  only corrects typos with a single candidate, and the plugin passes `--no-check-filenames` because Pants
  cannot write a rename back: whatever `fix` leaves behind, `lint` still reports.

For each run Pants:

1. Selects the files the goal was given that match `[typos].glob_pattern` (every file by default).
2. Includes every config file `typos` would discover for those files (see below).
3. Runs `typos` once per batch with `--force-exclude`, so the `files.extend-exclude` globs of your config apply
   even though Pants lists the files explicitly.

`lint` does not reuse the `fix` result (the usual Pants pattern for fixers): diffing a `fix` run would miss
the ambiguous typos and the misspelled file names that `typos` reports but cannot correct.

## Configuration

`typos` reads `typos.toml`, `_typos.toml` or `.typos.toml`, the `[tool.typos]` table of `pyproject.toml`, or
the `[workspace.metadata.typos]` / `[package.metadata.typos]` tables of `Cargo.toml`, from each checked
file's directory and its ancestors. Pants includes those files automatically. Point `[typos].config` at a
config file elsewhere to use that file alone.

| Option                     | Default         | Purpose                                                                               |
| :------------------------- | :-------------- | :------------------------------------------------------------------------------------ |
| `[typos].skip`             | `false`         | Skip `typos` during `pants lint` and `pants fix`.                                     |
| `[typos].args`             | `[]`            | Extra arguments for `typos`, e.g. `--locale en-us` or `--format brief`.               |
| `[typos].config`           | unset           | Path to a `typos` config file. Disables discovery and runs `typos` with `--isolated`. |
| `[typos].config_discovery` | `true`          | Include the config files `typos` discovers. When false, `typos` runs with `--isolated`. |
| `[typos].glob_pattern`     | `["**/*"]`      | Globs selecting the files to check; a leading `!` excludes.                           |
| `[typos].version`          | bundled default | `typos` release to download.                                                          |
| `[typos].known_versions`   | bundled default | Checksums of downloadable releases; extend to use another version.                    |

With `--isolated`, `typos` ignores config files it would otherwise find on its own, including a
`pyproject.toml` file that is itself among the files being checked.

### Using a different `typos` version

Add the release's checksums and sizes to `known_versions` and set `version`:

```toml
[typos]
version = "1.52.0"
known_versions.add = [
  "1.52.0|linux_arm64 |<sha256>|<size>",
  "1.52.0|linux_x86_64|<sha256>|<size>",
  "1.52.0|macos_arm64 |<sha256>|<size>",
  "1.52.0|macos_x86_64|<sha256>|<size>",
]
```

Compute each line with `curl -L $URL | tee >(wc -c) >(shasum -a 256) >/dev/null`, where `$URL` is the
`typos-v<version>-<target>.tar.gz` asset of the [GitHub release](https://github.com/crate-ci/typos/releases).

## Supported versions

| Plugin | Pants  | Python | `typos`        |
| :----- | :----- | :----- | :------------- |
| `0.x`  | `2.33` | `3.14` | `>=1.16.18,<2` |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on. The
files being checked can be anything `typos` understands.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/typos-pants-plugin/). Release notes live in the
[changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/typos-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
