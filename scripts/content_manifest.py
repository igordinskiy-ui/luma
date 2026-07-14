"""Print the immutable review digest for all committed production copy."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def reviewed_files() -> list[Path]:
    files = [ROOT / "apps" / "api" / "app" / "content.py"]
    features = ROOT / "apps" / "web" / "src" / "features"
    files.extend(path for path in features.rglob("*.tsx") if "design" not in path.parts)
    files.extend((ROOT / "apps" / "web" / "public").glob("*.html"))
    files.extend((ROOT / "apps" / "web" / "public").glob("*.json"))
    files.extend((ROOT / "apps" / "web" / "public").glob("*.webmanifest"))
    files.append(ROOT / "apps" / "web" / "public" / "sw.js")
    files.append(ROOT / "apps" / "web" / "index.html")
    return sorted(files)


def release_content_digest() -> str:
    digest = hashlib.sha256()
    for path in reviewed_files():
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    print(release_content_digest())
