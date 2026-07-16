# Production deploy runner

`scripts/deploy_production.py` is the repository-owned forced-command target
for the restricted `luma-deploy` SSH account. Installing it changes external
VPS state and must be performed by the server owner; committing this document
does not prove installation.

## Host contract

- Linux host with Python 3.12+, Git, Docker Engine and Compose v2.
- Checkout at `LUMA_REPO_DIR`, owned by `luma-deploy`, with protected `.env`.
- `LUMA_MIN_DEPLOY_REVISION` pinned to the reviewed commit that introduced the
  installed runner, preventing rollback to a revision that can remove it.
- Root-owned deploy configuration outside the checkout.
- A writable, pre-created `LUMA_DEPLOY_LOCK` for serialized deployments.
- `SMOKE_BASE_URL` set to the production HTTPS origin.
- Optional dedicated `SMOKE_ACCESS_TOKEN`; it enables dashboard/export smoke
  and must never belong to a real user.

Before enabling the runner, confirm that `docker-compose.prod.yml` is the
authoritative owner of ports 80/443. A separate system Caddy/nginx instance
would conflict with the Compose edge and requires an owner-approved cutover.

Membership in the Docker group is effectively root-level access. Keep the
account restricted to one CI key and one forced command; do not allow an
interactive shell, forwarding, agent forwarding or PTY allocation.

## Installation

Create `/etc/luma/deploy-runner.env` as root with mode `0600`:

```text
LUMA_REPO_DIR=/srv/luma
LUMA_DEPLOY_LOCK=/var/lock/luma-deploy.lock
LUMA_MIN_DEPLOY_REVISION=40_CHARACTER_INSTALLATION_COMMIT_SHA
SMOKE_BASE_URL=https://your-production-origin.example
```

Optionally add `SMOKE_ACCESS_TOKEN` for a dedicated synthetic account. Create
the lock as root, then assign only that file to the deploy user:

```sh
install -o luma-deploy -g luma-deploy -m 0600 /dev/null /var/lock/luma-deploy.lock
```

Install this root-owned wrapper as `/usr/local/sbin/luma-deploy-command` with
mode `0755`:

```sh
#!/bin/sh
set -eu
set -a
. /etc/luma/deploy-runner.env
set +a
exec /usr/bin/python3 "$LUMA_REPO_DIR/scripts/deploy_production.py"
```

The environment file is sourced only because it is root-owned and not writable
by `luma-deploy`. Add the CI public key to the account's `authorized_keys` with
OpenSSH restrictions:

```text
restrict,command="/usr/local/sbin/luma-deploy-command" ssh-ed25519 CI_PUBLIC_KEY_COMMENTED_BY_OWNER
```

The runner reads the requested revision from `SSH_ORIGINAL_COMMAND`, accepts
only a lowercase 40-character SHA, fetches `origin/main`, and rejects commits
that are not ancestors of that protected branch or descendants of the pinned
runner floor. The target must itself contain `scripts/deploy_production.py`, so
a rollback cannot remove the next forced-command entrypoint. It refuses a dirty
tracked checkout or concurrent deployment.

## Deployment and evidence

For an accepted revision the runner performs:

1. detached checkout of the exact tested SHA;
2. production Compose validation and `build --pull` for every buildable service;
3. `up -d --remove-orphans --wait`, including migration and Caddy;
4. real Caddy process verification: UID/GID 1000 and `NoNewPrivs=1`;
5. external HTTPS `/health` and `/ready` probes;
6. optional authenticated dashboard/export smoke.

Success prints exactly one safe line without secrets:

```text
LUMA_DEPLOY_EVIDENCE revision=<sha> previous=<sha> caddy_uid=1000 no_new_privs=1 health=200 ready=200 synthetic=passed|not_configured
```

After the owner installs and verifies the wrapper, set the GitHub repository
variable `LUMA_DEPLOY_EVIDENCE_REQUIRED=true`. Until then CI emits a warning
instead of treating the legacy runner's `Deployed <sha>` output as edge proof.

## Failure and rollback

Any failed command stops the deployment and prints `LUMA_DEPLOY_FAILED` without
environment values. The runner does not automatically downgrade the database
or deploy an older application. Before passing a previous green SHA, verify its
forward-schema compatibility and obtain the required operational approval.
Record the failed run, current migration head, selected revision, external
health evidence and the actual rollback duration.
