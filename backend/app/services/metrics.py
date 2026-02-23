class MetricsCollector:
    def write_sample(self, run_id: str, metric_name: str, value: float) -> None:
        # Placeholder for metrics ingestion/storage.
        _ = (run_id, metric_name, value)

    def summarize(self, run_id: str) -> dict:
        return {"run_id": run_id, "rps": 0, "latency_p95_ms": None, "error_rate": 0.0}

