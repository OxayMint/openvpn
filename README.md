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

2. Open `https://<dehost-ip>:943/admin` (self-signed cert until you replace it).
3. Under **Configuration → Network Settings**, set:
   - Hostname / public IP of the dehost machine
   - **TCP port number to 8443** (the host port you published, not 443)
   - UDP port 1194
4. Create a user, download a profile from `https://<dehost-ip>:8443/`, connect.

If you skip step 3, downloaded `.ovpn` files still say `remote ... 443` and TCP connections fail while UDP may still work.

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
