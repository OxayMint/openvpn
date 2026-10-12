# OpenVPN Access Server (dehost)

Docker Compose deploy for [OpenVPN Access Server](https://openvpn.net/access-server/) on a host where **TCP 443 is already taken**.

The official `docker run` maps `443:443`. Docker then fails with:

```text
Bind for 0.0.0.0:443 failed: port is already allocated
```

Do not steal 443 from whatever is already serving it. Keep OpenVPN listening on **443 inside the container** and publish a **free host port** (this repo uses **8443**).

## Ports

| Role | Inside container | Host (this repo) |
| --- | --- | --- |
| Admin UI (HTTPS) | 943 | 943 |
| Client portal + OpenVPN TCP | 443 | **8443** |
| OpenVPN UDP | 1194/udp | 1194/udp |

UDP 1194 is the data path you want for day-to-day VPN. TCP 8443 is for the client web UI and for TCP fallback when UDP is blocked.

## Deploy on the host

Requires Docker Engine with the Compose plugin, `/dev/net/tun`, and permission to add `NET_ADMIN` / `MKNOD`.

```bash
cp .env.example .env
# edit OVPN_DATA and ports if needed
chmod +x scripts/check-ports.sh scripts/deploy.sh
sudo ./scripts/check-ports.sh 443 943 1194 8443
sudo ./scripts/deploy.sh
```

Equivalent one-shot `docker run` (same mapping as Compose):

```bash
mkdir -p /root/openvpn-data
docker run -d \
  --name=openvpn-as --device /dev/net/tun \
  --cap-add=MKNOD --cap-add=NET_ADMIN \
  -p 943:943 -p 8443:443 -p 1194:1194/udp \
  -v /root/openvpn-data:/openvpn \
  --restart=unless-stopped \
  openvpn/openvpn-as
```

If 8443 is also busy, pick another free TCP port and change **both** `-p HOST:443` and `HOST_HTTPS_PORT` in `.env`.

See what owns 443:

```bash
ss -tlnp | grep ':443'
docker ps --format '{{.Names}} {{.Ports}}'
```

## After start

1. Read the generated admin password:

   ```bash
   docker logs openvpn-as 2>&1 | grep -i password
   ```

2. Open `https://13.143.223.160:943/admin` (self-signed cert until you replace it).
3. Under **Configuration → Network Settings**, set:
   - Hostname / public IP: `13.143.223.160`
   - **TCP port number to 8443** (the host port you published, not 443)
   - UDP port 1194
4. Create a user, then export an `.ovpn` (see below).

If you skip step 3, downloaded `.ovpn` files still say `remote ... 443` and TCP connections fail while UDP may still work.

## Importable `.ovpn` profile

Do not hand-write a config. Access Server embeds CA, client cert, and tls-crypt in the profile. Generate it from the running container, then import that file in [OpenVPN Connect](https://openvpn.net/client/).

Easiest import (autologin — connects without typing a password):

```bash
chmod +x scripts/export-profile.sh
sudo ./scripts/export-profile.sh \
  --user vpnuser \
  --password 'choose-a-strong-password' \
  --autologin \
  --out ./profiles/vpnuser.ovpn
```

Copy `profiles/vpnuser.ovpn` to your laptop/phone and import it:

- **Windows / macOS:** OpenVPN Connect → **Add** → **File** → select the `.ovpn`
- **Android / iOS:** OpenVPN Connect → **Add** → **File** / share the `.ovpn` into the app
- **CLI:** `sudo openvpn --config vpnuser.ovpn`

The export rewrites remotes to this host mapping:

```text
remote 13.143.223.160 1194 udp
remote 13.143.223.160 8443 tcp
```

Without `--autologin`, `GetUserlogin` is used and the client prompts for `vpnuser` / password.

Same thing by hand:

```bash
docker exec openvpn-as \
  /usr/local/openvpn_as/scripts/sacli --key "host.name" --value "13.143.223.160" ConfigPut
docker exec openvpn-as /usr/local/openvpn_as/scripts/sacli start

docker exec openvpn-as \
  /usr/local/openvpn_as/scripts/sacli --user vpnuser --key "type" --value "user_connect" UserPropPut
docker exec openvpn-as \
  /usr/local/openvpn_as/scripts/sacli --user vpnuser --new_pass 'choose-a-strong-password' SetPassword

docker exec openvpn-as \
  /usr/local/openvpn_as/scripts/sacli --user vpnuser GetUserlogin \
  > vpnuser.ovpn
# then change any "remote ... 443" line to "remote 13.143.223.160 8443"
```

You can also log into `https://13.143.223.160:8443/` as `vpnuser` and use **Yourself (user-locked profile)** — after download, still change TCP `443` to `8443` unless Network Settings already advertise 8443.

## krakkenVPN bot

krakkenVPN is the Telegram bot that creates Access Server client profiles and sends the `.ovpn` file in chat. It introduces itself as krakkenVPN and speaks in first person as a mighty kraken of the deep.

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

`/cancel` aborts the admin prompt. krakkenVPN talks to Access Server through the host Docker socket (`docker exec` / `sacli`), so it must run on the same Docker host as `openvpn-as`. Users must have a public Telegram username set.

If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_ADMIN_USERNAME` is empty, the krakkenVPN container stays up but idle and logs that it is waiting for those variables.

## Stop / remove

```bash
docker compose down
# data stays in OVPN_DATA (default /root/openvpn-data)
```

## Notes

- Mapping `-p 8443:443` only changes the **host** bind. The process inside the image still binds 443.
- Do not add `-p 443:443` while another process already holds 443.
- Open the host firewall for `943/tcp`, `8443/tcp`, and `1194/udp`.
- Access Server’s free license is limited to two concurrent connections unless you attach a subscription.
