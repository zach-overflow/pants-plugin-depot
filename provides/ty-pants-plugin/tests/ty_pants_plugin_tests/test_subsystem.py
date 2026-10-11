import re

import pytest
from pants.backend.python.util_rules.interpreter_constraints import InterpreterConstraints
from pants.core.util_rules.external_tool import UnsupportedVersion
from pants.engine.platform import Platform

from ty_pants_plugin.subsystem import Ty
from ty_pants_plugin_tests.conftest import make_ty

_TARGET_TRIPLES = {
    Platform.linux_arm64: "aarch64-unknown-linux-musl",
    Platform.linux_x86_64: "x86_64-unknown-linux-musl",
    Platform.macos_arm64: "aarch64-apple-darwin",
    Platform.macos_x86_64: "x86_64-apple-darwin",
}


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_url(platform: Platform) -> None:
    ty = make_ty()

    assert ty.generate_url(platform) == (
        f"https://github.com/astral-sh/ty/releases/download/{Ty.default_version}/ty-{_TARGET_TRIPLES[platform]}.tar.gz"
    )


@pytest.mark.parametrize("platform", list(Platform))
def test_generate_exe(platform: Platform) -> None:
    assert make_ty().generate_exe(platform) == f"./ty-{_TARGET_TRIPLES[platform]}/ty"


@pytest.mark.parametrize("platform", list(Platform))
def test_default_known_versions_cover_every_platform(platform: Platform) -> None:
    known = make_ty().known_version(platform)

    assert known is not None
    assert known.version == Ty.default_version
    assert known.platform == platform.value
    assert re.fullmatch(r"[0-9a-f]{64}", known.sha256)
    assert known.filesize > 0
    assert known.url_override is None


@pytest.mark.parametrize("platform", list(Platform))
def test_get_request(platform: Platform) -> None:
    ty = make_ty()

    request = ty.get_request(platform)

    assert request.download_file_request.url == ty.generate_url(platform)
    assert request.exe == ty.generate_exe(platform)


def test_unsupported_version_is_rejected() -> None:
    with pytest.raises(UnsupportedVersion):
        make_ty(version="0.0.1")


def test_config_request_with_discovery() -> None:
    request = make_ty().config_request()

    assert request.specified == ()
    assert request.specified_option_name == "[ty].config"
    assert request.discovery is True
    assert request.check_existence == ("ty.toml",)
    assert dict(request.check_content) == {"pyproject.toml": b"[tool.ty"}


def test_config_request_with_explicit_config() -> None:
    request = make_ty(config="configs/ty.toml", config_discovery=False).config_request()

    assert request.specified == ("configs/ty.toml",)
    assert request.discovery is False


def test_interpreter_constraints() -> None:
    ty = make_ty(interpreter_constraints=["CPython==3.12.*"])

    assert ty.interpreter_constraints == InterpreterConstraints(["CPython==3.12.*"])
