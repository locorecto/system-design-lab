from fastapi import FastAPI

from app.api.routes import projects, recommendations, reports, runs, scenarios


app = FastAPI(
    title="System Design Lab API",
    version="0.1.0",
    description="Starter API scaffold for scenario design, load testing, and recommendations.",
)

app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
app.include_router(reports.router, prefix="/api", tags=["reports"])


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

