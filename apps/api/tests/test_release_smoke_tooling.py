import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from production_smoke import validate_base_url  # noqa: E402


@pytest.mark.parametrize(
    "value",
    [
        "",
        "http://app.example.test",
        "https://user@app.example.test",
        "https://app.example.test/path",
        "https://app.example.test/?token=secret",
        "https://app.example.test/#fragment",
        "https://app.example.test:99999",
    ],
)
def test_production_smoke_rejects_non_origin_or_credential_urls(value):
    with pytest.raises(ValueError):
        validate_base_url(value)


def test_production_smoke_normalizes_safe_https_origin():
    assert validate_base_url("https://app.example.test/") == "https://app.example.test"


def test_load_smoke_has_safe_capacity_and_evidence_contract():
    script = (ROOT / "scripts" / "load-smoke.js").read_text(encoding="utf-8")
    assert "const EXPECTED_VUS = 50" in script
    assert "p(95)<500" in script
    assert "p(95)<700" in script
    assert "rate<0.01" in script
    assert "checks: ['rate==1']" in script
    assert "exactly ${EXPECTED_VUS} unique dedicated synthetic-account tokens" in script
    assert "LOAD_PRODUCTION_CONFIRMATION" in script
    assert "luma-load-smoke/v1" in script
    assert "target_origin" in script
    assert "Authorization" not in re.sub(r"export default function.*?export function handleSummary", "", script, flags=re.S)


def test_operations_runbook_requires_sanitized_load_evidence_and_fifty_accounts():
    runbook = (ROOT / "docs" / "OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", runbook)
    assert "50 unique synthetic accounts" in normalized
    assert "load-smoke-evidence.json" in normalized
    assert "does not prove staging or production capacity" in normalized
