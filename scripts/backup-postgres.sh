#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PLAIN="${BACKUP_DIR}/kurilka-${STAMP}.dump"
ENCRYPTED="${PLAIN}.enc"

mkdir -p "$BACKUP_DIR"
umask 077
pg_dump --format=custom --no-owner --no-privileges "$DATABASE_URL" --file "$PLAIN"
openssl enc -aes-256-cbc -salt -pbkdf2 -in "$PLAIN" -out "$ENCRYPTED" -pass env:BACKUP_ENCRYPTION_KEY
sha256sum "$ENCRYPTED" > "${ENCRYPTED}.sha256"
rm -f "$PLAIN"
printf '%s\n' "$ENCRYPTED"
