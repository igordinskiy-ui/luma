# Backup and restore procedure

The scripts in `scripts/` automate an encrypted PostgreSQL dump, SHA-256 checksum and isolated restore validation. Their presence is not evidence of a successful production backup or drill.

## Tool image

Build the same pinned, non-root image that CI scans:

```sh
docker build -f apps/backup/Dockerfile -t luma-backup:local .
```

It contains PostgreSQL 16.14 clients and pinned OpenSSL, runs as UID 70, and
does not contain `gosu`. The mounted backup directory must be writable by UID
70. Do not add the deploy user to broader storage groups only to bypass this
ownership contract.

## Backup

Run `scripts/backup-postgres.sh` from a protected scheduler with `DATABASE_URL`, `BACKUP_ENCRYPTION_KEY` and an encrypted storage-mounted `BACKUP_DIR`. Upload the `.enc` and `.sha256` pair to immutable storage, record the object version, checksum, timestamp and owner, then apply the approved lifecycle policy.

The encryption key must be at least 32 characters and is passed only through
the environment. The script creates the plaintext with mode `0600`, removes it
on success, failure or signal, writes the encrypted object and a basename-only
portable checksum through temporary files, and emits a non-secret
`BACKUP_EVIDENCE` line. An artifact without its checksum pair is incomplete.

## Restore drill

Provision a clean isolated database with a name containing `restore` or `drill`.
Before the destructive command, add an exact per-drill marker as a privileged
operator:

```sql
COMMENT ON DATABASE restore_drill IS 'luma-restore-drill:unique-drill-marker';
```

Set `RESTORE_DATABASE_URL`, `BACKUP_FILE`, `BACKUP_ENCRYPTION_KEY`,
`RESTORE_EXPECTED_DATABASE`, `RESTORE_DRILL_MARKER` and the exact confirmation
`RESTORE_DRILL_CONFIRM=I_UNDERSTAND_THIS_ERASES_THE_ISOLATED_TARGET`. Also pass
the production `DATABASE_URL` when available; equality is rejected. The script
connects before decrypting, verifies the actual database name, exact database
comment and absence of other sessions, then checks the portable checksum and
dump catalogue. Restore is fail-fast in one transaction.

Attach the safe `RESTORE_DRILL_EVIDENCE` line, protected exact row-count
comparison, start/end timestamps and isolated-environment cleanup evidence to
the drill record. CI runs `scripts/backup_restore_smoke.sh` against two
ephemeral PostgreSQL instances and proves marker rejection, row/version parity
and encrypted-file tamper rejection. That synthetic CI drill is regression
evidence for the tooling, not evidence of a production backup, storage policy,
RPO or RTO.

## Unresolved owner decisions

- approved RPO and RTO;
- backup frequency and freshness SLO;
- storage provider, region, encryption-key custody and access review;
- immutable retention and deletion/rotation period;
- restore-drill cadence and named operator/escalation owner.

Until these are approved and a dated drill succeeds, the production restore gate remains externally blocked.
