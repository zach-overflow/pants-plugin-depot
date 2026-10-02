# Contributing

All commands run from the repo root.

## Prerequisites

- [Pants](https://www.pantsbuild.org/stable/docs/getting-started/installing-pants) (the launcher; the
  version is pinned in `pants.toml`)
- Python 3.14
- [prek](https://prek.j178.dev/) for git hooks: `prek install`
- [cocogitto](https://docs.cocogitto.io/) for conventional commits: `cog commit`

## Repository layout

Each plugin is a separate Python distribution in its own top-level directory:

```
<plugin-name>/
  BUILD            # the `plugin-whl` python_distribution
  pyproject.toml   # packaging metadata, version and runtime dependencies of this plugin
  README.md
  CHANGELOG.md     # written by `cog bump`
  src/<root_module>/
  tests/<root_module>_tests/
```

The root `pyproject.toml` holds only the repo-wide tool configuration (ruff, pytest, mypy).

Test modules live in a `<root_module>_tests` package, not directly in `tests/`. Every plugin has a
`conftest.py`, and mypy rejects two modules with the same name in one `pants check ::` run.

## Common commands

```bash
pants fmt fix ::                        # ruff, shfmt, taplo, BUILD file formatting
pants lint ::                           # ruff, shellcheck, shfmt, taplo, yamllint
pants check ::                          # mypy
pants test ::                           # pytest
pants package ::                        # build every plugin's wheel -> dist/
pants generate-lockfiles                # regenerate 3rdparty/python/plugin-lockfile.json
pants export --resolve=plugin-resolve   # virtualenv for IDEs -> dist/export/
```

Append a directory to scope a goal to one plugin, e.g. `pants test pyproject-fmt-plugin::`.

## Dependencies

There is one resolve, `plugin-resolve`, shared by every plugin. It holds Pants itself (via the
`pants_requirements` target in the root `BUILD`), the test-only requirements in the root `BUILD`, and each
plugin's runtime dependencies. Pants' builtin tools (ruff, mypy, pytest, ...) use the default versions
Pants ships with.

A plugin declares its runtime dependencies in `[project].dependencies` of its own `pyproject.toml`. That
list is what the wheel requires. To make Pants see it, the plugin's `BUILD` needs:

```python
python_requirements(name="reqs", source="pyproject.toml")
```

Add that target together with the plugin's first dependency. Pants rejects it while the list is empty.

Two plugins MAY declare the same requirement. Imports then resolve to the importing plugin's own target
(`[python-infer].ambiguity_resolution` in `pants.toml`). Because the resolve is shared, their version
ranges MUST overlap.

Regenerate the lockfile whenever `pants_version` or any plugin's dependencies change.

A wheel MUST NOT declare `pantsbuild.pants` as a dependency: Pants supplies itself when it loads a plugin,
and its wheels are not on PyPI. Any other runtime dependency MUST be compatible with the versions Pants
itself pins.

## Versioning

Each plugin carries its own version, committed as `[project].version` in `<plugin-name>/pyproject.toml`.
It MUST NOT be edited by hand. `cog bump` rewrites it, updates `<plugin-name>/CHANGELOG.md`, and tags the
commit `<plugin-name>-vMAJOR.MINOR.PATCH`. There is no repo-wide version.

Between releases, a wheel built from `main` carries the last released version.

## Conventional commits

PRs are squash-merged, so the **PR title** becomes the commit on `main`. It MUST be a
[conventional commit](https://www.conventionalcommits.org/) message. The *PR title* workflow verifies it
with `cog verify`. Allowed scopes are listed in `cog.toml`.

`fix`, `perf` and `refactor` bump the patch version. `feat` bumps the minor version. Other types do not
warrant a release.

A commit counts for a plugin when it changes a file under that plugin's directory. The scope plays no
part. A commit that touches two plugins bumps both. A commit that touches only root files bumps none.

## Cutting a release

1. Land conventional commits on `main`. For each plugin, the commits since its latest tag that touch its
   directory are its release: they determine the version and become the release notes.
2. Run the *Release* workflow from `main` (Actions -> Release -> Run workflow). It:
   - checks the pending commits are conventional and that at least one plugin warrants a bump,
   - runs `pants lint check test ::` and builds the wheels,
   - runs `cog bump --auto`, which bumps every plugin with pending changes in one
     `chore(version): bump packages` commit and tags it once per bumped plugin,
   - pushes that commit and the tags to `main`,
   - creates one **draft** GitHub release per tag from the plugin's changelog,
   - dispatches the *Publish* workflow once per tag.
3. Approve the `pypi` environment prompt in each *Publish* run. It uploads the wheel to PyPI, then attaches
   the wheel to the draft release and publishes it.

## Adding a plugin

1. Create `<plugin-name>/` following the layout above. Copy `pyproject-fmt-plugin/BUILD` and
   `pyproject-fmt-plugin/pyproject.toml` as a starting point. Set `version = "0.0.0"`.
2. Keep the distribution target named `plugin-whl`. The Publish workflow builds `<plugin-name>:plugin-whl`.
3. Register the plugin in `cog.toml`: add `[monorepo.packages.<plugin-name>]` with `path = "<plugin-name>"`,
   and add `<plugin-name>` to `scopes`. The package name MUST equal the directory name.
4. Add the plugin's modules to `known-first-party` in the root `pyproject.toml`.
5. Add the plugin to the table in the root `README.md`.
6. Register a PyPI Trusted Publisher for the new project (see below).

## Required repository configuration

- **Environments**: `release` (no protection rules) and `pypi` (required reviewer; deployment limited to
  the `main` branch and `*-v*` tags).
- **`RELEASE_TOKEN`**: a secret of the `release` environment. A fine-grained personal access token of a
  repo admin, scoped to this repo with `Contents: read and write`. `main` requires pull requests, and only
  an admin's push bypasses that, so the Release workflow pushes the bump commit with this token.
- **Branch protection**: "Do not allow bypassing the above settings" MUST stay off for `main`. Otherwise
  the bump commit is rejected.
- **Immutable releases**: enabled. A published release cannot gain assets, which is why the release stays
  a draft until the wheel is attached.
- **Tag ruleset**: MUST NOT restrict tag creation. Restricting updates and deletions is fine.
- **Merging**: squash merging only, with the default commit message set to "Pull request title".
- **PyPI**: one Trusted Publisher per plugin project, each for owner/repo `zach-overflow/pants-plugin-depot`,
  workflow `publish.yml`, environment `pypi`. Publish is always dispatched, never called as a reusable
  workflow, because PyPI rejects reusable workflows.

## Troubleshooting

- **`check-commits` fails with a parse error**: a commit on `main` since the latest tag is not a valid
  conventional commit. Land the remaining commits with compliant messages.
- **`check-commits` fails with "No plugin has a commit that warrants a release"**: only non-bumping
  types (`chore`, `docs`, `ci`, ...) landed, or the bumping commits touched no plugin directory. Land at
  least one `fix` or `feat` that changes a plugin.
- **`approve-and-tag` fails with "moved past the validated commit"**: a PR merged while the release was
  running. Re-run the Release workflow.
- **`approve-and-tag` fails on `git push`**: `RELEASE_TOKEN` is missing, expired, or not an admin's token.
- **`build-wheel` finds no wheel for the version**: `[project].version` at the tag differs from the tag.
  The tag was not created by `cog bump`.
- **PyPI publish fails with an OIDC error**: the plugin's registered Trusted Publisher must match exactly.
- **`publish-release` fails because no GitHub release exists**: the tag was pushed by hand, or the Release
  run failed after pushing. Create the release as a draft, then run Publish with the tag:
  `gh release create <plugin-name>-vX.Y.Z --draft --title "<plugin-name> X.Y.Z" --notes "..."` and
  `gh workflow run publish.yml --ref <plugin-name>-vX.Y.Z -f tag=<plugin-name>-vX.Y.Z`.
