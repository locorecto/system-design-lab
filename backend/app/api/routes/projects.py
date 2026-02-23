from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


@router.post("/projects")
def create_project(payload: ProjectCreate) -> dict:
    return {
        "project_id": f"prj_{uuid4().hex[:8]}",
        "name": payload.name,
        "description": payload.description,
    }


@router.get("/projects")
def list_projects() -> dict:
    return {"items": []}


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    return {"project_id": project_id, "name": "example-project"}

