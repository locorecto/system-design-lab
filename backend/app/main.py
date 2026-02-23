from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import repo
from app.api.routes import projects, recommendations, reports, runs, scenarios


app = FastAPI(
    title="System Design Lab API",
    version="0.1.0",
    description="Starter API scaffold for scenario design, load testing, and recommendations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:15174",
        "http://127.0.0.1:15174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
app.include_router(reports.router, prefix="/api", tags=["reports"])


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    repo.init_schema()
