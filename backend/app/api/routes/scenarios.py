from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import design_generator, repo
from app.core.database import utc_now_iso

router = APIRouter()


class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None


class RequirementsPayload(BaseModel):
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: dict = Field(default_factory=dict)


@router.post("/projects/{project_id}/scenarios")
def create_scenario(project_id: str, payload: ScenarioCreate) -> dict:
    now = utc_now_iso()
    return repo.create_scenario(
        {
            "scenario_id": f"scn_{uuid4().hex[:8]}",
            "project_id": project_id,
            "name": payload.name,
            "description": payload.description,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "latest_requirement_set_id": None,
        }
    )


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    return repo.get_scenario(scenario_id) or {"scenario_id": scenario_id, "status": "unknown"}


@router.put("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, payload: ScenarioCreate) -> dict:
    return repo.update_scenario(scenario_id, name=payload.name, description=payload.description) or {
        "scenario_id": scenario_id,
        "status": "unknown",
    }


@router.post("/scenarios/{scenario_id}/requirements")
def save_requirements(scenario_id: str, payload: RequirementsPayload) -> dict:
    row = repo.create_requirement_set(
        {
            "requirement_set_id": f"req_{uuid4().hex[:8]}",
            "scenario_id": scenario_id,
            "created_at": utc_now_iso(),
            "functional_requirements": payload.functional_requirements,
            "non_functional_requirements": payload.non_functional_requirements,
        }
    )
    return {
        "scenario_id": scenario_id,
        "requirement_set_id": row["requirement_set_id"],
        "functional_count": len(row["functional_requirements"]),
        "non_functional_keys": sorted((row["non_functional_requirements"] or {}).keys()),
    }


@router.post("/scenarios/{scenario_id}/designs:generate")
def generate_design(scenario_id: str) -> dict:
    requirements = repo.get_latest_requirement_set_for_scenario(scenario_id)
    if not requirements:
        return {"scenario_id": scenario_id, "variants": [], "error": "No requirements found for scenario"}
    generated = design_generator.generate(scenario_id, requirements)
    saved_variants: list[dict] = []
    for variant in generated["variants"]:
        saved_variants.append(
            repo.create_architecture_variant(
                {
                    "variant_id": f"var_{uuid4().hex[:8]}",
                    "scenario_id": scenario_id,
                    "name": variant["name"],
                    "created_at": utc_now_iso(),
                    "assumptions": variant.get("assumptions", []),
                    "components": variant.get("components", []),
                    "target_profile": variant.get("target_profile", {}),
                    "rationale": variant.get("rationale"),
                }
            )
        )
    return {"scenario_id": scenario_id, "variants": saved_variants}


@router.get("/scenarios/{scenario_id}/variants")
def list_variants(scenario_id: str) -> dict:
    return {"scenario_id": scenario_id, "items": repo.list_variants(scenario_id)}


@router.get("/variants/{variant_id}")
def get_variant(variant_id: str) -> dict:
    return repo.get_variant(variant_id) or {"variant_id": variant_id, "status": "unknown"}
