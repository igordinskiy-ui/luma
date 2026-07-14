#!/bin/sh
set -eu

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL must point to an isolated drill database}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY is required}"
case "$RESTORE_DATABASE_URL" in
  *localhost*|*127.0.0.1*|*restore*|*drill*) ;;
  *) printf '%s\n' "Refusing restore: target must be visibly isolated (localhost/restore/drill)." >&2; exit 2 ;;
esac

sha256sum -c "${BACKUP_FILE}.sha256"
PLAIN="$(mktemp)"
trap 'rm -f "$PLAIN"' EXIT
openssl enc -d -aes-256-cbc -pbkdf2 -in "$BACKUP_FILE" -out "$PLAIN" -pass env:BACKUP_ENCRYPTION_KEY
pg_restore --clean --if-exists --no-owner --no-privileges --dbname "$RESTORE_DATABASE_URL" "$PLAIN"
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT version_num FROM alembic_version;"
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c "SELECT 'users' AS table_name, count(*) FROM users UNION ALL SELECT 'quit_plans', count(*) FROM quit_plans UNION ALL SELECT 'behavior_events', count(*) FROM behavior_events;"
