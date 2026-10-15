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


def plugin_root_sources(extra_dependencies: list[str] | None = None) -> None:
    """
    Defines the targets of a plugin's root package. Call it once from `provides/<plugin-name>/src/<plugin_name>/BUILD`.

    Generates:
        - `:pytyped-marker`: the `py.typed` marker file.
        - `:scm-version`: `version.py`, generated from the `<plugin-name>-vX.Y.Z` git tags at build time; never written
          to the tree.
        - the `python_sources` of the package, depending on both of the above.

    Args:
        extra_dependencies: Further addresses to add to the `python_sources` `dependencies` field, for example
            `["./lockfile_resource:lockfile-resource-module"]`.
    """
    tags = ["plugin_root_sources", COMMON_MACRO_TAG]
    pypi_name, root_pkg_name = _plugin_names()
    resource(name="pytyped-marker", source="py.typed", tags=tags)
    scm_version(
        name="scm-version",
        tag_prefix=f"{pypi_name}-v",
        generate_to=f"provides/{pypi_name}/src/{root_pkg_name}/version.py",
        template='__version__ = "{version}"\n',
        tags=tags,
    )
    python_sources(dependencies=[":pytyped-marker", ":scm-version", *(extra_dependencies or [])], tags=tags)


def plugin_wheel(extra_dependencies: list[str] | None = None) -> None:
    """
    Defines a plugin's `:plugin-whl` `python_distribution` and the targets it packages. Call it once from
    `provides/<plugin-name>/BUILD`. The Publish workflow builds `provides/<plugin-name>:plugin-whl`.

    The wheel depends on the plugin's root `python_sources` (see `plugin_root_sources`) and packages everything
    reachable from it. Subpackages that nothing in the root package imports are not reachable, so pass them in
    `extra_dependencies`.

    Args:
        extra_dependencies: Further addresses to add to the `python_distribution` `dependencies` field, for example
            `["./src/<plugin_name>/testing_utils"]`.
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
        sdist=False,
        wheel=True,
        generate_setup=False,
        tags=tags,
    )
