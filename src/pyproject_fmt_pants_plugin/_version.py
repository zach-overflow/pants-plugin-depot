"""
Version for the `pyproject-fmt-pants-plugin` distribution (read by setuptools at wheel-build time).

Pants generates `_scm_version.py` from the git state via the `vcs_version` target (setuptools-scm under
the hood), so Pants-built wheels carry the real version. The fallback reads the sibling `_scm_version.py`
file without importing the package. When that file doesn't exist on disk (builds outside Pants), the dev
placeholder applies.
"""

try:
    from pyproject_fmt_pants_plugin._scm_version import version as __version__
except ImportError:
    import ast
    from pathlib import Path

    def _sibling_scm_version() -> str | None:
        scm_path = Path(__file__).with_name("_scm_version.py")
        if not scm_path.exists():
            return None
        for node in ast.parse(scm_path.read_text()).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "version" for target in node.targets
            ):
                return str(ast.literal_eval(node.value))
        return None

    __version__ = _sibling_scm_version() or "0.0.0.dev0"
