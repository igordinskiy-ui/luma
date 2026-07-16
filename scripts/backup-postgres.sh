#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
if [ "${#BACKUP_ENCRYPTION_KEY}" -lt 32 ]; then
  printf '%s\n' "BACKUP_ENCRYPTION_KEY must be at least 32 characters." >&2
  exit 2
fi
BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

umask 077
mkdir -p "$BACKUP_DIR"
test -d "$BACKUP_DIR" && test -w "$BACKUP_DIR"
PLAIN="$(mktemp "${BACKUP_DIR}/.kurilka-${STAMP}-XXXXXX")"
TOKEN="$(basename "$PLAIN")"
TOKEN="${TOKEN##*-}"
BASENAME="kurilka-${STAMP}-${TOKEN}.dump.enc"
ENCRYPTED="${BACKUP_DIR}/${BASENAME}"
ENCRYPTED_TMP="${BACKUP_DIR}/.${BASENAME}.tmp"
CHECKSUM="${ENCRYPTED}.sha256"
CHECKSUM_TMP="${CHECKSUM}.tmp"
PUBLISHED=0

cleanup() {
  rm -f "$PLAIN" "$ENCRYPTED_TMP" "$CHECKSUM_TMP"
  if [ "$PUBLISHED" -ne 1 ]; then
    rm -f "$ENCRYPTED" "$CHECKSUM"
  fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

pg_dump --format=custom --no-owner --no-privileges "$DATABASE_URL" --file "$PLAIN"
openssl enc -aes-256-cbc -salt -pbkdf2 -in "$PLAIN" -out "$ENCRYPTED_TMP" -pass env:BACKUP_ENCRYPTION_KEY
DIGEST="$(sha256sum "$ENCRYPTED_TMP" | awk '{print $1}')"
printf '%s  %s\n' "$DIGEST" "$BASENAME" > "$CHECKSUM_TMP"
mv "$ENCRYPTED_TMP" "$ENCRYPTED"
mv "$CHECKSUM_TMP" "$CHECKSUM"
PUBLISHED=1
printf 'BACKUP_EVIDENCE file=%s checksum=%s\n' "$BASENAME" "$DIGEST"
