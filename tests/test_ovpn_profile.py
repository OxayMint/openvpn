#!/usr/bin/env python3
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ovpn_profile  # noqa: E402


SAMPLE_PROFILE = """\
# Automatically generated OpenVPN client config file
client
dev tun
proto udp
remote access.example 1194
<ca>
-----BEGIN CERTIFICATE-----
MIIB
-----END CERTIFICATE-----
</ca>
remote access.example 443 tcp
port 443
"""


class RewriteProfileTests(unittest.TestCase):
    def test_rewrites_udp_and_tcp_remotes(self) -> None:
        out = ovpn_profile.rewrite_profile(SAMPLE_PROFILE, "13.143.223.160", "8443", "1194")
        self.assertIn("remote 13.143.223.160 1194", out)
        self.assertIn("remote 13.143.223.160 8443 tcp", out)
        self.assertNotIn("remote access.example 443", out)
        self.assertIn("port 8443", out)
        self.assertNotIn("port 443", out)

    def test_rewrites_tcp_hint_even_when_port_is_custom(self) -> None:
        text = "remote vpn.example 9443 tcp\n"
        out = ovpn_profile.rewrite_profile(text, "13.143.223.160", "8443", "1194")
        self.assertEqual(out, "remote 13.143.223.160 8443 tcp\n")

    def test_empty_profile_raises(self) -> None:
        with self.assertRaises(ValueError):
            ovpn_profile.rewrite_profile("  \n", "h", "8443", "1194")

    def test_write_profile_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "profiles", "calogero007.ovpn")
            ovpn_profile.write_profile(SAMPLE_PROFILE, "13.143.223.160", "8443", "1194", out)
            data = Path(out).read_text(encoding="utf-8")
            self.assertIn("remote 13.143.223.160 8443 tcp", data)


class UsersManifestTests(unittest.TestCase):
    def test_calogero007_is_declared(self) -> None:
        manifest = json.loads((ROOT / "users.json").read_text(encoding="utf-8"))
        usernames = [user["username"] for user in manifest["users"]]
        self.assertIn("calogero007", usernames)
        user = next(item for item in manifest["users"] if item["username"] == "calogero007")
        self.assertTrue(user["autologin"])


class FakeHTTPResponse:
    def __init__(self, payload: bytes, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._payload = payload
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class RemoteExportTests(unittest.TestCase):
    def test_remote_export_creates_missing_user_and_writes_profile(self) -> None:
        calls: list[tuple[str, str, object]] = []

        def fake_urlopen(req: object, context: object = None, timeout: object = None) -> FakeHTTPResponse:
            method = req.get_method()  # type: ignore[attr-defined]
            url = req.full_url  # type: ignore[attr-defined]
            body = req.data.decode("utf-8") if req.data else ""  # type: ignore[attr-defined]
            payload = json.loads(body) if body else None
            calls.append((method, url, payload))
            if url.endswith("/api/auth/login/userpassword"):
                return FakeHTTPResponse(
                    json.dumps(
                        {
                            "auth_token": "token-1",
                            "user_properties": {"user_type": "admin"},
                        }
                    ).encode()
                )
            if url.endswith("/api/users/list"):
                return FakeHTTPResponse(json.dumps({"profiles": [], "total": 0}).encode())
            if url.endswith("/api/users/create"):
                return FakeHTTPResponse(json.dumps({"name": "calogero007"}).encode())
            if url.endswith("/api/auth/password/change"):
                return FakeHTTPResponse(json.dumps({"detail": "ok"}).encode())
            if url.endswith("/api/userprop/set"):
                return FakeHTTPResponse(b"[]")
            if url.endswith("/api/profiles/create"):
                return FakeHTTPResponse(SAMPLE_PROFILE.encode(), headers={"Content-Type": "text/plain"})
            raise AssertionError(f"unexpected url {url}")

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "calogero007.ovpn")
            with patch("ovpn_profile.urllib.request.urlopen", side_effect=fake_urlopen):
                ovpn_profile.remote_export(
                    api_base="https://13.143.223.160:943",
                    admin_user="openvpn",
                    admin_password="admin-secret",
                    username="calogero007",
                    user_password="user-secret",
                    autologin=True,
                    host="13.143.223.160",
                    tcp_port="8443",
                    udp_port="1194",
                    out=out,
                )
            data = Path(out).read_text(encoding="utf-8")

        self.assertIn("remote 13.143.223.160 8443 tcp", data)
        paths = [url.rsplit("/", 1)[-1] for _method, url, _payload in calls]
        self.assertEqual(
            paths,
            [
                "userpassword",
                "list",
                "create",
                "change",
                "set",
                "create",
            ],
        )

    def test_remote_export_requires_password_for_new_user(self) -> None:
        def fake_urlopen(req: object, context: object = None, timeout: object = None) -> FakeHTTPResponse:
            url = req.full_url  # type: ignore[attr-defined]
            if url.endswith("/api/auth/login/userpassword"):
                return FakeHTTPResponse(
                    json.dumps(
                        {
                            "auth_token": "token-1",
                            "user_properties": {"user_type": "admin"},
                        }
                    ).encode()
                )
            if url.endswith("/api/users/list"):
                return FakeHTTPResponse(json.dumps({"profiles": [], "total": 0}).encode())
            raise AssertionError(f"unexpected url {url}")

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "calogero007.ovpn")
            with patch("ovpn_profile.urllib.request.urlopen", side_effect=fake_urlopen):
                with self.assertRaises(ovpn_profile.AccessServerError):
                    ovpn_profile.remote_export(
                        api_base="https://13.143.223.160:943",
                        admin_user="openvpn",
                        admin_password="admin-secret",
                        username="calogero007",
                        user_password=None,
                        autologin=True,
                        host="13.143.223.160",
                        tcp_port="8443",
                        udp_port="1194",
                        out=out,
                    )


class CliTests(unittest.TestCase):
    def test_rewrite_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "calogero007.ovpn")
            with patch("sys.stdin", io.StringIO(SAMPLE_PROFILE)):
                rc = ovpn_profile._cli(
                    ["rewrite", "13.143.223.160", "8443", "1194", out]
                )
            self.assertEqual(rc, 0)
            self.assertIn("8443 tcp", Path(out).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
