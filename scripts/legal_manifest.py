"""Print the immutable digest of the public privacy policy and terms."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGAL_PAGES = (
    ROOT / "apps" / "web" / "public" / "privacy.html",
    ROOT / "apps" / "web" / "public" / "terms.html",
)


def legal_documents_digest() -> str:
    digest = hashlib.sha256()
    for path in LEGAL_PAGES:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    print(legal_documents_digest())
