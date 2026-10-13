#!/bin/bash
# Print an autologin .ovpn for NAME (creates the client cert if needed).
set -euo pipefail

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  echo "usage: issue-profile NAME" >&2
  exit 1
fi

OPENVPN_DIR=/etc/openvpn
PKI="${OPENVPN_DIR}/pki"
EASYRSA=/usr/share/easy-rsa/easyrsa
HOST="${PUBLIC_HOST:-}"
TCP_PORT="${HOST_HTTPS_PORT:-8443}"
UDP_PORT="${HOST_UDP_PORT:-1194}"

if [[ -z "$HOST" ]]; then
  echo "PUBLIC_HOST is not set." >&2
  exit 1
fi
if [[ ! -f "${PKI}/ca.crt" || ! -f "${OPENVPN_DIR}/tls-crypt.key" ]]; then
  echo "OpenVPN PKI is not ready." >&2
  exit 1
fi

export EASYRSA_PKI="$PKI"
export EASYRSA_BATCH=1
export EASYRSA_ALGO="${EASYRSA_ALGO:-ec}"
export EASYRSA_CURVE="${EASYRSA_CURVE:-prime256v1}"
export EASYRSA_CERT_EXPIRE="${EASYRSA_CERT_EXPIRE:-3650}"

if [[ ! -f "${PKI}/issued/${NAME}.crt" ]]; then
  "$EASYRSA" build-client-full "$NAME" nopass >/dev/null
fi

pem() {
  local tag="$1" file="$2"
  printf '<%s>\n' "$tag"
  if [[ "$tag" == "ca" || "$tag" == "cert" ]]; then
    openssl x509 -in "$file"
  else
    cat "$file"
  fi
  printf '</%s>\n' "$tag"
}

cat <<EOF
client
dev tun
nobind
persist-key
persist-tun
remote-cert-tls server
auth SHA256
auth-nocache
data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
resolv-retry infinite
remote ${HOST} ${UDP_PORT} udp
remote ${HOST} ${TCP_PORT} tcp
verb 3
EOF
pem ca "${PKI}/ca.crt"
pem cert "${PKI}/issued/${NAME}.crt"
pem key "${PKI}/private/${NAME}.key"
pem tls-crypt "${OPENVPN_DIR}/tls-crypt.key"
