# Network egress policy

Compose separates stateful services onto the internal `data` network and gives
outbound access only to API/worker workloads. The Docker network alone does not
enforce a destination allowlist; production needs a host firewall or egress
proxy, and its dated rule export is release evidence.

## Required destinations

| Workload | Destination | Purpose |
| --- | --- | --- |
| API | `oauth.telegram.org:443` | OIDC authorization code and JWKS |
| Worker | `api.telegram.org:443` | Telegram delivery |
| Worker | approved endpoints under `fcm.googleapis.com`, `updates.push.services.mozilla.com`, `push.services.mozilla.com`, `web.push.apple.com` on 443 | Web Push delivery |
| API/worker | approved DNS resolver and time source | name resolution and clock correctness |

Default-deny all other outbound traffic. Block RFC1918, loopback, link-local,
metadata and other reserved destinations at the egress layer. Log destination,
workload, decision and bytes without request bodies, Telegram IDs, notes,
tokens or subscription keys. Alert on denied bursts and allowlist changes.

`PushSubscriptionIn` independently allowlists endpoint hosts, while OIDC hosts
are constants in code. These application checks complement, but do not replace,
the network control. Until the production firewall/proxy rule is applied and
tested, the egress gate remains external-blocked.
