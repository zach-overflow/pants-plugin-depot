# Defined in `etc/pants-macros/_internal_pants_macros.py`; see `pants plugin_wheel --help`.
plugin_wheel()

# Source of the bundled `maturin` tool lockfile. Regenerate with `pants generate-lockfiles --resolve=maturin`.
# The requirement MUST match `Maturin.default_requirements` in `src/maturin_pants_plugin/subsystem.py`.
python_requirement(name="maturin-tool", requirements=["maturin>=1.15.0,<2"], resolve="maturin")
