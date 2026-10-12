#!/usr/bin/env python3
"""Rewrite Access Server .ovpn remotes and export profiles over the Web API."""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any


class AccessServerError(RuntimeError):
    """Raised when the Access Server Web API returns an error."""


def rewrite_profile(text: str, host: str, tcp_port: str, udp_port: str) -> str:
    """Point TCP/UDP remotes at the published host ports (8443:443 mapping)."""
    if not text.strip():
        raise ValueError("sacli returned an empty profile")

    def rewrite(match: re.Match[str]) -> str:
        port = match.group("port")
        rest = match.group("rest")
        proto_hint = rest.lower()
        if port == "443" or "tcp" in proto_hint:
            return f"remote {host} {tcp_port}{rest}"
        if port == "1194" or "udp" in proto_hint:
            return f"remote {host} {udp_port}{rest}"
        return f"remote {host} {port}{rest}"

    text = re.sub(
        r"^remote\s+\S+\s+(?P<port>\d+)(?P<rest>.*)$",
        rewrite,
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"^port\s+443\s*$", f"port {tcp_port}", text, flags=re.MULTILINE)
    text = re.sub(r"^port\s+1194\s*$", f"port {udp_port}", text, flags=re.MULTILINE)
    return text


def write_profile(text: str, host: str, tcp_port: str, udp_port: str, out: str) -> None:
    rewritten = rewrite_profile(text, host, tcp_port, udp_port)
    parent = os.path.dirname(os.path.abspath(out))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(rewritten)


class AccessServerClient:
    def __init__(self, base_url: str, insecure: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.context = ssl._create_unverified_context() if insecure else ssl.create_default_context()

    def _request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        accept: str = "application/json",
    ) -> tuple[int, str, dict[str, str]]:
        url = f"{self.base_url}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": accept}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["X-OpenVPN-As-AuthToken"] = self.token
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, body, {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, body, {k.lower(): v for k, v in exc.headers.items()}

    def _json(self, method: str, path: str, payload: Any | None = None) -> Any:
        status, body, _headers = self._request(method, path, payload)
        parsed: Any = None
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = body
        if status >= 400:
            reason = parsed
            if isinstance(parsed, dict):
                reason = parsed.get("reason") or parsed.get("detail") or parsed.get("message") or parsed
            raise AccessServerError(f"{method} {path} failed ({status}): {reason}")
        return parsed

    def login(self, username: str, password: str) -> None:
        result = self._json(
            "POST",
            "/api/auth/login/userpassword",
            {
                "username": username,
                "password": password,
                "request_admin": True,
            },
        )
        if not isinstance(result, dict) or not result.get("auth_token"):
            raise AccessServerError("login did not return an auth token")
        user_type = ""
        props = result.get("user_properties") or {}
        if isinstance(props, dict):
            user_type = str(props.get("user_type") or "")
        if user_type and user_type != "admin":
            raise AccessServerError("admin credentials are required to create users")
        self.token = str(result["auth_token"])

    def user_exists(self, username: str) -> bool:
        result = self._json("POST", "/api/users/list", {"users": [username]})
        if not isinstance(result, dict):
            return False
        profiles = result.get("profiles") or []
        return any(
            isinstance(item, dict) and item.get("name") == username for item in profiles
        )

    def create_user(self, username: str, autologin: bool) -> None:
        payload: dict[str, Any] = {"name": username}
        if autologin:
            payload["autologin"] = True
        try:
            self._json("POST", "/api/users/create", payload)
        except AccessServerError as exc:
            if "already" in str(exc).lower() or "exist" in str(exc).lower():
                return
            raise

    def set_password(self, username: str, password: str) -> None:
        self._json(
            "POST",
            "/api/auth/password/change",
            {"username": username, "new_password": password},
        )

    def set_autologin(self, username: str, enabled: bool) -> None:
        self._json(
            "POST",
            "/api/userprop/set",
            [{"name": username, "autologin": enabled}],
        )

    def create_profile(self, username: str, autologin: bool) -> str:
        status, body, _headers = self._request(
            "POST",
            "/api/profiles/create",
            {
                "username": username,
                "profile_type": "autologin" if autologin else "userlogin",
            },
            accept="*/*",
        )
        if status >= 400:
            raise AccessServerError(f"profile create failed ({status}): {body}")
        if not body.strip():
            raise AccessServerError("profile create returned an empty profile")
        return body


def remote_export(
    *,
    api_base: str,
    admin_user: str,
    admin_password: str,
    username: str,
    user_password: str | None,
    autologin: bool,
    host: str,
    tcp_port: str,
    udp_port: str,
    out: str,
) -> None:
    client = AccessServerClient(api_base)
    client.login(admin_user, admin_password)
    existed = client.user_exists(username)
    if not existed:
        if not user_password:
            raise AccessServerError(
                f"User {username} does not exist. Pass --password to create it."
            )
        client.create_user(username, autologin)
    if user_password:
        client.set_password(username, user_password)
    if autologin:
        client.set_autologin(username, True)
    profile = client.create_profile(username, autologin)
    write_profile(profile, host, tcp_port, udp_port, out)


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    rewrite = sub.add_parser("rewrite", help="Rewrite remotes in an .ovpn on stdin")
    rewrite.add_argument("host")
    rewrite.add_argument("tcp_port")
    rewrite.add_argument("udp_port")
    rewrite.add_argument("out")

    remote = sub.add_parser("remote-export", help="Create a user and export via Web API")
    remote.add_argument("--api-base", required=True)
    remote.add_argument("--admin-user", required=True)
    remote.add_argument("--admin-password", required=True)
    remote.add_argument("--user", required=True)
    remote.add_argument("--password", default="")
    remote.add_argument("--autologin", action="store_true")
    remote.add_argument("--host", required=True)
    remote.add_argument("--tcp-port", required=True)
    remote.add_argument("--udp-port", required=True)
    remote.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "rewrite":
            write_profile(sys.stdin.read(), args.host, args.tcp_port, args.udp_port, args.out)
            return 0
        remote_export(
            api_base=args.api_base,
            admin_user=args.admin_user,
            admin_password=args.admin_password,
            username=args.user,
            user_password=args.password or None,
            autologin=args.autologin,
            host=args.host,
            tcp_port=args.tcp_port,
            udp_port=args.udp_port,
            out=args.out,
        )
        return 0
    except (AccessServerError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
