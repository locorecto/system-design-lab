export type ApiRunCreateRequest = {
  scenario_id: string;
  variant_id: string;
  load_profile: {
    type: "constant" | "ramp" | "spike" | "step" | "soak";
    duration_sec: number;
    concurrency: number;
    request_mix: { read: number; write: number; search?: number };
    target_rps?: number;
    start_rps?: number;
    end_rps?: number;
  };
  sandbox_profile: "low" | "medium" | "high";
  safety_overrides?: {
    max_cpu_pct?: number;
    max_memory_mb?: number;
  };
};

const API_BASE = "http://localhost:8000/api";

export async function createRun(payload: ApiRunCreateRequest): Promise<unknown> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Failed to create run: ${response.status}`);
  }
  return response.json();
}

