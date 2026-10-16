"""
Internal macros that keep the per-plugin `BUILD` files under `provides/` DRY.

Each macro derives the plugin's PyPI project name (`<plugin-name>`) and root package name (`<plugin_name>`) from
the directory of the calling `BUILD` file, so the `BUILD` files stay free of repeated paths.

See:
    https://www.pantsbuild.org/stable/docs/writing-plugins/macros
    https://www.pantsbuild.org/stable/reference/build-file-symbols/build_file_dir
"""

COMMON_MACRO_TAG: Annotated[str, Doc("Tag added to every macro-generated target, for easier project inspection.")] = (
    "from-macro"
)
OCI_PEX_ARTIFACT_TYPE: Annotated[str, Doc("The OCI `artifactType` of the plugin PEXes this repo publishes.")] = (
    "application/vnd.python.pex.v1"
)
OCI_REGISTRY: Annotated[str, Doc("The OCI registry the plugin PEXes are published to.")] = "ghcr.io"
OCI_REPOSITORY_PREFIX: Annotated[str, Doc("A plugin PEX is published as `<OCI_REGISTRY>/<prefix>/<plugin-name>`.")] = (
    "zach-overflow/pants-plugin-depot"
)


def _plugin_names() -> tuple[str, str]:
    """
    Returns `("<plugin-name>", "<plugin_name>")`, the PyPI project name and the root package name of the plugin
    that owns the calling `BUILD` file.

    Supports `provides/<plugin-name>/BUILD` and `provides/<plugin-name>/src/<plugin_name>/BUILD`.
    """
    build_dir = build_file_dir()
    if build_dir.parent.name == "provides":
        pypi_name = build_dir.name
    elif build_dir.parent.name == "src" and build_dir.parent.parent.parent.name == "provides":
        pypi_name = build_dir.parent.parent.name
    else:
        raise ValueError(
            f"The plugin macros may only be called from `provides/<plugin-name>/BUILD` or "
            f"`provides/<plugin-name>/src/<plugin_name>/BUILD`, not from `{build_dir}/BUILD`."
        )
    return pypi_name, pypi_name.replace("-", "_")


def _release_tag_prefix(pypi_name: str) -> str:
    """`cog bump` tags a plugin's releases `<plugin-name>-vX.Y.Z`; vcs-versioning selects them by this prefix."""
    return f"{pypi_name}-v"


def plugin_root_sources(extra_dependencies: list[str] | None = None) -> None:
    """
    Defines the targets of a plugin's root package. Call it once from `provides/<plugin-name>/src/<plugin_name>/BUILD`.

    Generates:
        - `:pytyped-marker`: the `py.typed` marker file.
        - `:scm-version-for-wheel`: `version.py`, generated from the `<plugin-name>-vX.Y.Z` git tags at build time;
          never written to the tree. setuptools reads `__version__` from it when it builds the wheel.
        - the `python_sources` of the package, depending on both of the above.

    Args:
        extra_dependencies: Further addresses to add to the `python_sources` `dependencies` field, for example
            `["./lockfile_resource:lockfile-resource-module"]`.
    """
    tags = ["plugin_root_sources", COMMON_MACRO_TAG]
    pypi_name, root_pkg_name = _plugin_names()
    resource(name="pytyped-marker", source="py.typed", tags=tags)
    scm_version(
        name="scm-version-for-wheel",
        tag_prefix=_release_tag_prefix(pypi_name),
        generate_to=f"provides/{pypi_name}/src/{root_pkg_name}/version.py",
        template='__version__ = "{version}"\n',
        tags=tags,
    )
    python_sources(dependencies=[":pytyped-marker", ":scm-version-for-wheel", *(extra_dependencies or [])], tags=tags)


def plugin_wheel(extra_dependencies: list[str] | None = None, include_oci_pex: bool = True) -> None:
    """
    Defines a plugin's `:plugin-whl` `python_distribution` and the targets it packages. Call it once from
    `provides/<plugin-name>/BUILD`. The Publish workflow builds `provides/<plugin-name>:plugin-whl`.

    The wheel depends on the plugin's root `python_sources` (see `plugin_root_sources`) and packages everything
    reachable from it. Subpackages that nothing in the root package imports are not reachable, so pass them in
    `extra_dependencies`.

    With `include_oci_pex`, the wheel is also published as an OCI artifact, see `_plugin_oci_pex`. The Publish
    workflow publishes `provides/<plugin-name>:plugin-oci-artifact`.

    Args:
        extra_dependencies: Further addresses to add to the `python_distribution` `dependencies` field, for example
            `["./src/<plugin_name>/testing_utils"]`.
        include_oci_pex: Whether to also define `:plugin-pex` and `:plugin-oci-artifact`, the plugin as a PEX inside
            an OCI artifact.
    """
    tags = ["plugin_wheel", COMMON_MACRO_TAG]
    pypi_name, root_pkg_name = _plugin_names()
    file(name="pyproject", source="pyproject.toml", tags=tags)
    file(name="readme", source="README.md", tags=tags)
    # setuptools only accepts license files inside the project directory.
    relocated_files(name="license", files_targets=["//:license"], src="", dest=f"provides/{pypi_name}", tags=tags)
    # With `generate_setup=False`, setuptools reads `pyproject.toml` directly.
    python_distribution(
        name="plugin-whl",
        dependencies=[
            ":license",
            ":pyproject",
            ":readme",
            f"provides/{pypi_name}/src/{root_pkg_name}",
            *(extra_dependencies or []),
        ],
        provides=python_artifact(name=pypi_name),
        wheel=True,
        sdist=False,
        generate_setup=False,
        tags=tags,
    )
    if include_oci_pex:
        _plugin_oci_pex(pypi_name)


def _plugin_oci_pex(pypi_name: str) -> None:
    """
    Defines the plugin as a PEX inside an OCI artifact, next to `:plugin-whl`:

        - `:scm-version-for-oci-artifact`: `provides/<plugin-name>/version.txt`, the plugin's version from the same
          git tags as `:scm-version-for-wheel`, as one line; never written to the tree.
        - `:plugin-pex`: `<plugin-name>.pex`, a zipapp `pex_binary` holding the plugin's wheel and the
          `pants-plugin-developer-utils` wheel every plugin's wheel requires, and nothing else: no third-party
          requirements, so no `pantsbuild.pants`. It imports `pants` from the interpreter that runs it.
        - `:plugin-oci-artifact`: the PEX as an OCI artifact, tagged with the version and `latest`, published to
          `<OCI_REGISTRY>/<OCI_REPOSITORY_PREFIX>/<plugin-name>` by `pants publish`.
    """
    tags = ["plugin_oci_pex", COMMON_MACRO_TAG]
    # Pants builds these wheels and installs them into the PEX as distributions, in place of their loose sources. Every
    # plugin's `pyproject.toml` requires `pants-plugin-developer-utils`, which the PEX must then hold as a distribution
    # too, or it refuses to boot.
    dev_utils = "pants-plugin-developer-utils"
    wheels = [":plugin-whl"] if pypi_name == dev_utils else [":plugin-whl", f"provides/{dev_utils}:plugin-whl"]
    scm_version_file(
        name="scm-version-for-oci-artifact",
        tag_prefix=_release_tag_prefix(pypi_name),
        generate_to=f"provides/{pypi_name}/version.txt",
        # An OCI tag cannot contain `+`, so dev builds drop the `+g<sha>` local part and are tagged `X.Y.Z.devN`.
        local_scheme="no-local-version",
        tags=tags,
    )
    pex_binary(
        name="plugin-pex",
        # A flat name, so `oras pull` restores `<plugin-name>.pex` rather than `provides.<plugin-name>/plugin-pex.pex`.
        output_path=f"{pypi_name}.pex",
        dependencies=wheels,
        # Only the wheels above: with `include_requirements`, the PEX would bundle `pantsbuild.pants` (~30 MB, platform
        # specific), which the host Pants supplies. `fallback` lets the PEX import `pants` from the running interpreter,
        # which works in `zipapp` mode but not in `venv` mode, where the venv is built from the base interpreter.
        execution_mode="zipapp",
        include_requirements=False,
        include_sources=True,
        include_tools=True,
        inherit_path="fallback",
        tags=tags,
    )
    oci_artifact(
        name="plugin-oci-artifact",
        packages=[":plugin-pex"],
        oci_artifact_type=OCI_PEX_ARTIFACT_TYPE,
        oci_tags=["latest"],
        oci_tag_files=[":scm-version-for-oci-artifact"],
        oci_registries=[OCI_REGISTRY],
        oci_repository=f"{OCI_REPOSITORY_PREFIX}/{pypi_name}",
        tags=tags,
    )
