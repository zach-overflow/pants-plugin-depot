"""Resolves `oci_registries` field entries against `[oras].registries`, modeled on Pants' docker backend."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Self

from pants.util.frozendict import FrozenDict
from pants.util.ordered_set import FrozenOrderedSet
from pants.util.strutil import softwrap

from oras_pants_plugin.constants import ALL_DEFAULT_REGISTRIES


class OCIRegistryError(ValueError):
    """A problem with `[oras].registries` or with an `oci_registries` entry referring to it."""


class OCIRegistryNotFoundError(OCIRegistryError):
    """An `oci_registries` entry names an `@alias` that `[oras].registries` does not define."""

    def __init__(self, alias: str) -> None:  # noqa: D107
        super().__init__(
            f"There is no OCI registry configured with alias `{alias}`. "
            "Use the `[oras].registries` option to define registry aliases."
        )


class OCIRegistryAddressCollisionError(OCIRegistryError):
    """Two `[oras].registries` entries share one `address`."""

    def __init__(self, first: OCIRegistryOptions, second: OCIRegistryOptions) -> None:  # noqa: D107
        super().__init__(
            softwrap(
                f"""
                Duplicated OCI registry address `{first.address}` for aliases `{first.alias}` and `{second.alias}`.
                Each `address` in `[oras].registries` must be unique.
                """
            )
        )


@dataclass(frozen=True)
class OCIRegistryOptions:
    """One registry: its `address` (host with optional port and path prefix) and whether it is used by default."""

    _KNOWN_KEYS: ClassVar[FrozenOrderedSet[str]] = FrozenOrderedSet({"address", "default"})

    address: str
    alias: str = ""
    default: bool = False

    @classmethod
    def from_dict(cls, alias: str, options: Mapping[str, Any]) -> Self:
        unknown = sorted(set(options) - cls._KNOWN_KEYS)
        if unknown:
            raise OCIRegistryError(
                f"Unknown keys {unknown} in `[oras].registries` entry `{alias}`; known keys: {sorted(cls._KNOWN_KEYS)}."
            )
        address = options.get("address")
        if not isinstance(address, str) or not address:
            raise OCIRegistryError(f"`[oras].registries` entry `{alias}` must set a non-empty `address` string.")
        return cls(address=address, alias=alias, default=bool(options.get("default", alias == "default")))


@dataclass(frozen=True)
class OCIRegistries:
    """The configured registries, addressable by `address` or `@alias`, and the ones used by default."""

    default: tuple[OCIRegistryOptions, ...]
    by_name: FrozenDict[str, OCIRegistryOptions]

    @classmethod
    def from_dict(cls, options: Mapping[str, Mapping[str, Any]]) -> Self:
        by_name: dict[str, OCIRegistryOptions] = {}
        for alias, entry in options.items():
            registry = OCIRegistryOptions.from_dict(alias, entry)
            if registry.address in by_name:
                raise OCIRegistryAddressCollisionError(by_name[registry.address], registry)
            by_name[registry.address] = registry
            by_name[f"@{alias}"] = registry
        default = tuple(
            sorted({registry for registry in by_name.values() if registry.default}, key=lambda r: r.address)
        )
        return cls(default=default, by_name=FrozenDict(by_name))

    def resolve(self, names: Iterable[str]) -> tuple[OCIRegistryOptions, ...]:
        """
        The registries `names` refer to, in order and without duplicates.

        A name is a configured `@alias`, a configured or verbatim address, or `ALL_DEFAULT_REGISTRIES`.
        """
        resolved: dict[str, OCIRegistryOptions] = {}
        for name in names:
            if name == ALL_DEFAULT_REGISTRIES:
                registries: Iterable[OCIRegistryOptions] = self.default
            elif name in self.by_name:
                registries = (self.by_name[name],)
            elif name.startswith("@"):
                raise OCIRegistryNotFoundError(name[1:])
            else:
                registries = (OCIRegistryOptions(address=name),)
            for registry in registries:
                resolved.setdefault(registry.address, registry)
        return tuple(resolved.values())
