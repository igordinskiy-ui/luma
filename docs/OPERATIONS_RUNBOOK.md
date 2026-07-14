# Operations runbook

This runbook is an operational procedure, not proof that controls exist. Record
the incident/deploy ID, owner, timestamps and evidence for every execution.

## Deploy and rollback

1. Build and test the tagged image in CI; record the immutable image reference and approved change.
2. Verify a successful backup within the owner-approved freshness SLO, its checksum, storage encryption and the last successful restore drill.
3. Apply `alembic upgrade head`, deploy API and worker, then check `/health` and `/ready`.
4. Complete the production smoke test from `PRODUCTION_ENVIRONMENT.md`, including export and deletion of a synthetic account.
5. If health checks fail, stop the rollout, restore the previous image and assess migration compatibility. Do not run `alembic downgrade` unless reversibility is explicitly confirmed and the change owner approves it.

## Telegram webhook

After HTTPS deployment, call Telegram `setWebhook` with `https://<domain>/v1/telegram/webhook` and `TELEGRAM_WEBHOOK_SECRET`. Verify `getWebhookInfo` has no errors; never place the bot token in the web client. Complete `TELEGRAM_SETUP.md` before accepting public users.

## Privacy requests

1. Create a support record with request ID, receipt time, requested right and secure contact channel. Do not copy tokens, passwords or unneeded sensitive content into the ticket.
2. Authenticate the requester using the legal-owner-approved identity verification method; record only the minimum proof needed.
3. Use the authenticated export/deletion functions where applicable. For requests that cannot be self-served, assign the privacy owner and legal reviewer.
4. Check legal deadline, any permitted exceptions and effect on active data, logs and backups. Explain backup rotation truthfully; do not promise immediate erasure from immutable backup media.
5. Record decision, response time, evidence of completion and deletion/retention deadline. Escalate complaints or missed deadlines to the named privacy escalation contact in the incident roster.

## Personal-data/security incident

1. Open incident record; preserve relevant logs and identify incident commander, security and privacy/legal contacts.
2. Contain: revoke exposed credentials/sessions, restrict access or stop affected processing without destroying evidence.
3. Establish scope: systems, data categories, subjects, time window, recipient and ongoing risk. Do not speculate externally.
4. Consult the privacy/legal owner immediately to determine statutory notifications and deadlines. Send only approved notices; track acknowledgement and follow-up.
5. Recover, rotate credentials, validate monitoring, document root cause and corrective actions. Hold a post-incident review within the owner-approved incident SLA.

## Database failure and restore

1. Stop writes and declare the incident. Select the last verified encrypted backup according to approved RPO.
2. Restore only into a clean, isolated instance first. Validate backup checksum, migration version, row-count sanity checks and `/ready` (Postgres + Redis), not only `/health`, without exposing the instance publicly.
3. Obtain incident commander approval before switching API connections. Record actual RPO/RTO.
4. Destroy the temporary restore environment and credentials after verification according to the retention policy.

## Other safety actions

- **Message spam:** globally disable notification preferences, stop the worker, investigate outbox and document affected users.
- **Medical distress:** do not diagnose; use the approved escalation script and direct the user to local emergency/medical services.
- **Risk-score issue:** set `RISK_ENGINE_VERSION=baseline`, redeploy API and worker, verify dashboard risk is `low` while coping prompts continue to work. Do not switch it back without documented review.

## Metrics access

Scrapers must call `http://api:8000/internal/metrics` from the private
application network and send `X-Proxy-Secret` from the protected secret store.
The public edge intentionally returns 404 for `/api/internal/*`. Never publish
the API container port or reuse the proxy secret in a browser/dashboard URL.
