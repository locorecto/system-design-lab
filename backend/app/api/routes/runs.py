from uuid import uuid4

from fastapi import APIRouter

from app.models.contracts import RunCreateRequest
from app.services.run_manager import RunManager


router = APIRouter()
run_manager = RunManager()


@router.post("/runs")
def create_run(payload: RunCreateRequest) -> dict:
    return run_manager.create_run(payload)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    return run_manager.get_run(run_id)


@router.post("/runs/{run_id}/stop")
def stop_run(run_id: str) -> dict:
    return run_manager.stop_run(run_id)


@router.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "series": [
            {"name": "rps", "points": []},
            {"name": "latency_p95_ms", "points": []},
        ],
    }


@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str) -> dict:
    return {"run_id": run_id, "events": []}


@router.get("/runs/{run_id}/stream")
def stream_hint(run_id: str) -> dict:
    # Placeholder until WebSocket/SSE is implemented.
    return {"run_id": run_id, "transport": "todo", "endpoint": f"/api/runs/{run_id}/stream"}

