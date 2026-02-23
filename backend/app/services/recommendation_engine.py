from __future__ import annotations

from typing import Any

from app.core.database import SqliteRepository


class RecommendationEngine:
    """Rule-based, metric-driven recommendations for MVP."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def analyze_run(self, run_id: str) -> list[dict[str, Any]]:
        run = self._repo.get_run(run_id)
        if not run:
            return []
        summary = self._repo.summarize_run_metrics(run_id)
        if summary.get("sample_count", 0) == 0:
            return []

        request_mix = (run.get("load_profile", {}).get("request_mix") or {})
        read_ratio = float(request_mix.get("read", 0.0) or 0.0)
        write_ratio = float(request_mix.get("write", 0.0) or 0.0)
        search_ratio = float(request_mix.get("search", 0.0) or 0.0)
        limits = (run.get("sandbox", {}).get("limits") or {})
        mem_limit = float(limits.get("memory_mb") or 0)
        mem_pressure = float(summary["max_memory_mb"]) / mem_limit if mem_limit else 0.0

        recs: list[dict[str, Any]] = []
        if summary["max_latency_p95_ms"] > 180 and read_ratio >= 0.6:
            recs.append(self._make(run_id, "redis", "Redis", "caching", 95,
                                   f"High p95 latency ({summary['max_latency_p95_ms']:.0f}ms) on read-heavy traffic.",
                                   "Cache hot reads to reduce DB load and tail latency.",
                                   ["cache invalidation complexity", "memory cost"],
                                   "Low cache hit rate or highly write-heavy traffic.",
                                   "May introduce stale reads depending on TTL/invalidation."))
        if (summary["max_cpu_pct"] > 85 or summary["avg_cpu_pct"] > 75) and write_ratio >= 0.2:
            recs.append(self._make(run_id, "kafka", "Kafka", "async-processing", 90,
                                   f"CPU saturation observed (max {summary['max_cpu_pct']:.0f}%).",
                                   "Move non-critical write side effects to async consumers.",
                                   ["operational overhead", "eventual consistency"],
                                   "Strict synchronous workflows that cannot defer work.",
                                   "Introduces eventual consistency across producer/consumer boundaries."))
        if summary["max_latency_p95_ms"] > 220 and search_ratio >= 0.15:
            recs.append(self._make(run_id, "elastic", "Elasticsearch", "search-indexing", 85,
                                   "Search traffic contributes to high tail latency.",
                                   "Offload text/search queries from transactional DB.",
                                   ["index lag", "cluster operations", "data duplication"],
                                   "Simple indexed lookups already perform well in the primary DB.",
                                   "Search index is typically eventually consistent."))
        if summary["max_error_rate"] > 0.02 or summary["max_cpu_pct"] > 90:
            recs.append(self._make(run_id, "gateway", "API Gateway + Rate Limiting", "traffic-protection", 80,
                                   f"Error rate increases under load (max {summary['max_error_rate']:.2%}).",
                                   "Protect downstream services and shed excess load predictably.",
                                   ["extra hop", "policy tuning complexity"],
                                   "Low-traffic internal-only systems.",
                                   "No direct data consistency change; affects request admission behavior."))
        if mem_pressure > 0.8:
            recs.append(self._make(run_id, "memory", "Selective Response Caching", "memory-pressure", 70,
                                   f"Memory pressure is high ({mem_pressure:.0%} of sandbox limit).",
                                   "Reduce repeated in-process allocations and expensive recomputation.",
                                   ["cache eviction tuning", "complexity"],
                                   "If memory growth is due to leaks; fix leaks first.",
                                   "Cached content can become stale without invalidation."))
        if not recs:
            recs.append(self._make(run_id, "db-index", "Database Index Tuning", "database-optimization", 60,
                                   "No critical bottleneck detected; optimize query plans/indexes first.",
                                   "Improve p95 without adding distributed infrastructure.",
                                   ["write amplification", "index maintenance"],
                                   "If latency is dominated by external dependencies.",
                                   "No consistency model change."))

        recs.sort(key=lambda r: r["priority_score"], reverse=True)
        for i, item in enumerate(recs, start=1):
            item["rank"] = i
        self._repo.replace_recommendations(run_id, recs)
        return recs

    def get_recommendations(self, run_id: str) -> list[dict[str, Any]]:
        existing = self._repo.get_recommendations(run_id)
        return existing or self.analyze_run(run_id)

    def _make(
        self,
        run_id: str,
        slug: str,
        technology: str,
        category: str,
        score: int,
        problem: str,
        impact: str,
        tradeoffs: list[str],
        when_not: str,
        consistency: str,
    ) -> dict[str, Any]:
        return {
            "recommendation_id": f"rec_{run_id}_{slug}",
            "technology": technology,
            "category": category,
            "priority_score": score,
            "problem_observed": problem,
            "expected_impact": impact,
            "tradeoffs": tradeoffs,
            "consistency_implications": consistency,
            "when_not_to_use": when_not,
        }
