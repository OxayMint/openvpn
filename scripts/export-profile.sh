#!/usr/bin/env bash
# Export a community OpenVPN .ovpn that OpenVPN Connect can import.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

CONTAINER_NAME="${CONTAINER_NAME:-openvpn}"
PUBLIC_HOST="${PUBLIC_HOST:-13.143.223.160}"
HOST_HTTPS_PORT="${HOST_HTTPS_PORT:-8443}"
HOST_UDP_PORT="${HOST_UDP_PORT:-1194}"

USER_NAME=""
OUT=""

usage() {
  cat <<EOF
Usage: $0 --user NAME [--out FILE]

Writes a .ovpn profile for ${PUBLIC_HOST} that you can import into
OpenVPN Connect (or any OpenVPN 2.x client).

  --user NAME       Client certificate CN / username (required)
  --out FILE        Output path (default: ./profiles/NAME.ovpn)

The container still listens on 443 internally. Profiles use the published
host TCP port ${HOST_HTTPS_PORT} so import works with the 8443:443 mapping.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) USER_NAME="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --password|--autologin)
      # Kept so older docs/invocations still work; community profiles are always autologin.
      shift
      [[ "${1:-}" == -* || -z "${1:-}" ]] || shift
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ -z "$USER_NAME" ]]; then
  usage >&2
  exit 1
fi

if [[ -z "$OUT" ]]; then
  mkdir -p "$ROOT/profiles"
  OUT="$ROOT/profiles/${USER_NAME}.ovpn"
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "Container ${CONTAINER_NAME} is not running." >&2
  exit 1
fi

PROFILE="$(docker exec -e PUBLIC_HOST="$PUBLIC_HOST" \
  -e HOST_HTTPS_PORT="$HOST_HTTPS_PORT" \
  -e HOST_UDP_PORT="$HOST_UDP_PORT" \
  "$CONTAINER_NAME" /usr/local/bin/issue-profile "$USER_NAME")"

REWRITE_PY="$(mktemp)"
trap 'rm -f "$REWRITE_PY"' EXIT
cat >"$REWRITE_PY" <<'PY'
import re
import sys

host, tcp_port, udp_port, out = sys.argv[1:]
text = sys.stdin.read()
if not text.strip():
    sys.exit("issue-profile returned an empty profile")

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

with open(out, "w", encoding="utf-8") as fh:
    fh.write(text)
PY

printf '%s' "$PROFILE" | python3 "$REWRITE_PY" "$PUBLIC_HOST" "$HOST_HTTPS_PORT" "$HOST_UDP_PORT" "$OUT"

echo "Wrote ${OUT}"
echo "Import this file in OpenVPN Connect (File → Import profile / Add profile)."
echo "Server: ${PUBLIC_HOST}  UDP ${HOST_UDP_PORT}  TCP ${HOST_HTTPS_PORT}"
echo "This profile is autologin (client certificate); no Access Server password."
