from app import observability


def test_metrics_expose_cumulative_latency_histogram_and_gauges(monkeypatch):
    monkeypatch.setattr(observability, "REQUESTS", observability.Counter({"200": 3, "500": 1}))
    monkeypatch.setattr(observability, "TOTAL_DURATION_MS", 900)
    monkeypatch.setattr(observability, "DURATION_HISTOGRAM", observability.Counter({50: 1, 100: 2, 250: 3, 500: 3, 700: 4, 1000: 4, 2500: 4, 5000: 4}))
    output = observability.metrics_text({"kurilka_database_up": 1})
    assert 'kurilka_api_request_duration_ms_bucket{le="500"} 3' in output
    assert 'kurilka_api_request_duration_ms_bucket{le="+Inf"} 4' in output
    assert "kurilka_api_request_duration_ms_sum 900" in output
    assert "kurilka_api_request_duration_ms_count 4" in output
    assert "kurilka_database_up 1" in output
