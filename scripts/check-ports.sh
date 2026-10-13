#!/usr/bin/env bash
set -euo pipefail

ports=("$@")
if [[ ${#ports[@]} -eq 0 ]]; then
  ports=(443 1194 8443)
fi

echo "Listening sockets that match requested ports:"
if command -v ss >/dev/null 2>&1; then
  ss -tulnp | grep -E "($(IFS='|'; echo "${ports[*]}"))" || echo "(none)"
else
  netstat -tulnp | grep -E "($(IFS='|'; echo "${ports[*]}"))" || echo "(none)"
fi

echo
if command -v docker >/dev/null 2>&1; then
  echo "Docker containers publishing those ports:"
  docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep -E "($(IFS='|'; echo "${ports[*]}"))|NAMES" || echo "(none)"
fi
