from app.models.contracts import LoadProfile, SafetyOverrides


class SafetyPolicy:
    """Starter validation for local-safe load tests."""

    def validate(self, profile: LoadProfile, overrides: SafetyOverrides | None = None) -> list[str]:
        issues: list[str] = []
        if profile.duration_sec > 3600:
            issues.append("duration_sec exceeds local-safe maximum (3600)")
        if profile.concurrency > 2000:
            issues.append("concurrency exceeds starter maximum (2000)")
        if overrides and overrides.max_cpu_pct and overrides.max_cpu_pct > 95:
            issues.append("max_cpu_pct cannot exceed 95")
        return issues

