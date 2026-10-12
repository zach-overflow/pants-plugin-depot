from pants.backend.python.target_types import PythonResolveField
from pants.engine.target import COMMON_TARGET_FIELDS, OptionalSingleSourceField, StringField, Target
from pants.util.strutil import help_text

DEFAULT_TAG_REGEX = r"^(?:[\w-]+-)?(?P<version>[vV]?\d+(?:\.\d+){0,2}[^\+]*)(?:\+.*)?$"
"""setuptools-scm's default tag regex, as Pants' `vcs_version` target also uses it."""


class ScmVersionDummySourceField(OptionalSingleSourceField):
    """A dummy SourceField for participation in the codegen machinery."""

    alias = "_dummy_source"  # Leading underscore omits the field from help.
    help = "A version string generated from VCS information."


class ScmVersionTagPrefixField(StringField):
    """Literal prefix that selects this target's tags."""

    alias = "tag_prefix"
    default = None
    help = help_text(
        """
        Literal prefix a git tag must start with to be considered for this target, e.g. `my-package-v`.

        setuptools-scm then runs `git describe --match '<tag_prefix>*[0-9]*'` and strips the prefix before
        applying `tag_regex`. This lets every package in a monorepo be tagged `<package>-vX.Y.Z` and
        versioned independently. Without it, the nearest tag of any package is used.
        """
    )


class ScmVersionTagRegexField(StringField):
    """Regex extracting the version from a tag."""

    alias = "tag_regex"
    default = DEFAULT_TAG_REGEX
    help = help_text(
        """
        A Python regex string to extract the version string from a VCS tag, applied after `tag_prefix` is
        stripped.

        The regex needs to contain either a single match group, or a group named `version`, that captures
        the actual version information.

        Note that this is unrelated to the `tags` field and Pants's own tags concept.

        See https://setuptools-scm.readthedocs.io/en/latest/config/ for implementation details.
        """
    )


class ScmVersionVersionSchemeField(StringField):
    """setuptools-scm version scheme."""

    alias = "version_scheme"
    help = help_text(
        """
        The version scheme to configure setuptools-scm to use, e.g. `guess-next-dev` (the default) or
        `no-guess-dev`. See https://setuptools-scm.readthedocs.io/en/latest/extending/#version-number-construction
        """
    )


class ScmVersionLocalSchemeField(StringField):
    """setuptools-scm local scheme."""

    alias = "local_scheme"
    help = help_text(
        """
        The local scheme to configure setuptools-scm to use, e.g. `node-and-date` (the default) or
        `no-local-version`. See https://setuptools-scm.readthedocs.io/en/latest/extending/#version-number-construction
        """
    )


class ScmVersionGenerateToField(StringField):
    """Path of the generated module."""

    alias = "generate_to"
    required = True
    help = help_text(
        """
        Generate the version data to this path, relative to the build root, using the `template` field.

        The generated output is not written to disk in the source tree. It is available as a generated
        dependency to code that depends on this target, and is packaged with that code.
        """
    )


class ScmVersionTemplateField(StringField):
    """Format string of the generated module."""

    alias = "template"
    required = True
    help = help_text(
        """
        Generate the version data using this format string, which takes a `version` format kwarg, e.g.
        `'__version__ = "{version}"'`.
        """
    )


class ScmVersionPythonResolveField(PythonResolveField):
    """The resolve the generated module belongs to, for dependency inference."""

    alias = "python_resolve"


class ScmVersionTarget(Target):
    """Generates a version string from git tags with setuptools-scm."""

    alias = "scm_version"
    core_fields = (
        *COMMON_TARGET_FIELDS,
        ScmVersionTagPrefixField,
        ScmVersionTagRegexField,
        ScmVersionVersionSchemeField,
        ScmVersionLocalSchemeField,
        ScmVersionDummySourceField,
        ScmVersionGenerateToField,
        ScmVersionTemplateField,
        ScmVersionPythonResolveField,
    )
    help = help_text(
        """
        Generates a version string from git tags with setuptools-scm.

        A drop-in superset of Pants' `vcs_version` target that adds `tag_prefix`, so every package of a
        monorepo can be tagged and versioned on its own. Only the fields of this target configure
        setuptools-scm; any `[tool.setuptools_scm]` table in the repo is ignored.

        Requires setuptools-scm >= 10 (see the `[setuptools-scm-tool]` subsystem).
        """
    )
