# pants-plugin-depot

A collection of [Pantsbuild](https://www.pantsbuild.org/) plugins. Each plugin lives in its own directory
under [`provides/`](provides) and is its own Python distribution with its own version, changelog and PyPI
project.

## Plugins

Click on each plugin linked below for installation and supported versions.

<table>
  <thead>
    <tr>
      <th align="left" style="white-space: nowrap;">Plugin</th>
      <th align="left">What it does</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/actionlint-pants-plugin/"><code>actionlint-pants-plugin</code></a></td>
      <td>Lints GitHub Actions workflow files with <a href="https://github.com/rhysd/actionlint"><code>actionlint</code></a>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/maturin-pants-plugin/"><code>maturin-pants-plugin</code></a></td>
      <td>Build and publish Rust-backed Python wheels with <a href="https://www.maturin.rs/"><code>maturin</code></a>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/oras-pants-plugin/"><code>oras-pants-plugin</code></a></td>
      <td>Wraps <code>package</code>-able targets as custom OCI artifacts and publishes them to OCI registries as OCI artifacts with <a href="https://oras.land/"><code>oras</code></a>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/pants-plugin-developer-utils/"><code>pants-plugin-developer-utils</code></a></td>
      <td>Type aliases and pytest fixtures for writing and testing Pants plugins.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/pyproject-fmt-pants-plugin/"><code>pyproject-fmt-pants-plugin</code></a></td>
      <td>Formats <code>pyproject.toml</code> files with <a href="https://pyproject-fmt.readthedocs.io/"><code>pyproject-fmt</code></a>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/ty-pants-plugin/"><code>ty-pants-plugin</code></a></td>
      <td>Type checks Python code with <a href="https://docs.astral.sh/ty/"><code>ty</code></a>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/typos-pants-plugin/"><code>typos-pants-plugin</code></a></td>
      <td>Checks and fixes spelling in source code with <a href="https://github.com/crate-ci/typos"><code>typos</code></a>.</td>
    </tr>
    <tr>
      <td style="white-space: nowrap;"><a href="https://pypi.org/project/vcs-versioning-pants-plugin/"><code>vcs-versioning-pants-plugin</code></a></td>
      <td>Generates version modules from git tags with <a href="https://pypi.org/project/vcs-versioning/"><code>vcs-versioning</code></a> (the core of <code>setuptools-scm</code>), with per-package tag prefixes.</td>
    </tr>
  </tbody>
</table>

## Contributing and Development Info

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Releases

Each plugin is released on its own, under a `<plugin-name>-vX.Y.Z` tag. Release notes live in each plugin's
`CHANGELOG.md` and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

Every release publishes the plugin's wheel to PyPI. `oras-pants-plugin` releases also publish, dogfooding the
plugin itself, the plugin as a [PEX](https://docs.pex-tool.org/) inside an OCI artifact to GitHub Container
Registry, tagged with the version and `latest`. The PEX holds the plugin's wheel and
`pants-plugin-developer-utils` only; it imports `pants` from the interpreter that runs it.

```bash
oras pull ghcr.io/zach-overflow/pants-plugin-depot/oras-pants-plugin:X.Y.Z   # restores oras-pants-plugin.pex
```

## Bug Reports / Feature Requests

Open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
