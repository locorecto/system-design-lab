from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter()


class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None


class RequirementsPayload(BaseModel):
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: dict = Field(default_factory=dict)


@router.post("/projects/{project_id}/scenarios")
def create_scenario(project_id: str, payload: ScenarioCreate) -> dict:
    return {
        "scenario_id": f"scn_{uuid4().hex[:8]}",
        "project_id": project_id,
        "name": payload.name,
        "description": payload.description,
        "status": "draft",
    }


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    return {"scenario_id": scenario_id, "status": "draft"}


@router.put("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, payload: ScenarioCreate) -> dict:
    return {"scenario_id": scenario_id, "name": payload.name, "description": payload.description}


@router.post("/scenarios/{scenario_id}/requirements")
def save_requirements(scenario_id: str, payload: RequirementsPayload) -> dict:
    return {
        "scenario_id": scenario_id,
        "requirement_set_id": f"req_{uuid4().hex[:8]}",
        "functional_count": len(payload.functional_requirements),
    }


@router.post("/scenarios/{scenario_id}/designs:generate")
def generate_design(scenario_id: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "variants": [
            {
                "variant_id": f"var_{uuid4().hex[:8]}",
                "name": "baseline",
                "assumptions": ["Single region", "Read-heavy traffic"],
                "components": ["api", "db", "cache (optional)"],
            }
        ],
    }


@router.get("/scenarios/{scenario_id}/variants")
def list_variants(scenario_id: str) -> dict:
    return {"scenario_id": scenario_id, "items": []}


@router.get("/variants/{variant_id}")
def get_variant(variant_id: str) -> dict:
    return {"variant_id": variant_id, "name": "baseline"}

