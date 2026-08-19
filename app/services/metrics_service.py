from typing import Any


class MetricsService:
    def get_metrics(self) -> dict[str, Any]:
        return {
            "status": "not_available",
            "message": "Model metrics are not available until models are trained.",
            "metrics": {},
        }