import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from legal_manifest import LEGAL_PAGES, legal_documents_digest  # noqa: E402


def test_legal_digest_covers_both_named_public_documents():
    expected = hashlib.sha256()
    assert [path.name for path in LEGAL_PAGES] == ["privacy.html", "terms.html"]
    for path in LEGAL_PAGES:
        expected.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        expected.update(b"\0")
        expected.update(path.read_bytes())
        expected.update(b"\0")
    assert legal_documents_digest() == expected.hexdigest()
