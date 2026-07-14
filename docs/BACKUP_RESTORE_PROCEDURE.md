# Backup and restore procedure

The scripts in `scripts/` automate an encrypted PostgreSQL dump, SHA-256 checksum and isolated restore validation. Their presence is not evidence of a successful production backup or drill.

## Backup

Run `scripts/backup-postgres.sh` from a protected scheduler with `DATABASE_URL`, `BACKUP_ENCRYPTION_KEY` and an encrypted storage-mounted `BACKUP_DIR`. Upload the `.enc` and `.sha256` pair to immutable storage, record the object version, checksum, timestamp and owner, then apply the approved lifecycle policy.

## Restore drill

Provision a clean isolated database whose URL visibly contains `restore` or `drill`, set `RESTORE_DATABASE_URL`, `BACKUP_FILE` and the encryption key, then run `scripts/restore-drill.sh`. Attach checksum output, Alembic version, row-count sanity check, start/end timestamps and cleanup evidence to the incident/deploy record.

## Unresolved owner decisions

- approved RPO and RTO;
- backup frequency and freshness SLO;
- storage provider, region, encryption-key custody and access review;
- immutable retention and deletion/rotation period;
- restore-drill cadence and named operator/escalation owner.

Until these are approved and a dated drill succeeds, the production restore gate remains externally blocked.
