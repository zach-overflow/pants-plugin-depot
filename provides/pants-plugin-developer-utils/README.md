# Pants Plugin Developer Utils

Collection of utilities for writing and testing pantsbuild plugins.


## Type Aliases

Some type aliases for common pants plugin type hints are offered.

* `Iterable[Rule | UnionRule]` &rarr; `CollectedRules`
* `Iterable[type[Target]]` &rarr; `CollectedTargetTypes`


```python
# your pants plugin's `register.py` file
from pants_plugin_developer_utils import CollectedRules, CollectedTargets

from your_plugin.module import rules as your_rules
from your_plugin.target_types import YourCustomTarget


def rules() -> CollectedRules:
	return (your_rules(),)


def target_types() -> CollectedTargetTypes:
	return (YourCustomTarget,)
```

## Testing Utilities

### Pytest Fixtures
TODO: fill this in

