#!/usr/bin/env bash
# Export an OpenVPN Access Server .ovpn that OpenVPN Connect can import.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

CONTAINER_NAME="${CONTAINER_NAME:-openvpn-as}"
PUBLIC_HOST="${PUBLIC_HOST:-13.143.223.160}"
HOST_HTTPS_PORT="${HOST_HTTPS_PORT:-8443}"
HOST_UDP_PORT="${HOST_UDP_PORT:-1194}"
AS_API_BASE="${AS_API_BASE:-https://${PUBLIC_HOST}:943}"
AS_ADMIN_USER="${AS_ADMIN_USER:-openvpn}"
AS_ADMIN_PASSWORD="${AS_ADMIN_PASSWORD:-}"

USER_NAME=""
USER_PASS=""
AUTOLOGIN=0
OUT=""
CREATE_USER=0
FORCE_REMOTE=0

usage() {
  cat <<EOF
Usage: $0 --user NAME [--password PASS] [--autologin] [--out FILE] [--remote]

Writes a .ovpn profile for ${PUBLIC_HOST} that you can import into
OpenVPN Connect (or any OpenVPN 2.x client).

  --user NAME       Access Server username (required)
  --password PASS   Set/update that user's password (needed on first create)
  --autologin       Embed a client cert so the app connects without a password
  --out FILE        Output path (default: ./profiles/NAME.ovpn)
  --remote          Use the Access Server Web API instead of docker exec
  --admin-user NAME Admin username for Web API (default: openvpn)
  --admin-password  Admin password for Web API (or AS_ADMIN_PASSWORD)

Prefers a running ${CONTAINER_NAME} container. If Docker is unavailable,
falls back to the Web API at ${AS_API_BASE} using AS_ADMIN_USER /
AS_ADMIN_PASSWORD (or --admin-user / --admin-password).

The container still listens on 443 internally. This script rewrites the
TCP remote to host port ${HOST_HTTPS_PORT} so import works with the
8443:443 Docker mapping.
EOF
}

ADMIN_USER_FLAG=""
ADMIN_PASS_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) USER_NAME="$2"; shift 2 ;;
    --password) USER_PASS="$2"; shift 2 ;;
    --autologin) AUTOLOGIN=1; shift ;;
    --out) OUT="$2"; shift 2 ;;
    --remote) FORCE_REMOTE=1; shift ;;
    --admin-user) ADMIN_USER_FLAG="$2"; shift 2 ;;
    --admin-password) ADMIN_PASS_FLAG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ -n "$ADMIN_USER_FLAG" ]]; then
  AS_ADMIN_USER="$ADMIN_USER_FLAG"
fi
if [[ -n "$ADMIN_PASS_FLAG" ]]; then
  AS_ADMIN_PASSWORD="$ADMIN_PASS_FLAG"
fi

if [[ -z "$USER_NAME" ]]; then
  usage >&2
  exit 1
fi

if [[ -z "$OUT" ]]; then
  mkdir -p "$ROOT/profiles"
  OUT="$ROOT/profiles/${USER_NAME}.ovpn"
fi

REWRITE=(python3 "$ROOT/scripts/ovpn_profile.py" rewrite "$PUBLIC_HOST" "$HOST_HTTPS_PORT" "$HOST_UDP_PORT" "$OUT")

container_running() {
  command -v docker >/dev/null 2>&1 || return 1
  docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"
}

export_via_docker() {
  sacli() {
    docker exec "$CONTAINER_NAME" /usr/local/openvpn_as/scripts/sacli "$@"
  }

  sacli --key "host.name" --value "$PUBLIC_HOST" ConfigPut >/dev/null

  if ! sacli --user "$USER_NAME" UserPropGet >/dev/null 2>&1; then
    CREATE_USER=1
  fi

  if [[ "$CREATE_USER" -eq 1 && -z "$USER_PASS" ]]; then
    echo "User ${USER_NAME} does not exist. Pass --password to create it." >&2
    exit 1
  fi

  if [[ "$CREATE_USER" -eq 1 ]]; then
    sacli --user "$USER_NAME" --key "type" --value "user_connect" UserPropPut >/dev/null
  fi

  if [[ -n "$USER_PASS" ]]; then
    sacli --user "$USER_NAME" --new_pass "$USER_PASS" SetPassword >/dev/null
  fi

  if [[ "$AUTOLOGIN" -eq 1 ]]; then
    sacli --user "$USER_NAME" --key "prop_autologin" --value "true" UserPropPut >/dev/null
  fi

  # Apply hostname before generating the profile.
  sacli start >/dev/null

  if [[ "$AUTOLOGIN" -eq 1 ]]; then
    PROFILE="$(sacli --user "$USER_NAME" GetAutologin)"
  else
    PROFILE="$(sacli --user "$USER_NAME" GetUserlogin)"
  fi

  printf '%s' "$PROFILE" | "${REWRITE[@]}"
}

export_via_api() {
  if [[ -z "$AS_ADMIN_PASSWORD" ]]; then
    echo "Container ${CONTAINER_NAME} is not running, and AS_ADMIN_PASSWORD is not set." >&2
    echo "Either run this on the VPN host, or set AS_ADMIN_PASSWORD (admin UI user ${AS_ADMIN_USER})." >&2
    exit 1
  fi

  remote_args=(
    python3 "$ROOT/scripts/ovpn_profile.py" remote-export
    --api-base "$AS_API_BASE"
    --admin-user "$AS_ADMIN_USER"
    --admin-password "$AS_ADMIN_PASSWORD"
    --user "$USER_NAME"
    --host "$PUBLIC_HOST"
    --tcp-port "$HOST_HTTPS_PORT"
    --udp-port "$HOST_UDP_PORT"
    --out "$OUT"
  )
  if [[ -n "$USER_PASS" ]]; then
    remote_args+=(--password "$USER_PASS")
  fi
  if [[ "$AUTOLOGIN" -eq 1 ]]; then
    remote_args+=(--autologin)
  fi
  "${remote_args[@]}"
}

if [[ "$FORCE_REMOTE" -eq 1 ]]; then
  export_via_api
elif container_running; then
  export_via_docker
else
  export_via_api
fi

echo "Wrote ${OUT}"
echo "Import this file in OpenVPN Connect (File → Import profile / Add profile)."
echo "Server: ${PUBLIC_HOST}  UDP ${HOST_UDP_PORT}  TCP ${HOST_HTTPS_PORT}"
if [[ "$AUTOLOGIN" -ne 1 ]]; then
  echo "This profile is user-locked: the client will ask for ${USER_NAME}'s password."
fi
