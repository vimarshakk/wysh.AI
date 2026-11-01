from app.metrics import Metrics


def test_provider_metrics_are_bounded_and_do_not_contain_request_content():
    metrics = Metrics()
    metrics.observe_provider("medgemma", "success", 237)
    metrics.observe_provider("not-a-provider", "unexpected", 999999)
    rendered = metrics.render()

    assert 'event="provider_route_success_medgemma"' in rendered
    assert 'event="provider_route_failure_unknown"' in rendered
    assert 'event="provider_route_latency_ms_bucket_medgemma_250"' in rendered
    assert "not-a-provider" not in rendered
    assert "prompt" not in rendered.lower()
    assert "clinical" not in rendered.lower()


def test_provider_metrics_have_count_sum_and_buckets():
    metrics = Metrics()
    metrics.observe_provider("gemini", "failure", 1200)
    rendered = metrics.render()
    assert 'event="provider_route_latency_ms_count_gemini"} 1' in rendered
    assert 'event="provider_route_latency_ms_sum_gemini"} 1200' in rendered
    assert 'event="provider_route_latency_ms_bucket_gemini_2500"} 1' in rendered
