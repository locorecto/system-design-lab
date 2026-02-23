class DesignGenerator:
    def generate(self, scenario_id: str) -> dict:
        return {
            "scenario_id": scenario_id,
            "variants": [{"name": "baseline", "components": ["api", "db"]}],
        }

