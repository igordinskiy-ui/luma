from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKUP = (ROOT / "scripts" / "backup-postgres.sh").read_text(encoding="utf-8")
RESTORE = (ROOT / "scripts" / "restore-drill.sh").read_text(encoding="utf-8")
SMOKE = (ROOT / "scripts" / "backup_restore_smoke.sh").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "apps" / "backup" / "Dockerfile").read_text(encoding="utf-8")


def test_backup_cleans_plaintext_and_publishes_portable_checksum_atomically():
    assert '${#BACKUP_ENCRYPTION_KEY}' in BACKUP
    assert '-lt 32' in BACKUP
    assert 'trap cleanup EXIT' in BACKUP
    assert 'rm -f "$PLAIN"' in BACKUP
    assert 'printf \'%s  %s\\n\' "$DIGEST" "$BASENAME"' in BACKUP
    assert 'mv "$ENCRYPTED_TMP" "$ENCRYPTED"' in BACKUP
    assert 'mv "$CHECKSUM_TMP" "$CHECKSUM"' in BACKUP
    assert "BACKUP_EVIDENCE" in BACKUP


def test_restore_requires_exact_database_marker_and_destructive_confirmation():
    assert '${#BACKUP_ENCRYPTION_KEY}' in RESTORE
    assert '-lt 32' in RESTORE
    assert "I_UNDERSTAND_THIS_ERASES_THE_ISOLATED_TARGET" in RESTORE
    assert "RESTORE_EXPECTED_DATABASE" in RESTORE
    assert "shobj_description" in RESTORE
    assert "luma-restore-drill:${RESTORE_DRILL_MARKER}" in RESTORE
    assert 'target equals DATABASE_URL' in RESTORE
    assert "*localhost*|*127.0.0.1*|*restore*|*drill*" not in RESTORE


def test_restore_validates_manifest_before_transactional_destructive_restore():
    checksum_position = RESTORE.index('checksum mismatch')
    decrypt_position = RESTORE.index('openssl enc -d')
    restore_position = RESTORE.index('pg_restore --clean')
    assert checksum_position < decrypt_position < restore_position
    assert "--exit-on-error --single-transaction" in RESTORE
    assert "required tables are missing" in RESTORE
    assert "RESTORE_DRILL_EVIDENCE" in RESTORE


def test_real_docker_drill_covers_marker_and_tamper_rejection_with_cleanup():
    assert "marker_rejection=passed tamper_rejection=passed" in SMOKE
    assert "docker rm -f \"$SOURCE\" \"$TARGET\"" in SMOKE
    assert "docker volume rm \"$BACKUPS\"" in SMOKE
    assert "docker network rm \"$NETWORK\"" in SMOKE


def test_backup_image_is_pinned_non_root_and_has_exact_openssl_version():
    assert "postgres:16.14-alpine@sha256:" in DOCKERFILE
    assert "openssl=3.5.7-r0" in DOCKERFILE
    assert "rm -f /usr/local/bin/gosu" in DOCKERFILE
    assert "USER postgres" in DOCKERFILE
