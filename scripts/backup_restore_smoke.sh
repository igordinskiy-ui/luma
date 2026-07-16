#!/bin/sh
set -eu

RAW_ID="${GITHUB_RUN_ID:-local}-$$"
DRILL_ID="$(printf '%s' "$RAW_ID" | tr -cd 'A-Za-z0-9-')"
NETWORK="luma-restore-net-${DRILL_ID}"
SOURCE="luma-backup-source-${DRILL_ID}"
TARGET="luma-backup-target-${DRILL_ID}"
BACKUPS="luma-backups-${DRILL_ID}"
PASSWORD="ci-restore-password"
KEY="ci-backup-encryption-key-at-least-32-characters"
MARKER="ci-${DRILL_ID}"

cleanup() {
  docker rm -f "$SOURCE" "$TARGET" >/dev/null 2>&1 || true
  docker volume rm "$BACKUPS" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

wait_for_postgres() {
  container="$1"
  database="$2"
  attempts=0
  until docker exec "$container" pg_isready -U postgres -d "$database" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      docker logs "$container" >&2
      return 1
    fi
    sleep 1
  done
}

docker network create "$NETWORK" >/dev/null
docker volume create "$BACKUPS" >/dev/null
docker run --rm --user 0:0 --entrypoint chown -v "$BACKUPS:/backups" luma-backup:local 70:70 /backups

docker run -d --name "$SOURCE" --network "$NETWORK" \
  --tmpfs /var/lib/postgresql/data:rw,uid=70,gid=70 \
  -e POSTGRES_DB=source -e POSTGRES_PASSWORD="$PASSWORD" luma-postgres:local >/dev/null
docker run -d --name "$TARGET" --network "$NETWORK" \
  --tmpfs /var/lib/postgresql/data:rw,uid=70,gid=70 \
  -e POSTGRES_DB=restore_drill -e POSTGRES_PASSWORD="$PASSWORD" luma-postgres:local >/dev/null
wait_for_postgres "$SOURCE" source
wait_for_postgres "$TARGET" restore_drill

docker exec -i "$SOURCE" psql -U postgres -d source -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
CREATE TABLE alembic_version (version_num varchar(64) PRIMARY KEY);
INSERT INTO alembic_version VALUES ('20260717_drill');
CREATE TABLE users (id bigint PRIMARY KEY);
CREATE TABLE quit_plans (id bigint PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id));
CREATE TABLE behavior_events (id bigint PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id));
INSERT INTO users VALUES (1), (2);
INSERT INTO quit_plans VALUES (10, 1);
INSERT INTO behavior_events VALUES (20, 1), (21, 2);
SQL
docker exec "$TARGET" psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -c "COMMENT ON DATABASE restore_drill IS 'luma-restore-drill:${MARKER}'" >/dev/null

SOURCE_URL="postgresql://postgres:${PASSWORD}@${SOURCE}:5432/source"
TARGET_URL="postgresql://postgres:${PASSWORD}@${TARGET}:5432/restore_drill"
BACKUP_OUTPUT="$(docker run --rm --network "$NETWORK" -v "$BACKUPS:/backups" \
  -e DATABASE_URL="$SOURCE_URL" -e BACKUP_ENCRYPTION_KEY="$KEY" \
  -e BACKUP_DIR=/backups luma-backup:local)"
printf '%s\n' "$BACKUP_OUTPUT"
BACKUP_NAME="$(printf '%s\n' "$BACKUP_OUTPUT" | sed -n 's/^BACKUP_EVIDENCE file=\([^ ]*\) checksum=.*/\1/p')"
case "$BACKUP_NAME" in
  kurilka-*.dump.enc) ;;
  *) printf '%s\n' "Backup smoke did not receive a safe evidence filename." >&2; exit 1 ;;
esac

restore() {
  marker="$1"
  docker run --rm --network "$NETWORK" -v "$BACKUPS:/backups:ro" \
    -e DATABASE_URL="$SOURCE_URL" \
    -e RESTORE_DATABASE_URL="$TARGET_URL" \
    -e BACKUP_FILE="/backups/${BACKUP_NAME}" \
    -e BACKUP_ENCRYPTION_KEY="$KEY" \
    -e RESTORE_EXPECTED_DATABASE=restore_drill \
    -e RESTORE_DRILL_MARKER="$marker" \
    -e RESTORE_DRILL_CONFIRM=I_UNDERSTAND_THIS_ERASES_THE_ISOLATED_TARGET \
    luma-backup:local restore-drill
}

if restore wrong-marker >/dev/null 2>&1; then
  printf '%s\n' "Restore smoke accepted a target without the exact drill marker." >&2
  exit 1
fi
restore "$MARKER"

RESULT="$(docker exec "$TARGET" psql -U postgres -d restore_drill -X -A -t -v ON_ERROR_STOP=1 \
  -c "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM quit_plans), (SELECT count(*) FROM behavior_events), (SELECT version_num FROM alembic_version);")"
if [ "$RESULT" != "2|1|2|20260717_drill" ]; then
  printf '%s\n' "Restore smoke row/version validation failed." >&2
  exit 1
fi

docker run --rm --user 70:70 --entrypoint sh -v "$BACKUPS:/backups" luma-backup:local \
  -c "printf x >> '/backups/${BACKUP_NAME}'"
if restore "$MARKER" >/dev/null 2>&1; then
  printf '%s\n' "Restore smoke accepted a tampered encrypted backup." >&2
  exit 1
fi

printf 'BACKUP_RESTORE_SMOKE_EVIDENCE source_rows=2/1/2 marker_rejection=passed tamper_rejection=passed\n'
