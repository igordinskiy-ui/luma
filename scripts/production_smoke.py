"""Non-interactive production smoke for a dedicated synthetic account."""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(base: str, path: str, token: str = "", method: str = "GET") -> object:
    request = Request(base.rstrip("/") + path, method=method, headers={"Accept": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read()
            if response.status >= 300:
                raise RuntimeError(f"{path} returned {response.status}")
            return json.loads(body) if body else None
    except HTTPError as exc:
        raise RuntimeError(f"{path} returned {exc.code}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("SMOKE_BASE_URL", ""))
    parser.add_argument("--token", default=os.environ.get("SMOKE_ACCESS_TOKEN", ""))
    parser.add_argument("--delete", action="store_true", help="Delete the dedicated synthetic account after export")
    args = parser.parse_args()
    if not args.base_url.startswith("https://"):
        parser.error("--base-url must be an HTTPS origin")
    if not args.token:
        parser.error("--token must belong to a dedicated synthetic account")

    call(args.base_url, "/health")
    call(args.base_url, "/ready")
    dashboard = call(args.base_url, "/api/v1/dashboard", args.token)
    exported = call(args.base_url, "/api/v1/privacy-export", args.token)
    if not isinstance(dashboard, dict) or "phase" not in dashboard:
        raise RuntimeError("dashboard response is incomplete")
    if not isinstance(exported, dict) or "events" not in exported or "coping_sessions" not in exported:
        raise RuntimeError("privacy export is incomplete")
    if args.delete:
        call(args.base_url, "/api/v1/account", args.token, "DELETE")
    print("Production smoke passed" + ("; synthetic account deleted." if args.delete else "; deletion not requested."))
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"Production smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
