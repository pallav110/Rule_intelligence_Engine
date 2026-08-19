from app.services.metrics_service import MetricsService


def test_metrics_are_not_available_without_trained_models():
    result = MetricsService().get_metrics()

    assert result["status"] == "not_available"
    assert result["metrics"] == {}