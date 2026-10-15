import pytest

from oras_pants_plugin.constants import ALL_DEFAULT_REGISTRIES
from oras_pants_plugin.registries import (
    OCIRegistries,
    OCIRegistryAddressCollisionError,
    OCIRegistryError,
    OCIRegistryNotFoundError,
    OCIRegistryOptions,
)

_CONFIG = {
    "prod": {"address": "ghcr.io/my-org", "default": True},
    "local": {"address": "localhost:5000"},
    "default": {"address": "registry.example.com"},
}
_PROD = OCIRegistryOptions(address="ghcr.io/my-org", alias="prod", default=True)
_LOCAL = OCIRegistryOptions(address="localhost:5000", alias="local")
_EXAMPLE = OCIRegistryOptions(address="registry.example.com", alias="default", default=True)


def test_from_dict() -> None:
    registries = OCIRegistries.from_dict(_CONFIG)

    assert registries.default == (_PROD, _EXAMPLE)
    assert dict(registries.by_name) == {
        "ghcr.io/my-org": _PROD,
        "@prod": _PROD,
        "localhost:5000": _LOCAL,
        "@local": _LOCAL,
        "registry.example.com": _EXAMPLE,
        "@default": _EXAMPLE,
    }


def test_from_dict_empty() -> None:
    registries = OCIRegistries.from_dict({})

    assert registries.default == ()
    assert registries.resolve([ALL_DEFAULT_REGISTRIES]) == ()


@pytest.mark.parametrize(
    ("entry", "match"),
    [
        ({}, "non-empty `address`"),
        ({"address": ""}, "non-empty `address`"),
        ({"address": 5000}, "non-empty `address`"),
        ({"address": "ghcr.io", "skip_push": True}, r"Unknown keys \['skip_push'\]"),
    ],
)
def test_from_dict_rejects_bad_entries(entry: dict[str, object], match: str) -> None:
    with pytest.raises(OCIRegistryError, match=match):
        OCIRegistries.from_dict({"bad": entry})


def test_from_dict_rejects_duplicate_addresses() -> None:
    with pytest.raises(OCIRegistryAddressCollisionError, match="`ghcr.io` for aliases `a` and `b`"):
        OCIRegistries.from_dict({"a": {"address": "ghcr.io"}, "b": {"address": "ghcr.io"}})


def test_resolve_aliases_addresses_and_defaults() -> None:
    registries = OCIRegistries.from_dict(_CONFIG)

    assert registries.resolve(["@local"]) == (_LOCAL,)
    assert registries.resolve(["localhost:5000"]) == (_LOCAL,)
    assert registries.resolve([ALL_DEFAULT_REGISTRIES]) == (_PROD, _EXAMPLE)
    assert registries.resolve(["docker.io/me"]) == (OCIRegistryOptions(address="docker.io/me"),)
    assert registries.resolve(["@local", ALL_DEFAULT_REGISTRIES, "docker.io/me"]) == (
        _LOCAL,
        _PROD,
        _EXAMPLE,
        OCIRegistryOptions(address="docker.io/me"),
    )


def test_resolve_deduplicates_by_address() -> None:
    registries = OCIRegistries.from_dict(_CONFIG)

    assert registries.resolve(["@prod", "ghcr.io/my-org", ALL_DEFAULT_REGISTRIES, "@prod"]) == (_PROD, _EXAMPLE)


def test_resolve_rejects_unknown_alias() -> None:
    with pytest.raises(OCIRegistryNotFoundError, match="alias `staging`"):
        OCIRegistries.from_dict(_CONFIG).resolve(["@staging"])
