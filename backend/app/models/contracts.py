from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RequestMix(BaseModel):
    read: float = 1.0
    write: float = 0.0
    search: float = 0.0

    @model_validator(mode="after")
    def validate_total(self) -> "RequestMix":
        total = self.read + self.write + self.search
        if abs(total - 1.0) > 0.001:
            raise ValueError("request_mix weights must sum to 1.0")
        return self


class LoadProfile(BaseModel):
    type: Literal["constant", "ramp", "spike", "step", "soak"] = "constant"
    duration_sec: int = Field(default=60, ge=1)
    concurrency: int = Field(default=10, ge=1)
    request_mix: RequestMix = Field(default_factory=RequestMix)
    target_rps: int | None = Field(default=None, ge=1)
    start_rps: int | None = Field(default=None, ge=1)
    end_rps: int | None = Field(default=None, ge=1)


class SafetyOverrides(BaseModel):
    max_cpu_pct: int | None = Field(default=None, ge=1, le=100)
    max_memory_mb: int | None = Field(default=None, ge=128)


class RunCreateRequest(BaseModel):
    scenario_id: str
    variant_id: str
    load_profile: LoadProfile
    sandbox_backend: Literal["process", "container"] = "process"
    sandbox_profile: Literal["low", "medium", "high"] = "medium"
    safety_overrides: SafetyOverrides | None = None


class RunRecord(BaseModel):
    run_id: str
    scenario_id: str
    variant_id: str
    status: str
    phase: str
