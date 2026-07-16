"""Fail when CI actions or production container images are mutable."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CONTAINER_FILES = (
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.prod.yml",
    ROOT / "apps" / "api" / "Dockerfile",
    ROOT / "apps" / "web" / "Dockerfile",
    ROOT / "apps" / "postgres" / "Dockerfile",
    ROOT / "apps" / "caddy" / "Dockerfile",
    ROOT / "apps" / "backup" / "Dockerfile",
    WORKFLOW,
)
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([^\s#]+)")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
REMOTE_IMAGE = re.compile(
    r"(?<![\w./-])(?:docker\.io/library/)?"
    r"(?:postgres|redis|caddy|python|node|nginx):[A-Za-z0-9._-]+"
    r"(?:@sha256:[0-9a-f]{64})?"
)


def unpinned_actions(text: str) -> list[str]:
    failures: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = USES.match(line)
        if not match or match.group(1).startswith("./"):
            continue
        if not FULL_SHA.fullmatch(match.group(2)):
            failures.append(f"line {line_number}: {match.group(1)}@{match.group(2)}")
    return failures


def unpinned_container_images(text: str, source: str = "input") -> list[str]:
    failures: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("image:"):
            candidates = REMOTE_IMAGE.finditer(stripped.removeprefix("image:").strip())
        elif stripped.startswith("FROM "):
            candidates = REMOTE_IMAGE.finditer(stripped.removeprefix("FROM ").strip())
        elif "docker run" in line:
            candidates = REMOTE_IMAGE.finditer(line)
        else:
            continue
        for match in candidates:
            reference = match.group(0)
            if "@sha256:" not in reference:
                failures.append(f"{source}:{line_number}: {reference}")
    return failures


def main() -> int:
    action_failures = unpinned_actions(WORKFLOW.read_text(encoding="utf-8"))
    container_failures = [
        failure
        for path in CONTAINER_FILES
        for failure in unpinned_container_images(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
    ]
    if action_failures:
        print("Remote GitHub Actions must use a full lowercase commit SHA:")
        for failure in action_failures:
            print(f"- {failure}")
    if container_failures:
        print("Remote production and CI images must use an immutable sha256 digest:")
        for failure in container_failures:
            print(f"- {failure}")
    if action_failures or container_failures:
        return 1
    print("CI action and container image pins: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
