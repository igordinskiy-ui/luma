FROM postgres:16.14-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777

RUN apk add --no-cache openssl=3.5.7-r0 \
    && rm -f /usr/local/bin/gosu \
    && test "$(id -u postgres)" = "70"

COPY --chmod=0755 scripts/backup-postgres.sh /usr/local/bin/backup-postgres
COPY --chmod=0755 scripts/restore-drill.sh /usr/local/bin/restore-drill

USER postgres
CMD ["backup-postgres"]
