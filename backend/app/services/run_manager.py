from datetime import datetime, timezone
from uuid import uuid4

from app.core.policies import SafetyPolicy
from app.models.contracts import RunCreateRequest


class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, dict] = {}
        self._policy = SafetyPolicy()

    def create_run(self, payload: RunCreateRequest) -> dict:
        issues = self._policy.validate(payload.load_profile, payload.safety_overrides)
        if issues:
            return {"status": "rejected", "validation_errors": issues}

        run_id = f"run_{uuid4().hex[:8]}"
        record = {
            "run_id": run_id,
            "status": "run_queued",
            "phase": "provisioning",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scenario_id": payload.scenario_id,
            "variant_id": payload.variant_id,
            "sandbox": {"profile": payload.sandbox_profile},
        }
        self._runs[run_id] = record
        return record

    def get_run(self, run_id: str) -> dict:
        return self._runs.get(
            run_id,
            {
                "run_id": run_id,
                "status": "unknown",
                "phase": "unknown",
                "message": "Run not found in starter in-memory store.",
            },
        )

    def stop_run(self, run_id: str) -> dict:
        run = self._runs.setdefault(run_id, {"run_id": run_id})
        run["status"] = "stopped"
        run["phase"] = "terminated"
        run["stop_reason"] = "manual_stop"
        return run

