#!/usr/bin/env bash
# Create Access Server users declared in users.json and export .ovpn profiles.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

USERS_FILE="${1:-$ROOT/users.json}"
if [[ ! -f "$USERS_FILE" ]]; then
  echo "Missing users file: ${USERS_FILE}" >&2
  exit 1
fi

python3 - "$USERS_FILE" <<'PY' | while IFS=$'\t' read -r username autologin password_env; do
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

for user in data.get("users", []):
    username = user["username"]
    autologin = "1" if user.get("autologin") else "0"
    env_name = user.get("password_env") or f"USER_{username.upper()}_PASSWORD"
    print(f"{username}\t{autologin}\t{env_name}")
PY
  args=(
    "$ROOT/scripts/export-profile.sh"
    --user "$username"
    --out "$ROOT/profiles/${username}.ovpn"
  )
  if [[ "$autologin" == "1" ]]; then
    args+=(--autologin)
  fi
  password="${!password_env:-}"
  if [[ -n "$password" ]]; then
    args+=(--password "$password")
  fi
  "${args[@]}"
done
