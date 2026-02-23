class SandboxRuntimeManager:
    """Backend-agnostic placeholder for process/container sandbox integration."""

    def provision(self, profile: str) -> dict:
        return {"profile": profile, "limits": {"cpu_cores": 2, "memory_mb": 2048}}

    def stop(self, run_id: str, reason: str) -> dict:
        return {"run_id": run_id, "status": "stopped", "reason": reason}

