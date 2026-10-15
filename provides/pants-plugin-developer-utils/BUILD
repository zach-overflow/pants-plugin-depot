# Defined in `etc/pants-macros/_internal_pants_macros.py`; see `pants plugin_wheel --help`.
# Nothing in the root package imports `testing_utils`, so the wheel depends on it explicitly.
plugin_wheel(extra_dependencies=["./src/pants_plugin_developer_utils/testing_utils"])

# `pytest` is the only third-party requirement in the shared resolve; every plugin's tests resolve to it.
python_requirements(name="reqs", source="pyproject.toml")
