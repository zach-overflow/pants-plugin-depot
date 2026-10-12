# setuptools-scm-pants-plugin

A [Pantsbuild](https://www.pantsbuild.org/) plugin that generates a version module from git tags with
[`setuptools-scm`](https://setuptools-scm.readthedocs.io/), so no version string has to be committed. Its
`scm_version` target is a drop-in superset of Pants' builtin `vcs_version` that adds a `tag_prefix`, which makes
it work in monorepos where every package is tagged and released on its own (`<package>-vX.Y.Z`).

## Installation

Add the plugin to `pants.toml` and enable its backend:

```toml
[GLOBAL]
plugins = ["setuptools-scm-pants-plugin==<version>"]
backend_packages.add = ["setuptools_scm_pants_plugin"]
```

The backend does not depend on `pants.backend.experimental.python` and coexists with it.

## Usage

Declare one `scm_version` target per package, next to the package's sources:

```python
# src/my_package/BUILD
scm_version(
    name="scm-version",
    tag_prefix="my-package-v",  # only `my-package-vX.Y.Z` tags count; omit for repo-wide `vX.Y.Z` tags
    generate_to="src/my_package/version.py",
    template='__version__ = "{version}"\n',
)
python_sources(dependencies=[":scm-version"])
```

Let setuptools read the generated module. With `generate_setup=False`, Pants hands your `pyproject.toml` to
setuptools untouched:

```toml
# pyproject.toml
[project]
name = "my-package"
dynamic = ["version"]

[tool.setuptools]
dynamic.version = { attr = "my_package.version.__version__" }
```

```python
# BUILD
python_distribution(
    name="my-package-whl",
    dependencies=[":pyproject", "src/my_package", "src/my_package:scm-version"],
    provides=python_artifact(name="my-package"),
    generate_setup=False,
)
```

`pants package //:my-package-whl` then builds `my_package-X.Y.Z-py3-none-any.whl` on a checkout of the
`my-package-vX.Y.Z` tag. Code can also import the module at runtime (`from my_package.version import
__version__`): dependency inference maps the generated module to its `scm_version` target.

## How it works

For every `scm_version` target Pants:

1. Locates the git worktree of the build root.
2. Writes a synthetic `pyproject.toml` holding only this target's fields into a sandbox. Any
   `[tool.setuptools_scm]` table in the repository is ignored, and setuptools-scm can never write a version file
   into the workspace.
3. Runs `setuptools-scm` from the bundled lockfile against the worktree. With `tag_prefix`, that is
   `git describe --tags --match '<tag_prefix>*[0-9]*'`; the prefix is stripped before `tag_regex` runs.
4. Renders `template` with the resulting version into `generate_to`. The file exists only in the sandboxes of
   targets that depend on it (tests, `check`, `package`, ...), and in the wheel. It is never written to the
   source tree. Preview it with `pants export-codegen path/to:scm-version` (written under `dist/codegen/`).

The process result is cached per Pants session, so each run reflects the current git state.

### Versions produced

| git state                                   | version                   |
| :------------------------------------------ | :------------------------ |
| `HEAD` is tagged `<tag_prefix>1.2.3`        | `1.2.3`                   |
| 4 commits after that tag                    | `1.2.4.dev4+g<sha>`       |
| the same, with uncommitted changes          | `1.2.4.dev4+g<sha>.d<date>` |
| no tag with `tag_prefix` reachable          | `0.1.dev<N>+g<sha>`       |

`version_scheme` and `local_scheme` adjust these forms, see the setuptools-scm
[documentation](https://setuptools-scm.readthedocs.io/en/latest/extending/#version-number-construction).

setuptools-scm needs the tags and the history between them and `HEAD`. In GitHub Actions, check out with
`fetch-depth: 0`; a shallow clone yields `0.1.dev1`.

### Why not `vcs_version`?

Pants' `vcs_version` passes only `tag_regex`, `version_scheme` and `local_scheme` to setuptools-scm, and pins
setuptools-scm 7. setuptools-scm therefore runs `git describe --match '*[0-9]*'`, which returns the nearest tag
of *any* package. In a monorepo with per-package tags every package ends up with the same version, and a
`tag_regex` that rejects the foreign tag makes setuptools-scm fail instead of looking further. `tag.prefix`,
which fixes this, arrived in setuptools-scm 10.

## Target fields

| Field            | Default                                | Purpose                                                                          |
| :--------------- | :------------------------------------- | :------------------------------------------------------------------------------- |
| `tag_prefix`     | unset                                  | Literal prefix a tag must carry, e.g. `my-package-v`. Stripped before `tag_regex`. |
| `tag_regex`      | setuptools-scm's default               | Regex extracting the version from the (prefix-stripped) tag.                     |
| `version_scheme` | unset (`guess-next-dev`)               | setuptools-scm version scheme.                                                   |
| `local_scheme`   | unset (`node-and-date`)                | setuptools-scm local scheme.                                                     |
| `generate_to`    | required                               | Build-root-relative path of the generated file.                                  |
| `template`       | required                               | Format string with a `{version}` placeholder.                                    |
| `python_resolve` | `[python].default_resolve`             | Resolve the generated module belongs to, for dependency inference.               |

## Configuration

The `[setuptools-scm-tool]` subsystem installs setuptools-scm from a lockfile bundled with the plugin
(setuptools-scm `>=10.3.4,<11`). To use another version, point `install_from_resolve` at one of your
resolves, see
[lockfiles for tools](https://www.pantsbuild.org/stable/docs/python/overview/lockfiles#lockfiles-for-tools).

| Option                                            | Default                   | Purpose                                              |
| :------------------------------------------------ | :------------------------ | :--------------------------------------------------- |
| `[setuptools-scm-tool].install_from_resolve`      | unset (bundled lockfile)  | Install setuptools-scm from this resolve instead.    |
| `[setuptools-scm-tool].requirements`              | the whole resolve         | Subset of that resolve to install.                   |
| `[setuptools-scm-tool].interpreter_constraints`   | `["CPython>=3.14,<3.15"]` | Interpreter that runs setuptools-scm.                |

## Supported versions

| Plugin | Pants  | Python | `setuptools-scm` |
| :----- | :----- | :----- | :--------------- |
| `0.x`  | `2.33` | `3.14` | `>=10.3.4,<11`   |

Pants loads plugins into its own interpreter, so the plugin requires the Python version Pants runs on. The
versioned code may target any Python version.

## Releases

Wheels are published to [PyPI](https://pypi.org/project/setuptools-scm-pants-plugin/). Release notes live in the
[changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/setuptools-scm-pants-plugin/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This plugin lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
