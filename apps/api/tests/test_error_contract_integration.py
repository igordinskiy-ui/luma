"""Runs in CI's Python 3.12 environment with the full API dependency set."""
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@app.get("/__test__/unexpected-error")
def unexpected_error_for_contract_test():
    raise RuntimeError("private payload must never leave the server")


def test_validation_errors_have_stable_shape_and_request_id():
    with TestClient(app) as client:
        response = client.post("/v1/auth/telegram", json={"init_data": "short"}, headers={"X-Request-ID": "contract-test-request"})
    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "contract-test-request"
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["request_id"] == "contract-test-request"
    assert response.json()["error"]["field_errors"]


def test_payload_limit_uses_the_same_error_contract(monkeypatch):
    monkeypatch.setattr(settings, "max_request_body_bytes", 5)
    with TestClient(app) as client:
        response = client.post("/v1/auth/telegram", json={"init_data": "long-enough"}, headers={"X-Request-ID": "large-body-request"})
    assert response.status_code == 413
    assert response.headers["X-Request-ID"] == "large-body-request"
    assert response.json() == {"error": {"code": "payload_too_large", "message": "Request body is too large", "request_id": "large-body-request"}}


def test_payload_limit_counts_streamed_bytes_without_content_length(monkeypatch):
    monkeypatch.setattr(settings, "max_request_body_bytes", 5)

    def body_chunks():
        yield b'{"ini'
        yield b't_data":"long-enough"}'

    with TestClient(app) as client:
        response = client.post(
            "/v1/auth/telegram",
            content=body_chunks(),
            headers={"X-Request-ID": "chunked-large-body", "Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert response.json() == {"error": {"code": "payload_too_large", "message": "Request body is too large", "request_id": "chunked-large-body"}}


def test_auth_and_router_errors_use_the_same_contract():
    with TestClient(app) as client:
        unauthenticated = client.get("/v1/bootstrap", headers={"X-Request-ID": "auth-contract-request"})
        missing = client.get("/v1/route-that-does-not-exist", headers={"X-Request-ID": "missing-contract-request"})
        wrong_method = client.delete("/v1/bootstrap", headers={"X-Request-ID": "method-contract-request"})

    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"error": {"code": "http_401", "message": "Authentication required", "request_id": "auth-contract-request"}}
    assert missing.status_code == 404
    assert missing.json() == {"error": {"code": "http_404", "message": "Not Found", "request_id": "missing-contract-request"}}
    assert wrong_method.status_code == 405
    assert wrong_method.json() == {"error": {"code": "http_405", "message": "Method Not Allowed", "request_id": "method-contract-request"}}


def test_unexpected_error_is_sanitized_and_correlated():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/unexpected-error", headers={"X-Request-ID": "internal-contract-request"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "internal-contract-request"
    assert response.json() == {"error": {"code": "internal_error", "message": "Internal server error", "request_id": "internal-contract-request"}}
    assert "private payload" not in response.text


def test_untrusted_request_id_is_replaced_before_logging_or_display():
    with TestClient(app) as client:
        response = client.get("/v1/route-that-does-not-exist", headers={"X-Request-ID": "line-one\nline-two"})

    generated = response.json()["error"]["request_id"]
    assert response.status_code == 404
    assert generated == response.headers["X-Request-ID"]
    assert generated != "line-one\nline-two"
    assert len(generated) == 36


def test_internal_metrics_require_the_private_scraper_secret(monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", "metrics-private-secret")
    with TestClient(app) as client:
        assert client.get("/internal/metrics").status_code == 404
        allowed = client.get("/internal/metrics", headers={"X-Proxy-Secret": "metrics-private-secret"})
    assert allowed.status_code == 200
    assert "kurilka_api_requests_total" in allowed.text
    assert 'kurilka_api_request_duration_ms_bucket{le="500"}' in allowed.text
    assert "kurilka_database_up 1" in allowed.text
    assert "kurilka_outbox_pending" in allowed.text
    assert "kurilka_worker_heartbeat_age_seconds" in allowed.text
