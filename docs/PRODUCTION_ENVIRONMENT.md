# Production environment contract

The repository deliberately starts only after explicit production configuration.
Copy `.env.example` to a protected `.env` on the deployment host; do not commit
that file or paste its values into support chats.

## Deployment modes

Production defaults to a closed infrastructure preview. Keep
`PUBLIC_LAUNCH_ENABLED=false` for the first VPS deploy: migrations, HTTPS,
landing page, database, Redis and readiness checks remain available, while all
user `/v1` endpoints and notification delivery fail closed. This mode does not
pretend that pending content or legal documents are approved.

Set `PUBLIC_LAUNCH_ENABLED=true` only for an intentional public launch. That
switch activates the additional Telegram, editorial and legal gates below.

## Required for every production deployment

| Variable | Requirement |
| --- | --- |
| `DOMAIN` | Public hostname with DNS A/AAAA records pointed at the host. |
| `APP_ENVIRONMENT` | Exactly `production`. |
| `PUBLIC_LAUNCH_ENABLED` | `false` for a closed preview; `true` only after every public-launch gate passes. |
| `SESSION_SECRET` | New random secret, at least 32 characters. |
| `TELEGRAM_WEBAPP_URL` | `https://<DOMAIN>`; must match Telegram configuration. |
| `CORS_ORIGINS` | Comma-separated allowed origins, normally `https://<DOMAIN>`. |
| `REDIS_PASSWORD` | New random secret, at least 32 characters; never use the development default. |
| `REDIS_URL` | Redis URL that includes the URL-encoded `REDIS_PASSWORD`; it must refer to the internal `redis` host. |
| `RISK_ENGINE_VERSION` | `rules_v1` for the reviewed model, or `baseline` during an incident. |
| `ADMIN_TELEGRAM_IDS` | Comma-separated Telegram numeric IDs for staff overview and feedback triage; leave empty to disable staff endpoints. |
| `ACQUISITION_SOURCES` | Optional comma-separated allowlist of short, non-personal Telegram `startapp` campaign codes. Unlisted codes are discarded. |

## Additional gates for `PUBLIC_LAUNCH_ENABLED=true`

| Variable | Requirement |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Fresh token from BotFather, used only by API/worker. Rotate any token ever pasted into a chat. |
| `TELEGRAM_WEBHOOK_SECRET` | New random secret, at least 24 characters. |
| `CONTENT_REVIEW_STATUS` | Exactly `approved` after editorial sign-off. |
| `CONTENT_APPROVED_DIGEST` | SHA-256 of all production web/API copy printed by `python scripts/content_manifest.py` after signed review; any reviewed-file edit closes preflight. |
| `CONTENT_CATALOGUE_DIGEST` | Exact runtime API catalogue SHA-256 printed by `python -c "from app.content import CONTENT_DIGEST; print(CONTENT_DIGEST)"` in `apps/api`. |
| `LEGAL_DOCUMENTS_STATUS` | Exactly `approved` only after a legal owner has filled and approved the public policy and terms templates. |
| `LEGAL_DOCUMENTS_VERSION` | Immutable identifier of those approved documents (for example, `2026-07-14`); it is recorded with each consent. |
| `LEGAL_DOCUMENTS_DIGEST` | Exact lowercase SHA-256 printed by `python scripts/legal_manifest.py`; it binds consent to the bytes and filenames of `privacy.html` and `terms.html`. |

## Optional integrations

Set the three `TELEGRAM_OIDC_*` variables to enable browser login outside the
Mini App. They are all-or-none; the redirect must be
`https://<DOMAIN>/api/v1/auth/oidc/callback`. Set `VAPID_PUBLIC_KEY`,
`VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT` to
enable web push. Omit either integration entirely until it is configured; the
app remains usable from Telegram Mini App when OIDC is absent.

## First closed-preview smoke test

1. Keep `PUBLIC_LAUNCH_ENABLED=false` and leave pending approval values truthful.
2. Run `python scripts/release_preflight.py`; it must report a production preview.
3. Deploy Compose and confirm `/health`, `/ready` and `/api/v1/launch-status`.
4. Confirm the landing page says the launch is being prepared.
5. Confirm `/api/v1/bootstrap` and `/api/v1/auth/telegram` return 503 with
   `public_launch_disabled` and that the worker sends no notifications.

## Public-launch smoke test

1. Run `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.
2. Confirm `https://<DOMAIN>/health` and `https://<DOMAIN>/ready` return 200.
3. Set the Telegram webhook to `https://<DOMAIN>/v1/telegram/webhook`, then
   inspect `getWebhookInfo` for errors.
4. Complete the path: authenticated user -> consent -> last-pack event -> quit
   mode -> craving -> Telegram message (or configured web push).
5. Export data and delete the test account. Confirm a fresh login requires
   onboarding again.

Never use real support users for smoke tests, and never mark the content as
approved merely to bypass the startup gate.

## Pre-deploy gate

On the deployment host, export the production environment (or load it into
the shell from the protected secret store) and run:

```sh
python scripts/release_preflight.py
```

In closed-preview mode it validates infrastructure settings and confirms that
user access remains disabled. In public mode it additionally binds editorial
and legal approval to the exact committed digests and refuses to pass while
legal pages are pending or contain template values. Before enabling the public
launch, compute the legal value with `python scripts/legal_manifest.py`. The
preflight never prints secret values.

## Changing legal documents

Publish the approved files first, then deploy a new immutable
`LEGAL_DOCUMENTS_VERSION` and their exact `LEGAL_DOCUMENTS_DIGEST`. A change to
either value sends existing users through the consent screen before they can
resume the quit-plan workflow; their plan is retained and is not reset by
re-consent. Each acceptance is appended to immutable consent history and is
included in export. Do not reuse or roll back a version identifier after it has
been shown to users.
