#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

# shellcheck disable=SC1091
source .env

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need_cmd docker

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is required" >&2
  exit 1
fi

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tuln | grep -qE "[:.]${port}[[:space:]]"
  else
    netstat -tuln | grep -qE "[:.]${port}[[:space:]]"
  fi
}

mkdir -p "${OVPN_DATA}"

if [[ -e "${OVPN_DATA}/as.conf" || -d "${OVPN_DATA}/etc" ]]; then
  echo "${OVPN_DATA} looks like OpenVPN Access Server data. Set OVPN_DATA to a new directory (for example /root/openvpn-pki)." >&2
  exit 1
fi

if port_in_use "${HOST_UDP_PORT}"; then
  echo "Host port ${HOST_UDP_PORT}/udp is already allocated. Set HOST_UDP_PORT in .env to a free port." >&2
  exit 1
fi

if port_in_use "${HOST_HTTPS_PORT}"; then
  echo "Host port ${HOST_HTTPS_PORT} is already allocated. Set HOST_HTTPS_PORT in .env to a free TCP port." >&2
  exit 1
fi

if port_in_use 443 && [[ "${HOST_HTTPS_PORT}" == "443" ]]; then
  echo "Port 443 is already allocated. Change HOST_HTTPS_PORT in .env (for example 8443)." >&2
  exit 1
fi

docker compose down --remove-orphans >/dev/null 2>&1 || true
docker compose up -d --build

echo
echo "Community OpenVPN is up (no 2-connection Access Server license)."
echo "  UDP VPN:      <host>:${HOST_UDP_PORT}/udp"
echo "  TCP fallback: <host>:${HOST_HTTPS_PORT}/tcp"
echo "  max-clients:  ${MAX_CLIENTS:-4096} per protocol"
echo
echo "Existing Access Server .ovpn files will not work with this CA — issue new profiles."
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_ADMIN_USERNAME:-}" ]]; then
  echo "krakkenVPN bot: DM it as @${TELEGRAM_ADMIN_USERNAME#@} and send /create"
else
  echo "krakkenVPN bot is idle until TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_USERNAME are set in .env"
fi
