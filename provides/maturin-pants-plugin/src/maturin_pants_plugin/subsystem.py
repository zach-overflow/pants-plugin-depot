from collections.abc import Sequence
from typing import ClassVar

from pants.backend.python.subsystems.python_tool_base import PythonToolBase
from pants.backend.python.target_types import ConsoleScript
from pants.core.goals.resolves import ExportableTool
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.option.option_types import BoolOption, IntOption, SkipOption, StrListOption, StrOption
from pants.util.strutil import softwrap

from pants_plugin_developer_utils import CollectedRules


class Maturin(PythonToolBase):
    """Controls the `maturin` pantsbuild plugin for building rust-based Python wheels."""

    options_scope = "maturin"
    name = "maturin"
    help_short = "The pantsbuild options for the `maturin` build tool for building python wheels from rust projects."
    default_version = "1.15.0"
    default_main = ConsoleScript("maturin")
    # Only constrains the interpreter that runs `maturin` itself. The wheels' target interpreters are `interpreter`.
    register_interpreter_constraints = True
    # A list, not a tuple: Pants uses it as the default of the list-typed `interpreter_constraints` option.
    default_interpreter_constraints: ClassVar[Sequence[str]] = ["CPython>=3.14,<3.15"]
    # MUST match the `maturin-tool` requirement in `provides/maturin-pants-plugin/BUILD`.
    default_requirements = ("maturin>=1.15.0,<2",)
    default_lockfile_resource = ("maturin_pants_plugin.lockfile_resource", "maturin_lockfile.json")

    # `[maturin]` section of `pants.toml` options below:
    skip = SkipOption("publish")
    bindings = StrOption(
        default="pyo3",
        help=softwrap(
            """
            Which kind of bindings to use for `maturin` builds.
            Possible values are: 'pyo3', 'pyo3-ffi', 'cffi', 'uniffi', 'bin'.
            """
        ),
        advanced=True,
    )
    compatibility = StrOption(
        default="pypi",
        help=softwrap(
            """
            Controls the platform tag and PyPI compatibility.
            See `maturin` docs on the `--compatibility` flag for more info.
            """
        ),
        advanced=True,
    )
    interpreter = StrListOption(
        default=["python3.12", "python3.13", "python3.14"],
        help=softwrap(
            """
            The python interpreter version(s) to build wheels for with `maturin build`, given as the executables of
            interpreters such as `python3.9` or `/usr/bin/python3.8`. They are looked up on the `PATH` passed to the
            build process. Set to `[]` to omit `--interpreter` and let `maturin` decide, e.g. for `bin` bindings.
            """
        ),
    )
    jobs = IntOption(
        default=None, help="Number of parallel jobs to run with `maturin`, defaults to # of CPUs.", advanced=True
    )
    profile_guided_optimization = BoolOption(
        default=False,
        help=softwrap(
            """
            If `true`, build with Profile-Guided Optimization (PGO).
            Requires `pgo-command` to be set in `[tool.maturin]` in pyproject.toml.
            This performs a three-phase build: instrumented build, profile training, and optimized rebuild.
            """
        ),
        advanced=True,
    )
    release = BoolOption(
        default=True, help="Build maturin artifacts in release mode, with optimizations.", advanced=True
    )
    skip_existing = BoolOption(
        default=False,
        help=softwrap(
            """
            If `true`, pass `--skip-existing` to `maturin upload` so files that already exist in the registry
            are skipped instead of failing the upload. Only PyPI is guaranteed to support this.
            """
        ),
        advanced=True,
    )
    extra_env_vars = StrListOption(
        default=[],
        help=softwrap(
            """
            Additional environment variables to make available to `maturin` processes. Entries are either strings
            in the form `ENV_VAR=value` to use explicitly, or just `ENV_VAR` to copy the value from Pants's own
            environment. `PATH`, `HOME`, `CARGO_HOME` and `RUSTUP_HOME` are always passed through so that `cargo`,
            `rustc` and the `interpreter` executables can be found. Example: `["RUSTFLAGS=-C target-cpu=native"]`.

            Note that the values of these variables become part of the build's cache key, while the installed rust
            toolchain version does not.
            """
        ),
        advanced=True,
    )


def rules() -> CollectedRules:
    return (*collect_rules(), UnionRule(ExportableTool, Maturin))
