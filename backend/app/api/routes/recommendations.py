from fastapi import APIRouter

from app.services.recommendation_engine import RecommendationEngine


router = APIRouter()
engine = RecommendationEngine()


@router.post("/runs/{run_id}/analyze")
def analyze_run(run_id: str) -> dict:
    return {"run_id": run_id, "recommendations": engine.generate_stub(run_id)}


@router.get("/runs/{run_id}/recommendations")
def get_recommendations(run_id: str) -> dict:
    return {"run_id": run_id, "items": engine.generate_stub(run_id)}


@router.post("/recommendations/{recommendation_id}/apply")
def apply_recommendation(recommendation_id: str) -> dict:
    return {
        "recommendation_id": recommendation_id,
        "status": "applied_stub",
        "message": "Create a new architecture variant and rerun test.",
    }

