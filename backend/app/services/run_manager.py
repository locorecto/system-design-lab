from __future__ import annotations

import json
import math
import random
import threading
import time
from typing import Any, Iterator
from uuid import uuid4

from app.core.database import SqliteRepository, utc_now_iso
from app.core.policies import SafetyPolicy
from app.models.contracts import RunCreateRequest
from app.services.sandbox import SandboxRuntimeManager


class RunManager:
    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo
        self._policy = SafetyPolicy()
        self._sandbox = SandboxRuntimeManager()
        self._lock = threading.Lock()
        self._stop_flags: dict[str, threading.Event] = {}
        self._workers: dict[str, threading.Thread] = {}

    def create_run(self, payload: RunCreateRequest) -> dict:
        issues = self._policy.validate(payload.load_profile, payload.safety_overrides)
        if issues:
            return {"status": "rejected", "validation_errors": issues}
        scenario = self._repo.get_scenario(payload.scenario_id)
        if not scenario:
            return {"status": "rejected", "validation_errors": [f"Unknown scenario_id: {payload.scenario_id}"]}
        variant = self._repo.get_variant(payload.variant_id)
        if not variant:
            return {"status": "rejected", "validation_errors": [f"Unknown variant_id: {payload.variant_id}"]}
        if str(variant.get("scenario_id")) != payload.scenario_id:
            return {"status": "rejected", "validation_errors": ["variant_id does not belong to scenario_id"]}

        run_id = f"run_{uuid4().hex[:8]}"
        now = utc_now_iso()
        self._repo.create_run(
            {
                "run_id": run_id,
                "scenario_id": payload.scenario_id,
                "variant_id": payload.variant_id,
                "status": "run_queued",
                "phase": "run_queued",
                "created_at": now,
                "updated_at": now,
                "sandbox_profile": payload.sandbox_profile,
                "sandbox_backend": payload.sandbox_backend,
                "sandbox_limits": {},
                "load_profile": payload.load_profile.model_dump(),
                "safety_overrides": payload.safety_overrides.model_dump() if payload.safety_overrides else None,
            }
        )
        self._emit(run_id, "run.status_changed", {"status": "run_queued", "phase": "run_queued"})
        stop_flag = threading.Event()
        worker = threading.Thread(
            target=self._execute_run,
            args=(run_id, payload.model_dump(mode="python"), stop_flag),
            daemon=True,
            name=f"run-{run_id}",
        )
        with self._lock:
            self._stop_flags[run_id] = stop_flag
            self._workers[run_id] = worker
        worker.start()
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict:
        return self._repo.get_run(run_id) or {"run_id": run_id, "status": "unknown", "phase": "unknown"}

    def stop_run(self, run_id: str) -> dict:
        with self._lock:
            flag = self._stop_flags.get(run_id)
        if flag:
            flag.set()
            self._emit(run_id, "run.warning", {"message": "Manual stop requested."})
        run = self._repo.update_run(run_id, status="stopped", phase="terminated", stop_reason="manual_stop")
        if run:
            self._emit(run_id, "run.status_changed", {"status": "stopped", "phase": "terminated", "stop_reason": "manual_stop"})
            return run
        return {"run_id": run_id, "status": "unknown"}

    def get_metrics(self, run_id: str) -> dict:
        return self._repo.get_metric_series(run_id)

    def get_events(self, run_id: str) -> dict:
        return {"run_id": run_id, "events": self._repo.get_events(run_id)}

    def stream_chunks(self, run_id: str) -> Iterator[str]:
        last_event_id = 0
        last_metric_id = 0
        last_emit = time.monotonic()
        while True:
            run = self.get_run(run_id)
            if run["status"] == "unknown":
                yield self._sse("run.warning", {"message": f"Unknown run {run_id}"})
                break
            for item in self._repo.get_metric_events(run_id, after_id=last_metric_id):
                last_metric_id = max(last_metric_id, int(item["id"]))
                payload = dict(item)
                payload.pop("id", None)
                yield self._sse("metric.aggregate", payload)
                last_emit = time.monotonic()
            for item in self._repo.get_events(run_id, after_id=last_event_id):
                last_event_id = max(last_event_id, int(item["id"]))
                payload = {"run_id": item["run_id"], "timestamp": item["timestamp"], **item["payload"]}
                yield self._sse(item["type"], payload)
                last_emit = time.monotonic()
            if time.monotonic() - last_emit > 2:
                yield ": keepalive\n\n"
                last_emit = time.monotonic()
            if run["status"] in {"completed", "failed", "stopped", "throttled"}:
                break
            time.sleep(0.5)

    def _execute_run(self, run_id: str, payload: dict[str, Any], stop_flag: threading.Event) -> None:
        sandbox_info: dict[str, Any] = {}
        try:
            self._transition(run_id, "run_provisioning", "provisioning")
            self._emit(run_id, "run.status_changed", {"status": "run_provisioning", "phase": "provisioning"})
            backend_name = str(payload.get("sandbox_backend") or "process")
            sandbox_info = self._sandbox.provision(run_id, payload["sandbox_profile"], backend_name=backend_name)
            self._repo.update_run(run_id, sandbox_backend=sandbox_info["backend"], sandbox_limits=sandbox_info["limits"])
            variant = self._repo.get_variant(payload["variant_id"]) or {}
            target_profile = (variant.get("target_profile") or {})
            self._sandbox.start_target(run_id, target_spec=target_profile)
            self._sandbox.start_load_generator(run_id, load_spec={"load_profile": payload["load_profile"]})

            self._transition(run_id, "running", "load_execution")
            self._emit(run_id, "run.status_changed", {"status": "running", "phase": "load_execution"})
            profile = payload["load_profile"]
            sample_count = max(6, min(int(profile.get("duration_sec", 60)), 90))
            safety = payload.get("safety_overrides") or {}
            cpu_limit = float(safety.get("max_cpu_pct") or 90)
            mem_limit = float(safety.get("max_memory_mb") or sandbox_info["limits"].get("memory_mb", 1024))
            for step in range(sample_count):
                if stop_flag.is_set():
                    self._transition(run_id, "stopped", "terminated", "manual_stop")
                    self._emit(run_id, "run.status_changed", {"status": "stopped", "phase": "terminated", "stop_reason": "manual_stop"})
                    return
                sample = self._simulate_sample(step, sample_count, profile, sandbox_info["limits"], target_profile)
                self._repo.append_metric(run_id, sample)
                if sample["cpu_pct"] >= cpu_limit or sample["memory_mb"] >= mem_limit:
                    self._emit(
                        run_id,
                        "run.warning",
                        {"message": "Safety threshold exceeded.", "cpu_pct": sample["cpu_pct"], "memory_mb": sample["memory_mb"]},
                    )
                    self._transition(run_id, "throttled", "safety_stop", "safety_threshold_exceeded")
                    self._emit(run_id, "run.throttled", {"status": "throttled", "phase": "safety_stop", "stop_reason": "safety_threshold_exceeded"})
                    return
                time.sleep(0.5)
            self._transition(run_id, "completed", "completed")
            self._emit(run_id, "run.completed", {"status": "completed", "phase": "completed"})
            self._emit(run_id, "run.status_changed", {"status": "completed", "phase": "completed"})
        except Exception as exc:  # pragma: no cover
            self._transition(run_id, "failed", "failed", "exception")
            self._emit(run_id, "run.warning", {"message": f"Run failed: {exc.__class__.__name__}: {exc}"})
            self._emit(run_id, "run.status_changed", {"status": "failed", "phase": "failed"})
        finally:
            try:
                self._sandbox.cleanup(run_id)
            except Exception:
                pass
            with self._lock:
                self._stop_flags.pop(run_id, None)
                self._workers.pop(run_id, None)

    def _transition(self, run_id: str, status: str, phase: str, stop_reason: str | None = None) -> None:
        self._repo.update_run(run_id, status=status, phase=phase, stop_reason=stop_reason)

    def _emit(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self._repo.append_event(run_id, event_type, payload)

    def _desired_rps(self, step: int, sample_count: int, profile: dict[str, Any]) -> float:
        kind = profile.get("type", "constant")
        if kind == "ramp":
            start = float(profile.get("start_rps") or 20)
            end = float(profile.get("end_rps") or 500)
            t = step / max(1, sample_count - 1)
            return start + (end - start) * t
        if kind == "spike":
            base = float(profile.get("target_rps") or 100)
            center = sample_count // 2
            return base * 3 if abs(step - center) <= max(1, sample_count // 12) else base
        if kind == "step":
            start = float(profile.get("start_rps") or 50)
            end = float(profile.get("end_rps") or 500)
            p = step / max(1, sample_count)
            return start if p < 0.33 else ((start + end) / 2 if p < 0.66 else end)
        if kind == "soak":
            base = float(profile.get("target_rps") or 150)
            return base + math.sin(step / 4) * 8
        return float(profile.get("target_rps") or profile.get("start_rps") or 100)

    def _simulate_sample(
        self,
        step: int,
        sample_count: int,
        profile: dict[str, Any],
        limits: dict[str, Any],
        target_profile: dict[str, Any],
    ) -> dict[str, Any]:
        desired_rps = self._desired_rps(step, sample_count, profile)
        capacity = float(limits.get("nominal_rps_capacity") or 500)
        memory_limit = float(limits.get("memory_mb") or 1024)
        concurrency = float(profile.get("concurrency") or 10)
        tuning = (target_profile.get("simulation_tuning") or {})
        cpu_bias = float(tuning.get("cpu_bias") or 1.0)
        memory_bias = float(tuning.get("memory_bias") or 1.0)
        queue_sensitivity = float(tuning.get("queue_sensitivity") or 1.0)
        error_sensitivity = float(tuning.get("error_sensitivity") or 1.0)
        workload = (target_profile.get("workload") or {})
        search_ratio = float(workload.get("search_ratio") or 0.0)
        write_ratio = float(workload.get("write_ratio") or 0.0)
        load_factor = desired_rps / max(capacity, 1)
        cpu_pct = min(100.0, ((load_factor * 68) + (concurrency / 30) + search_ratio * 10 + write_ratio * 6) * cpu_bias + random.uniform(-2.5, 4))
        memory_mb = min(
            memory_limit * 1.2,
            (memory_limit * (0.25 + 0.5 * min(1.2, load_factor)) + concurrency * 2.5 + search_ratio * 70) * memory_bias + random.uniform(-12, 15),
        )
        p50 = 18 + load_factor * 30 + random.uniform(0, 8)
        p95 = p50 + 30 + max(0.0, (cpu_pct - 70) * 2.7) * queue_sensitivity + random.uniform(5, 15)
        p99 = p95 + 20 + max(0.0, (cpu_pct - 80) * 3.2) + random.uniform(5, 20)
        error_rate = min(0.35, (max(0.0, load_factor - 1) * 0.08 + max(0.0, cpu_pct - 92) * 0.003 + random.uniform(0, 0.004)) * error_sensitivity)
        achieved_rps = max(0.0, desired_rps * (1 - min(error_rate * 1.5, 0.5)))
        return {
            "timestamp": utc_now_iso(),
            "rps": round(achieved_rps, 2),
            "latency_ms": {"p50": round(p50, 2), "p95": round(p95, 2), "p99": round(p99, 2)},
            "error_rate": round(error_rate, 4),
            "cpu_pct": round(max(cpu_pct, 1), 2),
            "memory_mb": round(max(memory_mb, 64), 2),
        }

    def _sse(self, event_name: str, payload: dict[str, Any]) -> str:
        return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
