class RecommendationEngine:
    """Stub rule engine. Replace with metric-driven detectors and ranking."""

    def generate_stub(self, run_id: str) -> list[dict]:
        return [
            {
                "recommendation_id": f"rec_{run_id}_cache",
                "technology": "Redis",
                "category": "caching",
                "problem_observed": "High read latency under burst load (placeholder finding)",
                "expected_impact": "Lower p95 latency for repeated reads",
                "tradeoffs": ["cache invalidation complexity", "memory cost"],
                "when_not_to_use": "Low read reuse or strict write-through semantics without cache strategy",
            }
        ]

