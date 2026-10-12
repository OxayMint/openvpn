from __future__ import annotations

from types import SimpleNamespace

import pytest

import ovpn


SAMPLE_PROFILE = """\
client
dev tun
proto udp
remote vpn.example 1194
remote vpn.example 443 tcp
port 443
<ca>
CERT
</ca>
"""


def test_validate_username_accepts_simple_names():
    assert ovpn.validate_username("  vpnuser  ") == "vpnuser"
    assert ovpn.validate_username("Alice.1-two_3") == "Alice.1-two_3"


@pytest.mark.parametrize(
    "name",
    ["", "   ", "has space", "bad/name", "../x", "-leading", "semi;colon", "a" * 65],
)
def test_validate_username_rejects_bad_names(name):
    with pytest.raises(ValueError):
        ovpn.validate_username(name)


def test_rewrite_profile_maps_published_ports():
    rewritten = ovpn.rewrite_profile(SAMPLE_PROFILE, "13.143.223.160", "8443", "1194")
    assert "remote 13.143.223.160 1194" in rewritten
    assert "remote 13.143.223.160 8443 tcp" in rewritten
    assert "port 8443" in rewritten
    assert "remote vpn.example" not in rewritten
    assert "port 443" not in rewritten


def test_rewrite_profile_rejects_empty():
    with pytest.raises(ovpn.ProfileError):
        ovpn.rewrite_profile(" \n", "host", "8443", "1194")


class FakeContainer:
    def __init__(self, existing=None, profile=SAMPLE_PROFILE):
        self.existing = set(existing or [])
        self.profile = profile
        self.status = "running"
        self.calls: list[list[str]] = []

    def exec_run(self, cmd, demux=False):
        self.calls.append(list(cmd))
        action = cmd[-1]
        if action == "UserPropGet":
            username = cmd[cmd.index("--user") + 1]
            if username in self.existing:
                return SimpleNamespace(exit_code=0, output=(b"type=user_connect", b""))
            return SimpleNamespace(exit_code=1, output=(b"", b"NO_HOST_INFO"))
        if action == "GetAutologin":
            return SimpleNamespace(exit_code=0, output=(self.profile.encode(), b""))
        return SimpleNamespace(exit_code=0, output=(b"OK", b""))


class FakeClient:
    def __init__(self, container: FakeContainer):
        self.containers = SimpleNamespace(get=lambda name: container)


def test_create_ovpn_profile_creates_missing_user_and_rewrites(monkeypatch):
    monkeypatch.setenv("PUBLIC_HOST", "13.143.223.160")
    monkeypatch.setenv("HOST_HTTPS_PORT", "8443")
    monkeypatch.setenv("HOST_UDP_PORT", "1194")
    monkeypatch.setenv("CONTAINER_NAME", "openvpn-as")
    container = FakeContainer()
    profile = ovpn.create_ovpn_profile("vpnuser", docker_client=FakeClient(container))

    actions = [call[-1] for call in container.calls]
    assert "UserPropPut" in actions
    assert "SetPassword" in actions
    assert "GetAutologin" in actions
    assert "remote 13.143.223.160 8443 tcp" in profile
    assert profile.startswith("client")


def test_create_ovpn_profile_skips_password_for_existing_user(monkeypatch):
    monkeypatch.setenv("PUBLIC_HOST", "13.143.223.160")
    container = FakeContainer(existing={"vpnuser"})
    ovpn.create_ovpn_profile("vpnuser", docker_client=FakeClient(container))
    actions = [call[-1] for call in container.calls]
    assert "SetPassword" not in actions
    assert "GetAutologin" in actions


def test_create_ovpn_profile_requires_public_host(monkeypatch):
    monkeypatch.delenv("PUBLIC_HOST", raising=False)
    with pytest.raises(ovpn.ProfileError, match="PUBLIC_HOST"):
        ovpn.create_ovpn_profile("vpnuser", docker_client=FakeClient(FakeContainer()))
