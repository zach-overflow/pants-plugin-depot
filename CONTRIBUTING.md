# Contributing

All commands run from the repo root.

## Prerequisites

- [Pants](https://www.pantsbuild.org/stable/docs/getting-started/installing-pants) (the launcher; the
  version is pinned in `pants.toml`)
- Python 3.14
- [prek](https://prek.j178.dev/) for git hooks: `prek install`
- [cocogitto](https://docs.cocogitto.io/) for conventional commits: `cog commit`

## Common commands

```bash
pants fmt fix ::                        # ruff, shfmt, taplo, BUILD file formatting
pants lint ::                           # ruff, shellcheck, shfmt, taplo, yamllint
pants check ::                          # mypy
pants test ::                           # pytest
pants package ::                        # build the wheel -> dist/
pants generate-lockfiles                # regenerate 3rdparty/python/plugin-lockfile.json
pants export --resolve=plugin-resolve   # virtualenv for IDEs -> dist/export/
```

## Dependencies

There is one resolve, `plugin-resolve`. It holds Pants itself (via the `pants_requirements` target in the
root `BUILD`) plus test-only requirements. Pants' builtin tools (ruff, mypy, pytest, ...) use the default
versions Pants ships with.

Regenerate the lockfile whenever `pants_version` changes.

The wheel MUST NOT declare `pantsbuild.pants` as a dependency: Pants supplies itself when it loads a
plugin, and its wheels are not on PyPI. Any other runtime dependency added to `[project].dependencies`
MUST be compatible with the versions Pants itself pins.

## Versioning

No version string is committed. The `vcs_version` target in `src/pyproject_fmt_pants_plugin/BUILD`
generates `_scm_version.py` from the git state via setuptools-scm, and the committed `_version.py`
re-exports it.

- On a checkout of a `vMAJOR.MINOR.PATCH` tag, the version is exactly `MAJOR.MINOR.PATCH`.
- On any other commit it is a dev version (`X.Y.Z.devN+g<hash>`).

## Conventional commits

PRs are squash-merged, so the **PR title** becomes the commit on `main`. It MUST be a
[conventional commit](https://www.conventionalcommits.org/) message. The *PR title* workflow verifies it
with `cog verify`. Allowed scopes are listed in `cog.toml`.

`fix`, `perf` and `refactor` bump the patch version. `feat` bumps the minor version. Other types do not
warrant a release.

## Cutting a release

1. Land conventional commits on `main`. The commits since the latest tag are the release: they determine
   the version and become the release notes.
2. Run the *Release* workflow from `main` (Actions -> Release -> Run workflow). It:
   - checks the pending commits are conventional and warrant a bump,
   - runs `pants lint check test ::` and builds the wheel,
   - tags the validated commit `vX.Y.Z` with `cog bump --auto` (tag-only; nothing is pushed to `main`),
   - creates a **draft** GitHub release with the cog-generated changelog,
   - dispatches the *Publish* workflow.
3. Approve the `pypi` environment prompt in the *Publish* run. It uploads the wheel to PyPI, then attaches
   the wheel to the draft release and publishes it.

## Required repository configuration

- **Environments**: `release` (no protection rules) and `pypi` (required reviewer; deployment limited to
  the `main` branch and `v*` tags).
- **Immutable releases**: enabled. A published release cannot gain assets, which is why the release stays
  a draft until the wheel is attached.
- **Tag ruleset**: MUST NOT restrict tag creation. The Release workflow pushes the tag with the built-in
  `GITHUB_TOKEN`, which cannot be added to a bypass list. Restricting updates and deletions is fine.
- **Merging**: squash merging only, with the default commit message set to "Pull request title".
- **PyPI**: a Trusted Publisher for owner/repo `zach-overflow/pyproject-fmt-pantsbuild-plugin`, workflow
  `publish.yml`, environment `pypi`. Publish is always dispatched, never called as a reusable workflow,
  because PyPI rejects reusable workflows.

## Troubleshooting

- **`check-commits` fails with a parse error**: a commit on `main` since the latest tag is not a valid
  conventional commit. Land the remaining commits with compliant messages.
- **`check-commits` fails with "No commit since the latest tag warrants a release"**: only non-bumping
  types (`chore`, `docs`, `ci`, ...) landed. Land at least one `fix` or `feat`.
- **The wheel carries a dev version after Publish**: the build did not see the release tag. The
  `build-wheel` job must check out `v<version>` with `fetch-depth: 0`.
- **PyPI publish fails with an OIDC error**: the registered Trusted Publisher must match exactly.
- **`publish-release` fails because no GitHub release exists**: the tag was pushed by hand. Create the
  release as a draft, then re-run Publish:
  `gh release create vX.Y.Z --draft --title X.Y.Z --notes-file <(cog changelog --at vX.Y.Z)`.
