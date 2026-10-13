#!/bin/bash
# Initialize PKI (once) and run UDP + TCP OpenVPN daemons with no license cap.
set -euo pipefail

OPENVPN_DIR=/etc/openvpn
PKI="${OPENVPN_DIR}/pki"
EASYRSA=/usr/share/easy-rsa/easyrsa
MAX_CLIENTS="${MAX_CLIENTS:-4096}"

export EASYRSA_PKI="$PKI"
export EASYRSA_BATCH=1
export EASYRSA_ALGO="${EASYRSA_ALGO:-ec}"
export EASYRSA_CURVE="${EASYRSA_CURVE:-prime256v1}"
export EASYRSA_CA_EXPIRE="${EASYRSA_CA_EXPIRE:-3650}"
export EASYRSA_CERT_EXPIRE="${EASYRSA_CERT_EXPIRE:-3650}"

mkdir -p "$OPENVPN_DIR" /var/log/openvpn

if [[ -e "${OPENVPN_DIR}/as.conf" || -d "${OPENVPN_DIR}/etc" ]]; then
  echo "This volume looks like OpenVPN Access Server data." >&2
  echo "Community OpenVPN needs an empty PKI directory (default OVPN_DATA=/root/openvpn-pki)." >&2
  exit 1
fi

if [[ ! -f "${PKI}/ca.crt" ]]; then
  echo "Initializing krakkenVPN PKI…"
  "$EASYRSA" init-pki
  EASYRSA_REQ_CN="${EASYRSA_REQ_CN:-krakkenVPN-CA}" "$EASYRSA" build-ca nopass
  "$EASYRSA" build-server-full server nopass
fi

if [[ ! -f "${OPENVPN_DIR}/tls-crypt.key" ]]; then
  openvpn --genkey secret "${OPENVPN_DIR}/tls-crypt.key"
fi

write_server_conf() {
  local conf="$1" proto="$2" port="$3" network="$4" netmask="$5" dev="$6"
  {
    cat <<EOF
port ${port}
proto ${proto}
dev ${dev}
topology subnet
server ${network} ${netmask}
keepalive 10 120
persist-key
persist-tun
dh none
ecdh-curve ${EASYRSA_CURVE}
tls-groups X25519:${EASYRSA_CURVE}
data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
auth SHA256
remote-cert-tls client
ca ${PKI}/ca.crt
cert ${PKI}/issued/server.crt
key ${PKI}/private/server.key
tls-crypt ${OPENVPN_DIR}/tls-crypt.key
max-clients ${MAX_CLIENTS}
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
push "dhcp-option DNS 8.8.8.8"
push "block-outside-dns"
status /var/log/openvpn/status-${dev}.log 10
verb 3
mute 20
EOF
    if [[ "$proto" == udp* ]]; then
      echo "explicit-exit-notify 1"
    fi
  } >"$conf"
}

write_server_conf "${OPENVPN_DIR}/server-udp.conf" udp 1194 10.8.0.0 255.255.0.0 tun0
write_server_conf "${OPENVPN_DIR}/server-tcp.conf" tcp 443 10.9.0.0 255.255.0.0 tun1

sysctl -w net.ipv4.ip_forward=1 >/dev/null || true

nat_masquerade() {
  local iface="$1"
  for ipt in iptables iptables-legacy; do
    command -v "$ipt" >/dev/null 2>&1 || continue
    "$ipt" -t nat -C POSTROUTING -s 10.8.0.0/15 -o "$iface" -j MASQUERADE 2>/dev/null && return 0
    "$ipt" -t nat -A POSTROUTING -s 10.8.0.0/15 -o "$iface" -j MASQUERADE && return 0
  done
  return 0
}

IFACE="$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}')"
if [[ -n "${IFACE:-}" ]]; then
  nat_masquerade "$IFACE"
fi

echo "Starting OpenVPN (max-clients=${MAX_CLIENTS}, no Access Server license cap)"
openvpn --config "${OPENVPN_DIR}/server-udp.conf" &
udp_pid=$!
openvpn --config "${OPENVPN_DIR}/server-tcp.conf" &
tcp_pid=$!

term() {
  kill "$udp_pid" "$tcp_pid" 2>/dev/null || true
  wait "$udp_pid" "$tcp_pid" 2>/dev/null || true
}
trap term INT TERM

wait -n "$udp_pid" "$tcp_pid"
echo "An OpenVPN daemon exited; shutting down." >&2
term
exit 1
