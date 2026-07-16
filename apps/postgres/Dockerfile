FROM postgres:16.14-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777

# The official entrypoint only needs gosu while starting as root. Production
# runs directly as postgres, so remove the stale Go binary and its CVE surface.
RUN rm -f /usr/local/bin/gosu \
    && test "$(id -u postgres)" = "70"

USER postgres
