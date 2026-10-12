# pants-plugin-depot

A collection of [Pantsbuild](https://www.pantsbuild.org/) plugins. Each plugin lives in its own directory
under [`provides/`](provides) and is its own Python distribution with its own version, changelog and PyPI
project.

## Plugins

<table>
  <thead>
    <tr>
      <th align="left">Plugin</th>
      <th align="left">Latest Release</th>
      <th align="left">What it does</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><a href="provides/maturin-pants-plugin"><code>maturin-pants-plugin</code></a></td>
      <td><a href="https://pypi.org/project/maturin-pants-plugin/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/maturin-pants-plugin?style=plastic&color=blue"></a></td>
      <td>Build and publish Rust-backed Python wheels with <a href="https://www.maturin.rs/"><code>maturin</code></a>.</td>
    </tr>
    <tr>
      <td><a href="provides/pants-plugin-developer-utils"><code>pants-plugin-developer-utils</code></a></td>
      <td><a href="https://pypi.org/project/pants-plugin-developer-utils/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/pants-plugin-developer-utils?style=plastic&color=blue">
</a></td>
      <td>Type aliases and pytest fixtures for writing and testing Pants plugins.</td>
    </tr>
    <tr>
      <td><a href="provides/pyproject-fmt-pants-plugin"><code>pyproject-fmt-pants-plugin</code></a></td>
      <td><a href="https://pypi.org/project/pyproject-fmt-pants-plugin/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/pyproject-fmt-pants-plugin?style=plastic&color=blue">
</a></td>
      <td>Formats <code>pyproject.toml</code> files with <a href="https://pyproject-fmt.readthedocs.io/"><code>pyproject-fmt</code></a>.</td>
    </tr>
    <tr>
      <td><a href="provides/ty-pants-plugin"><code>ty-pants-plugin</code></a></td>
      <td><a href="https://pypi.org/project/ty-pants-plugin/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/ty-pants-plugin?style=plastic&color=blue"></a></td>
      <td>Type checks Python code with <a href="https://docs.astral.sh/ty/"><code>ty</code></a>.</td>
    </tr>
    <tr>
      <td><a href="provides/vcs-versioning-pants-plugin"><code>vcs-versioning-pants-plugin</code></a></td>
      <td><a href="https://pypi.org/project/vcs-versioning-pants-plugin/"><img alt="PyPI Version" src="https://img.shields.io/pypi/v/vcs-versioning-pants-plugin?style=plastic&color=blue"></a></td>
      <td>Generates version modules from git tags with <a href="https://pypi.org/project/vcs-versioning/"><code>vcs-versioning</code></a> (the core of <code>setuptools-scm</code>), with per-package tag prefixes.</td>
    </tr>
  </tbody>
</table>

See each plugin's README for installation and supported versions.

## Contributing and Development Info

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Releases

Each plugin is released on its own, under a `<plugin-name>-vX.Y.Z` tag. Release notes live in each plugin's
`CHANGELOG.md` and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Bug Reports / Feature Requests

Open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
