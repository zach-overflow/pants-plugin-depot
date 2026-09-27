from pyproject_fmt_pants_plugin._version import __version__


def test_version_is_derived_from_git() -> None:
    assert __version__ != "0.0.0.dev0"
