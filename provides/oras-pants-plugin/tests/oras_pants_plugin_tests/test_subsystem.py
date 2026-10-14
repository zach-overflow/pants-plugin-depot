import re

import pytest
from pants.core.util_rules.external_tool import UnsupportedVersion
from pants.engine.platform import Platform

from oras_pants_plugin.subsystem import ORAS_BASE_ENV_VAR_NAMES, Oras
from oras_pants_plugin_tests.conftest import OrasFactory

_ASSET_PLATFORMS = {
    Platform.linux_arm64: "linux_arm64",
    Platform.linux_x86_64: "linux_amd64",
    Platform.macos_arm64: "darwin_arm64",
    Platform.macos_x86_64: "darwin_amd64",
}


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_url(platform: Platform, oras_factory: OrasFactory) -> None:
    version = Oras.default_version

    assert oras_factory().generate_url(platform) == (
        f"https://github.com/oras-project/oras/releases/download/v{version}/"
        f"oras_{version}_{_ASSET_PLATFORMS[platform]}.tar.gz"
    )


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_exe(platform: Platform, oras_factory: OrasFactory) -> None:
    assert oras_factory().generate_exe(platform) == "./oras"


@pytest.mark.parametrize("platform", list(Platform))
def test_default_known_versions_cover_every_platform(platform: Platform, oras_factory: OrasFactory) -> None:
    known = oras_factory().known_version(platform)

    assert known is not None
    assert known.version == Oras.default_version
    assert known.platform == platform.value
    assert re.fullmatch(r"[0-9a-f]{64}", known.sha256)
    assert known.filesize > 0
    assert known.url_override is None


@pytest.mark.parametrize("platform", list(Platform))
def test_get_request(platform: Platform, oras_factory: OrasFactory) -> None:
    oras = oras_factory()

    request = oras.get_request(platform)

    assert request.download_file_request.url == oras.generate_url(platform)
    assert request.exe == oras.generate_exe(platform)


def test_unsupported_version_is_rejected(oras_factory: OrasFactory) -> None:
    with pytest.raises(UnsupportedVersion):
        oras_factory(version="1.0.0")


def test_credentials_env_vars_are_always_passed() -> None:
    """`oras` finds `docker login` credentials through these, so they must not depend on `extra_env_vars`."""
    assert set(ORAS_BASE_ENV_VAR_NAMES) == {"PATH", "HOME", "DOCKER_CONFIG"}
