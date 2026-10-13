# krakkenVPN (community OpenVPN)

Docker Compose deploy for **community OpenVPN** on a host where **TCP 443 is already taken**.

This used to run [OpenVPN Access Server](https://openvpn.net/access-server/). That product’s free license allows **two concurrent tunnels** (`max concurrent connections exceeded`). Access Server will not lift that cap without a paid subscription, and this repo does not bypass that license.

Community OpenVPN has no connection license. The daemons allow **4096 clients per protocol** by default (`MAX_CLIENTS`). Each protocol uses a `/16` pool (`10.8.0.0/16` UDP, `10.9.0.0/16` TCP).

Keep OpenVPN listening on **443/tcp and 1194/udp inside the container** and publish a **free host TCP port** (this repo uses **8443**).

## Ports

| Role | Inside container | Host (this repo) |
| --- | --- | --- |
| OpenVPN TCP fallback | 443 | **8443** |
| OpenVPN UDP | 1194/udp | 1194/udp |

UDP 1194 is the data path you want for day-to-day VPN. TCP 8443 is fallback when UDP is blocked. There is no Access Server admin UI on 943.

## Deploy on the host

Requires Docker Engine with the Compose plugin, `/dev/net/tun`, and permission to add `NET_ADMIN` / `MKNOD`.

```bash
cp .env.example .env
# edit OVPN_DATA and ports if needed
chmod +x scripts/check-ports.sh scripts/deploy.sh
sudo ./scripts/check-ports.sh 443 1194 8443
sudo ./scripts/deploy.sh
```

If you previously ran Access Server, **do not reuse** `/root/openvpn-data`. Point `OVPN_DATA` at a new directory (default `/root/openvpn-pki`) and issue **new** `.ovpn` profiles — the CA is different.

If 8443 is also busy, pick another free TCP port and change **both** `-p HOST:443` and `HOST_HTTPS_PORT` in `.env`.

See what owns 443:

```bash
ss -tlnp | grep ':443'
docker ps --format '{{.Names}} {{.Ports}}'
```

## Importable `.ovpn` profile

Easiest import (autologin — client cert, no password):

```bash
chmod +x scripts/export-profile.sh
sudo ./scripts/export-profile.sh \
  --user vpnuser \
  --out ./profiles/vpnuser.ovpn
```

Copy `profiles/vpnuser.ovpn` to your laptop/phone and import it:

- **Windows / macOS:** OpenVPN Connect → **Add** → **File** → select the `.ovpn`
- **Android / iOS:** OpenVPN Connect → **Add** → **File** / share the `.ovpn` into the app
- **CLI:** `sudo openvpn --config vpnuser.ovpn`

The export writes remotes for this host mapping:

```text
remote 13.143.223.160 1194 udp
remote 13.143.223.160 8443 tcp
```

## krakkenVPN bot

krakkenVPN is the Telegram bot that creates client certs and sends the `.ovpn` file in chat.

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` and copy the token.
2. Set these in `.env`:

   ```bash
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_ADMIN_USERNAME=your_telegram_username
   ```

   `TELEGRAM_ADMIN_USERNAME` is the Telegram handle (with or without `@`). That account must have a public username set.

3. Recreate the stack so krakkenVPN starts:

   ```bash
   docker compose up -d --build
   ```

4. Open a private chat with krakkenVPN and send `/create`:
   - **Admin** (`TELEGRAM_ADMIN_USERNAME`) is asked for the new OpenVPN username, then receives that `.ovpn`.
   - **Anyone else** gets a profile named after their Telegram username, and the `.ovpn` is sent to them.

`/cancel` aborts the admin prompt. krakkenVPN talks to the OpenVPN container through the host Docker socket (`docker exec` / `issue-profile`), so it must run on the same Docker host. Users must have a public Telegram username set.

If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_ADMIN_USERNAME` is empty, the krakkenVPN container stays up but idle and logs that it is waiting for those variables.

## Who is connected

```bash
docker exec openvpn cat /var/log/openvpn/status-tun0.log
docker exec openvpn cat /var/log/openvpn/status-tun1.log
```

## Stop / remove

```bash
docker compose down
# PKI stays in OVPN_DATA (default /root/openvpn-pki)
```

## Notes

- Mapping `-p 8443:443` only changes the **host** bind. The process inside the image still binds 443.
- Do not add `-p 443:443` while another process already holds 443.
- Open the host firewall for `8443/tcp` and `1194/udp`.
- Raise or lower the daemon ceiling with `MAX_CLIENTS` in `.env` (restart the `openvpn` service).
