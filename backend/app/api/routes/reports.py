from fastapi import APIRouter


router = APIRouter()


@router.get("/scenarios/{scenario_id}/comparisons")
def get_comparisons(scenario_id: str) -> dict:
    return {"scenario_id": scenario_id, "items": []}


@router.get("/reports/{report_id}")
def get_report(report_id: str) -> dict:
    return {"report_id": report_id, "status": "not_implemented"}

