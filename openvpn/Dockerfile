FROM alpine:3.20

RUN apk add --no-cache \
        bash \
        easy-rsa \
        iptables \
        iptables-legacy \
        iproute2 \
        openvpn \
        openssl

COPY entrypoint.sh /entrypoint.sh
COPY issue-profile.sh /usr/local/bin/issue-profile
RUN chmod +x /entrypoint.sh /usr/local/bin/issue-profile

VOLUME ["/etc/openvpn"]
EXPOSE 1194/udp 443/tcp
ENTRYPOINT ["/entrypoint.sh"]
