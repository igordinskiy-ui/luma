#!/bin/sh
set -eu

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL must point to an isolated drill database}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
: "${RESTORE_EXPECTED_DATABASE:?RESTORE_EXPECTED_DATABASE is required}"
: "${RESTORE_DRILL_MARKER:?RESTORE_DRILL_MARKER is required}"
: "${RESTORE_DRILL_CONFIRM:?RESTORE_DRILL_CONFIRM is required}"

if [ "${#BACKUP_ENCRYPTION_KEY}" -lt 32 ]; then
  printf '%s\n' "BACKUP_ENCRYPTION_KEY must be at least 32 characters." >&2
  exit 2
fi

if [ "$RESTORE_DRILL_CONFIRM" != "I_UNDERSTAND_THIS_ERASES_THE_ISOLATED_TARGET" ]; then
  printf '%s\n' "Refusing restore: exact destructive-action confirmation is required." >&2
  exit 2
fi
case "$RESTORE_EXPECTED_DATABASE" in
  *[!A-Za-z0-9_]*|'') printf '%s\n' "Refusing restore: invalid expected database name." >&2; exit 2 ;;
esac
if [ "${#RESTORE_EXPECTED_DATABASE}" -gt 63 ]; then
  printf '%s\n' "Refusing restore: expected database name is too long." >&2
  exit 2
fi
case "$RESTORE_DRILL_MARKER" in
  *[!A-Za-z0-9_.-]*|'') printf '%s\n' "Refusing restore: invalid drill marker." >&2; exit 2 ;;
esac
if [ "${#RESTORE_DRILL_MARKER}" -gt 64 ]; then
  printf '%s\n' "Refusing restore: drill marker is too long." >&2
  exit 2
fi
case "$RESTORE_EXPECTED_DATABASE" in
  *restore*|*drill*) ;;
  *) printf '%s\n' "Refusing restore: database name must visibly contain restore or drill." >&2; exit 2 ;;
esac
if [ "${DATABASE_URL:-}" = "$RESTORE_DATABASE_URL" ]; then
  printf '%s\n' "Refusing restore: target equals DATABASE_URL." >&2
  exit 2
fi
if [ ! -f "$BACKUP_FILE" ] || [ ! -f "${BACKUP_FILE}.sha256" ]; then
  printf '%s\n' "Refusing restore: encrypted backup/checksum pair is incomplete." >&2
  exit 2
fi

BACKUP_NAME="$(basename "$BACKUP_FILE")"
EXPECTED_DIGEST="$(awk 'NR == 1 && NF == 2 { value = $1 } END { if (NR != 1 || value == "") exit 1; print value }' "${BACKUP_FILE}.sha256")" || {
  printf '%s\n' "Refusing restore: checksum manifest is not a single portable entry." >&2
  exit 2
}
RECORDED_NAME="$(awk 'NR == 1 && NF == 2 { value = $2 } END { if (NR != 1 || value == "") exit 1; print value }' "${BACKUP_FILE}.sha256")" || {
  printf '%s\n' "Refusing restore: checksum manifest is not a single portable entry." >&2
  exit 2
}
if [ "$RECORDED_NAME" != "$BACKUP_NAME" ] || [ "${#EXPECTED_DIGEST}" -ne 64 ]; then
  printf '%s\n' "Refusing restore: checksum manifest is not a single portable entry." >&2
  exit 2
fi
case "$EXPECTED_DIGEST" in
  *[!0-9a-f]*) printf '%s\n' "Refusing restore: checksum digest is invalid." >&2; exit 2 ;;
esac
ACTUAL_DIGEST="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"
if [ "$EXPECTED_DIGEST" != "$ACTUAL_DIGEST" ]; then
  printf '%s\n' "Refusing restore: encrypted backup checksum mismatch." >&2
  exit 2
fi

ACTUAL_DATABASE="$(psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT current_database();')"
if [ "$ACTUAL_DATABASE" != "$RESTORE_EXPECTED_DATABASE" ]; then
  printf '%s\n' "Refusing restore: connected database does not match RESTORE_EXPECTED_DATABASE." >&2
  exit 2
fi
ACTUAL_MARKER="$(psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c "SELECT coalesce(shobj_description(oid, 'pg_database'), '') FROM pg_database WHERE datname = current_database();")"
if [ "$ACTUAL_MARKER" != "luma-restore-drill:${RESTORE_DRILL_MARKER}" ]; then
  printf '%s\n' "Refusing restore: target database is missing the exact drill marker." >&2
  exit 2
fi
OTHER_CONNECTIONS="$(psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();")"
if [ "$OTHER_CONNECTIONS" != "0" ]; then
  printf '%s\n' "Refusing restore: target database has other active connections." >&2
  exit 2
fi

PLAIN="$(mktemp)"
trap 'rm -f "$PLAIN"' EXIT
trap 'exit 1' HUP INT TERM
STARTED_AT="$(date +%s)"
openssl enc -d -aes-256-cbc -pbkdf2 -in "$BACKUP_FILE" -out "$PLAIN" -pass env:BACKUP_ENCRYPTION_KEY
pg_restore --list "$PLAIN" >/dev/null
pg_restore --clean --if-exists --exit-on-error --single-transaction --no-owner --no-privileges --dbname "$RESTORE_DATABASE_URL" "$PLAIN"
ALEMBIC_VERSION="$(psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version;')"
case "$ALEMBIC_VERSION" in
  *[!A-Za-z0-9_.-]*|'') printf '%s\n' "Restore validation failed: invalid Alembic version." >&2; exit 1 ;;
esac
TABLE_COUNT="$(psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM (VALUES (to_regclass('public.users')), (to_regclass('public.quit_plans')), (to_regclass('public.behavior_events'))) AS required(name) WHERE name IS NOT NULL;")"
if [ "$TABLE_COUNT" != "3" ]; then
  printf '%s\n' "Restore validation failed: required tables are missing." >&2
  exit 1
fi
psql "$RESTORE_DATABASE_URL" -X -A -t -v ON_ERROR_STOP=1 -c 'SELECT count(*) FROM users UNION ALL SELECT count(*) FROM quit_plans UNION ALL SELECT count(*) FROM behavior_events;' >/dev/null
DURATION="$(( $(date +%s) - STARTED_AT ))"
printf 'RESTORE_DRILL_EVIDENCE backup_sha256=%s alembic=%s target=%s required_tables=3 duration_seconds=%s\n' "$ACTUAL_DIGEST" "$ALEMBIC_VERSION" "$ACTUAL_DATABASE" "$DURATION"
