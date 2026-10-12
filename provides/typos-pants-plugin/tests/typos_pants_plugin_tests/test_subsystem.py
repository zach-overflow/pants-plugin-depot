import re

import pytest
from pants.core.util_rules.external_tool import UnsupportedVersion
from pants.engine.platform import Platform

from typos_pants_plugin.subsystem import Typos
from typos_pants_plugin_tests.conftest import TyposFactory

_TARGET_TRIPLES = {
    Platform.linux_arm64: "aarch64-unknown-linux-musl",
    Platform.linux_x86_64: "x86_64-unknown-linux-musl",
    Platform.macos_arm64: "aarch64-apple-darwin",
    Platform.macos_x86_64: "x86_64-apple-darwin",
}


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_url(platform: Platform, typos_factory: TyposFactory) -> None:
    typos = typos_factory()

    assert typos.generate_url(platform) == (
        "https://github.com/crate-ci/typos/releases/download/"
        f"v{Typos.default_version}/typos-v{Typos.default_version}-{_TARGET_TRIPLES[platform]}.tar.gz"
    )


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_exe(platform: Platform, typos_factory: TyposFactory) -> None:
    assert typos_factory().generate_exe(platform) == "./typos"


@pytest.mark.parametrize("platform", list(Platform))
def test_default_known_versions_cover_every_platform(platform: Platform, typos_factory: TyposFactory) -> None:
    known = typos_factory().known_version(platform)

    assert known is not None
    assert known.version == Typos.default_version
    assert known.platform == platform.value
    assert re.fullmatch(r"[0-9a-f]{64}", known.sha256)
    assert known.filesize > 0
    assert known.url_override is None


@pytest.mark.parametrize("platform", list(Platform))
def test_get_request(platform: Platform, typos_factory: TyposFactory) -> None:
    typos = typos_factory()

    request = typos.get_request(platform)

    assert request.download_file_request.url == typos.generate_url(platform)
    assert request.exe == typos.generate_exe(platform)


def test_unsupported_version_is_rejected(typos_factory: TyposFactory) -> None:
    with pytest.raises(UnsupportedVersion):
        typos_factory(version="1.0.0")


def test_config_request_with_discovery(typos_factory: TyposFactory) -> None:
    request = typos_factory().config_request(dirs=("docs", "docs/guides"))

    assert request.specified == ()
    assert request.specified_option_name == "[typos].config"
    assert request.discovery is True
    assert request.check_existence == tuple(
        sorted(
            [
                *(f"{d}{name}" for d in ("", "docs/", "docs/guides/") for name in ("typos.toml", "_typos.toml")),
                *(f"{d}.typos.toml" for d in ("", "docs/", "docs/guides/")),
            ]
        )
    )
    assert dict(request.check_content) == {
        "pyproject.toml": b"[tool.typos",
        "docs/pyproject.toml": b"[tool.typos",
        "docs/guides/pyproject.toml": b"[tool.typos",
        "Cargo.toml": b"metadata.typos",
        "docs/Cargo.toml": b"metadata.typos",
        "docs/guides/Cargo.toml": b"metadata.typos",
    }


def test_config_request_with_explicit_config(typos_factory: TyposFactory) -> None:
    request = typos_factory(config="configs/typos.toml", config_discovery=False).config_request(dirs=("docs",))

    assert request.specified == ("configs/typos.toml",)
    assert request.discovery is False
