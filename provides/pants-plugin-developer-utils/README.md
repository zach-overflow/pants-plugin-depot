# pants-plugin-developer-utils

Utilities for writing and testing [Pantsbuild](https://www.pantsbuild.org/) plugins: type aliases for the
`register.py` hooks, and pytest fixtures around `pants.testutil.rule_runner.RuleRunner`.

## Installation

The package is on [PyPI](https://pypi.org/project/pants-plugin-developer-utils/).

```bash
pip install pants-plugin-developer-utils            # type aliases only
pip install "pants-plugin-developer-utils[testing]" # plus the pytest fixtures
```

In a Pants repo, add the requirement to the resolve your plugin code and tests use. The `testing` extra
also needs `pantsbuild.pants.testutil` at the same version as the Pants you test against. It is not a
declared dependency, because declaring it would pin a Pants version.

Pants loads plugins into its own interpreter, so the package requires the Python version Pants runs on.

## Type aliases

| Alias                  | Expands to                       | Use as the return type of |
| :--------------------- | :------------------------------- | :------------------------ |
| `CollectedRules`       | `Iterable[Rule \| UnionRule]`    | `rules()`                 |
| `CollectedTargetTypes` | `Iterable[type[Target]]`         | `target_types()`          |

```python
# your plugin's `register.py`
from pants_plugin_developer_utils import CollectedRules, CollectedTargetTypes

from your_plugin.module import rules as your_rules
from your_plugin.target_types import YourCustomTarget


def rules() -> CollectedRules:
    return (*your_rules(),)


def target_types() -> CollectedTargetTypes:
    return (YourCustomTarget,)
```

The aliases are only needed for type checking. To keep your published plugin free of a runtime dependency on
this package, import them under `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pants_plugin_developer_utils import CollectedRules
```

## Testing utilities

`pants_plugin_developer_utils.testing_utils` provides:

- `rule_runner_factory`: a function-scoped fixture returning a factory that builds a `RuleRunner` from
  `rules` plus any optional `RuleRunner` keyword arguments.
- `RuleRunnerFactory`: the type of that factory, for annotating fixtures that take it.
- `RuleRunnerOptionalKwargs`: a `TypedDict` of the optional `RuleRunner` constructor arguments.
- `RuleRunnerCollectedRules`: `CollectedRules` widened to accept `QueryRule`.

```python
# conftest.py
import pytest
from pants.core.goals.package import BuiltPackage
from pants.core.target_types import FileTarget
from pants.testutil.rule_runner import QueryRule, RuleRunner

from pants_plugin_developer_utils.testing_utils import RuleRunnerFactory
from your_plugin import rules as your_rules
from your_plugin.goals.package import YourFieldSet


@pytest.fixture
def your_rule_runner(rule_runner_factory: RuleRunnerFactory) -> RuleRunner:
    return rule_runner_factory(
        rules=[*your_rules(), QueryRule(BuiltPackage, [YourFieldSet])],
        target_types=[FileTarget],
    )
```

The fixtures register through a `pytest11` entry point, so they are available as soon as the wheel is
installed. When consuming this package as first-party source instead, import the fixture into a
`conftest.py`:

```python
from pants_plugin_developer_utils.testing_utils import rule_runner_factory  # noqa: F401
```

## Supported versions

| Package | Pants  | Python |
| :------ | :----- | :----- |
| `0.x`   | `2.33` | `3.14` |

## Releases

Wheels are published to [PyPI](https://pypi.org/project/pants-plugin-developer-utils/). Release notes live in
the [changelog](https://github.com/zach-overflow/pants-plugin-depot/blob/main/provides/pants-plugin-developer-utils/CHANGELOG.md)
and on the [GitHub releases page](https://github.com/zach-overflow/pants-plugin-depot/releases).

## Contributing, Bug Reports and Feature Requests

This package lives in the [pants-plugin-depot](https://github.com/zach-overflow/pants-plugin-depot) repo.
See its [CONTRIBUTING.md](https://github.com/zach-overflow/pants-plugin-depot/blob/main/CONTRIBUTING.md), or
open an [issue](https://github.com/zach-overflow/pants-plugin-depot/issues/new/choose).
