FROM caddy:2.11.4-builder-alpine@sha256:8e89605351333ad2cc2f3bcc95275a2ccc427f88914050e86a5fde0fd77a63c4 AS build

# Rebuild the stock binary with the builder's patched Go 1.26.5 toolchain.
RUN xcaddy build v2.11.4 --output /usr/bin/caddy

FROM caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648

# curl is not used at runtime and currently carries fixed High CVEs in the
# upstream image. Removing it also removes libcurl; the rebuilt Caddy binary
# replaces the vulnerable Go 1.26.3 binary from the runtime layer.
RUN apk add --no-cache su-exec=0.3-r0 \
    && apk del --no-network curl \
    && rm -f /usr/bin/caddy \
    && addgroup -S -g 1000 caddy \
    && adduser -S -D -H -u 1000 -G caddy caddy \
    && chown -R caddy:caddy /data /config
COPY --from=build --chmod=0755 /usr/bin/caddy /usr/bin/caddy
RUN setcap -r /usr/bin/caddy
COPY --chmod=0755 entrypoint.sh /usr/local/bin/luma-caddy-entrypoint

USER caddy
ENTRYPOINT ["/usr/local/bin/luma-caddy-entrypoint"]
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
