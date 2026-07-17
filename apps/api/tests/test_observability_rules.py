from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RULES = (ROOT / "ops" / "prometheus" / "luma-alerts.yml").read_text(encoding="utf-8")
RULE_TESTS = (ROOT / "ops" / "prometheus" / "luma-alerts.test.yml").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def test_alert_contract_covers_release_gate_signals_without_user_labels():
    for alert in (
        "LumaApiLatencyHigh",
        "LumaApiErrorRateHigh",
        "LumaApiErrorRateCritical",
        "LumaDatabaseUnavailable",
        "LumaMetricsMissing",
        "LumaWorkerHeartbeatUnavailable",
        "LumaOutboxBacklogHigh",
        "LumaOutboxBacklogGrowing",
        "LumaOutboxHasFailedRecords",
        "LumaDeliveryFailureRatioHigh",
    ):
        assert f"alert: {alert}" in RULES
    assert "{{" not in RULES
    assert "telegram_id" not in RULES.lower()
    assert "push_endpoint" not in RULES.lower()
    assert "request_id" not in RULES.lower()


def test_promtool_synthetic_suite_covers_threshold_and_for_window_behaviour():
    for alert in (
        "LumaApiLatencyHigh",
        "LumaApiErrorRateHigh",
        "LumaDatabaseUnavailable",
        "LumaWorkerHeartbeatUnavailable",
        "LumaOutboxBacklogHigh",
        "LumaOutboxHasFailedRecords",
        "LumaDeliveryFailureRatioHigh",
    ):
        assert f"alertname: {alert}" in RULE_TESTS
    assert "exp_alerts: []" in RULE_TESTS


def test_ci_runs_promtool_from_an_immutable_current_image():
    image = "prom/prometheus:v3.12.0@sha256:69f5241418838263316593f7274a304b095c40bcf22e57272865da91bd60a8ac"
    assert WORKFLOW.count(image) == 2
    assert "promtool" in WORKFLOW and "check rules" in WORKFLOW and "test rules" in WORKFLOW
