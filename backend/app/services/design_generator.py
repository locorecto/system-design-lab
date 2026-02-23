from __future__ import annotations

from typing import Any


class DesignGenerator:
    """Generate a runnable synthetic target profile from requirements (MVP)."""

    def generate(self, scenario_id: str, requirements: dict[str, Any]) -> dict[str, Any]:
        frs = [str(item).strip() for item in requirements.get("functional_requirements", []) if str(item).strip()]
        nfr = requirements.get("non_functional_requirements", {}) or {}
        fr_text = " ".join(frs).lower()
        nfr_text = " ".join(f"{k} {v}" for k, v in nfr.items()).lower()

        has_search = ("search" in fr_text) or ("search" in nfr_text)
        has_geo = ("geo" in fr_text) or ("geospatial" in fr_text) or ("location" in fr_text)
        has_feed = "feed" in fr_text
        has_chat = "chat" in fr_text or "message" in fr_text
        write_heavy_hint = any(word in fr_text for word in ["create", "write", "publish", "upload", "message"])

        throughput_rps = self._extract_number(
            nfr,
            keys=["throughput_rps", "rps", "throughput"],
            default=500,
        )
        p95_target_ms = self._extract_number(
            nfr,
            keys=["latency_p95_ms", "p95_ms", "latency"],
            default=200,
        )
        consistency = str(nfr.get("consistency", "eventual")).lower()

        search_ratio = 0.2 if has_search else 0.0
        write_ratio = 0.35 if (write_heavy_hint or has_chat) else 0.2
        if has_feed:
            write_ratio = min(write_ratio, 0.2)
        read_ratio = max(0.0, 1.0 - write_ratio - search_ratio)
        total = read_ratio + write_ratio + search_ratio
        if total <= 0:
            read_ratio, write_ratio, search_ratio = 0.8, 0.2, 0.0
        else:
            read_ratio, write_ratio, search_ratio = [round(x / total, 2) for x in (read_ratio, write_ratio, search_ratio)]
            # Fix rounding drift on the last component.
            search_ratio = round(max(0.0, 1.0 - read_ratio - write_ratio), 2)

        components = ["api-service", "primary-database"]
        assumptions = ["Single region for local sandbox tests", "Synthetic target profile used for generated system execution"]
        if read_ratio >= 0.65:
            components.append("cache-layer (candidate)")
            assumptions.append("Read-heavy workload; cache likely beneficial")
        if has_search:
            components.append("search-index (candidate)")
        if write_ratio >= 0.3:
            components.append("async-queue (candidate)")
        if has_geo:
            components.append("geospatial-index (candidate)")
        if has_chat:
            components.append("websocket-gateway (candidate)")

        consistency_mode = "strong" if "strong" in consistency else "eventual"
        cpu_bias = 1.1 if write_ratio >= 0.3 else 0.9
        if has_search:
            cpu_bias += 0.2
        memory_bias = 1.0 + (0.15 if has_feed else 0) + (0.2 if has_search else 0)

        target_profile = {
            "kind": "synthetic_generated_target",
            "workload": {
                "read_ratio": read_ratio,
                "write_ratio": write_ratio,
                "search_ratio": search_ratio,
            },
            "performance_targets": {
                "throughput_rps": throughput_rps,
                "latency_p95_ms": p95_target_ms,
            },
            "consistency": consistency_mode,
            "simulation_tuning": {
                "cpu_bias": round(cpu_bias, 2),
                "memory_bias": round(memory_bias, 2),
                "queue_sensitivity": 1.2 if p95_target_ms <= 120 else 1.0,
                "error_sensitivity": 1.15 if throughput_rps > 3000 else 1.0,
            },
            "default_run_config": {
                "sandbox_profile": "medium" if throughput_rps <= 2000 else "high",
                "load_profile": {
                    "type": "ramp",
                    "duration_sec": 20,
                    "concurrency": max(20, min(800, int(max(throughput_rps / 4, 50)))),
                    "start_rps": max(10, int(throughput_rps * 0.1)),
                    "end_rps": max(100, int(throughput_rps * 1.2)),
                    "target_rps": int(throughput_rps),
                    "request_mix": {
                        "read": read_ratio,
                        "write": write_ratio,
                        "search": search_ratio,
                    },
                },
                "safety_overrides": {
                    "max_cpu_pct": 90,
                    "max_memory_mb": 1024 if throughput_rps <= 2000 else 2048,
                },
            },
        }

        rationale = (
            f"Generated baseline variant from {len(frs)} functional requirements and NFR targets "
            f"(throughput≈{throughput_rps} rps, p95≈{p95_target_ms} ms, consistency={consistency_mode})."
        )

        return {
            "scenario_id": scenario_id,
            "variants": [
                {
                    "name": "generated-baseline",
                    "assumptions": assumptions,
                    "components": components,
                    "target_profile": target_profile,
                    "rationale": rationale,
                }
            ],
        }

    def _extract_number(self, nfr: dict[str, Any], keys: list[str], default: int) -> int:
        for key in keys:
            if key not in nfr:
                continue
            value = nfr[key]
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                digits = "".join(ch for ch in value if ch.isdigit())
                if digits:
                    return int(digits)
        return default
