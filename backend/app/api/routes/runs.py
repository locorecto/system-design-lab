from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import run_manager
from app.models.contracts import RunCreateRequest


router = APIRouter()


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
    return run_manager.get_metrics(run_id)


@router.get("/runs/{run_id}/events")
def get_run_events(run_id: str) -> dict:
    return run_manager.get_events(run_id)


@router.get("/runs/{run_id}/stream")
def stream_run(run_id: str) -> StreamingResponse:
    return StreamingResponse(run_manager.stream_chunks(run_id), media_type="text/event-stream")
