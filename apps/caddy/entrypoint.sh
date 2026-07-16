#!/bin/sh
set -eu

if [ "$(id -u)" = "0" ]; then
  chown -R 1000:1000 /data /config
  exec su-exec 1000:1000 setpriv --nnp "$@"
fi

exec setpriv --nnp "$@"
