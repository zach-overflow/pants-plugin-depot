import re

import pytest
from pants.core.util_rules.external_tool import UnsupportedVersion
from pants.engine.platform import Platform

from actionlint_pants_plugin.subsystem import Actionlint
from actionlint_pants_plugin_tests.conftest import ActionlintFactory

_ASSET_PLATFORMS = {
    Platform.linux_arm64: "linux_arm64",
    Platform.linux_x86_64: "linux_amd64",
    Platform.macos_arm64: "darwin_arm64",
    Platform.macos_x86_64: "darwin_amd64",
}


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_url(platform: Platform, actionlint_factory: ActionlintFactory) -> None:
    version = Actionlint.default_version

    assert actionlint_factory().generate_url(platform) == (
        f"https://github.com/rhysd/actionlint/releases/download/v{version}/"
        f"actionlint_{version}_{_ASSET_PLATFORMS[platform]}.tar.gz"
    )


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_exe(platform: Platform, actionlint_factory: ActionlintFactory) -> None:
    assert actionlint_factory().generate_exe(platform) == "./actionlint"


@pytest.mark.parametrize("platform", list(Platform))
def test_default_known_versions_cover_every_platform(platform: Platform, actionlint_factory: ActionlintFactory) -> None:
    known = actionlint_factory().known_version(platform)

    assert known is not None
    assert known.version == Actionlint.default_version
    assert known.platform == platform.value
    assert re.fullmatch(r"[0-9a-f]{64}", known.sha256)
    assert known.filesize > 0
    assert known.url_override is None


@pytest.mark.parametrize("platform", list(Platform))
def test_get_request(platform: Platform, actionlint_factory: ActionlintFactory) -> None:
    actionlint = actionlint_factory()

    request = actionlint.get_request(platform)

    assert request.download_file_request.url == actionlint.generate_url(platform)
    assert request.exe == actionlint.generate_exe(platform)


def test_unsupported_version_is_rejected(actionlint_factory: ActionlintFactory) -> None:
    with pytest.raises(UnsupportedVersion):
        actionlint_factory(version="1.0.0")


def test_config_request_with_discovery(actionlint_factory: ActionlintFactory) -> None:
    request = actionlint_factory().config_request()

    assert request.specified == ()
    assert request.specified_option_name == "[actionlint].config"
    assert request.discovery is True
    assert request.check_existence == (".github/actionlint.yaml", ".github/actionlint.yml")
    assert not request.check_content


def test_config_request_with_explicit_config(actionlint_factory: ActionlintFactory) -> None:
    request = actionlint_factory(config="configs/actionlint.yaml", config_discovery=False).config_request()

    assert request.specified == ("configs/actionlint.yaml",)
    assert request.discovery is False
