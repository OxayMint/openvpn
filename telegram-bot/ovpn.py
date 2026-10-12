"""Create an OpenVPN Access Server user and export an autologin .ovpn profile."""

from __future__ import annotations

import os
import re
import secrets
import time
from typing import Any

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SACLI = "/usr/local/openvpn_as/scripts/sacli"


class ProfileError(Exception):
    """Raised when an OpenVPN profile cannot be created or exported."""


def validate_username(username: str) -> str:
    """Return a stripped username or raise ValueError if it is not usable."""
    name = username.strip()
    if not name:
        raise ValueError("Username cannot be empty.")
    if not USERNAME_RE.fullmatch(name):
        raise ValueError(
            "Use 1–64 characters: letters, digits, dot, underscore, or hyphen, "
            "starting with a letter or digit."
        )
    return name


def rewrite_profile(text: str, host: str, tcp_port: str, udp_port: str) -> str:
    """Rewrite remotes to the published host ports (same rules as export-profile.sh)."""
    if not text.strip():
        raise ProfileError("Access Server returned an empty profile.")

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


def _decode(data: bytes | None) -> str:
    return (data or b"").decode("utf-8", errors="replace").strip()


def _sacli(container: Any, *args: str) -> str:
    result = container.exec_run([SACLI, *args], demux=True)
    stdout, stderr = result.output if result.output is not None else (b"", b"")
    if result.exit_code != 0:
        detail = _decode(stderr) or _decode(stdout) or f"exit {result.exit_code}"
        raise ProfileError(f"sacli {' '.join(args)} failed: {detail}")
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace")
    return ""


def _user_exists(container: Any, username: str) -> bool:
    result = container.exec_run([SACLI, "--user", username, "UserPropGet"], demux=True)
    return result.exit_code == 0


def create_ovpn_profile(username: str, *, docker_client: Any | None = None) -> str:
    """Create the Access Server user if needed and return an autologin .ovpn body."""
    username = validate_username(username)
    host = os.environ.get("PUBLIC_HOST", "").strip()
    tcp_port = os.environ.get("HOST_HTTPS_PORT", "8443").strip() or "8443"
    udp_port = os.environ.get("HOST_UDP_PORT", "1194").strip() or "1194"
    container_name = os.environ.get("CONTAINER_NAME", "openvpn-as").strip() or "openvpn-as"

    if not host:
        raise ProfileError("PUBLIC_HOST is not set.")

    if docker_client is None:
        import docker
        from docker.errors import DockerException, NotFound

        try:
            docker_client = docker.from_env()
        except DockerException as exc:
            raise ProfileError(f"Cannot talk to Docker: {exc}") from exc
    else:
        NotFound = Exception  # type: ignore[misc, assignment]

    try:
        container = docker_client.containers.get(container_name)
    except NotFound as exc:
        raise ProfileError(f"Container {container_name} is not running.") from exc

    status = getattr(container, "status", None)
    if status and status != "running":
        raise ProfileError(f"Container {container_name} is {status}.")

    last_error: ProfileError | None = None
    for _attempt in range(15):
        try:
            _sacli(container, "--key", "host.name", "--value", host, "ConfigPut")
            break
        except ProfileError as exc:
            last_error = exc
            time.sleep(2)
    else:
        raise ProfileError(f"Access Server is not ready: {last_error}") from last_error

    if not _user_exists(container, username):
        _sacli(container, "--user", username, "--key", "type", "--value", "user_connect", "UserPropPut")
        _sacli(container, "--user", username, "--new_pass", secrets.token_urlsafe(24), "SetPassword")

    _sacli(container, "--user", username, "--key", "prop_autologin", "--value", "true", "UserPropPut")
    _sacli(container, "start")
    profile = _sacli(container, "--user", username, "GetAutologin")
    return rewrite_profile(profile, host, tcp_port, udp_port)
