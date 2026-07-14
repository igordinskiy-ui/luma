"""Fail when a remote GitHub Action is not pinned to a full commit SHA."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([^\s#]+)")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def unpinned_actions(text: str) -> list[str]:
    failures: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = USES.match(line)
        if not match or match.group(1).startswith("./"):
            continue
        if not FULL_SHA.fullmatch(match.group(2)):
            failures.append(f"line {line_number}: {match.group(1)}@{match.group(2)}")
    return failures


def main() -> int:
    failures = unpinned_actions(WORKFLOW.read_text(encoding="utf-8"))
    if failures:
        print("Remote GitHub Actions must use a full lowercase commit SHA:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("CI action pins: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
