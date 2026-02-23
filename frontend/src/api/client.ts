export type ApiRunCreateRequest = {
  scenario_id: string;
  variant_id: string;
  sandbox_backend?: "process" | "container";
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

export type ApiRunRecord = {
  run_id: string;
  status: string;
  phase: string;
  stop_reason?: string | null;
  sandbox?: {
    profile: string;
    backend?: string | null;
    limits?: { cpu_cores?: number; memory_mb?: number };
  };
};

export type MetricAggregateEvent = {
  type: "metric.aggregate";
  run_id: string;
  timestamp: string;
  metrics: {
    rps: number;
    error_rate: number;
    cpu_pct: number;
    memory_mb: number;
    latency_ms: {
      p50: number;
      p95: number;
      p99: number;
    };
  };
};

export type Recommendation = {
  recommendation_id: string;
  technology: string;
  category: string;
  priority_score?: number;
  rank?: number;
  problem_observed: string;
  expected_impact: string;
  tradeoffs: string[];
  consistency_implications?: string;
  when_not_to_use?: string;
};

export type ScenarioRecord = {
  scenario_id: string;
  project_id: string;
  name: string;
  description?: string | null;
  status: string;
  latest_requirement_set_id?: string | null;
};

export type GeneratedVariant = {
  variant_id: string;
  scenario_id: string;
  name: string;
  assumptions: string[];
  components: string[];
  rationale?: string | null;
  target_profile?: {
    kind?: string;
    workload?: {
      read_ratio?: number;
      write_ratio?: number;
      search_ratio?: number;
    };
    default_run_config?: {
      sandbox_backend?: "process" | "container";
      sandbox_profile?: "low" | "medium" | "high";
      load_profile?: Partial<ApiRunCreateRequest["load_profile"]>;
      safety_overrides?: {
        max_cpu_pct?: number;
        max_memory_mb?: number;
      };
    };
  };
};

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000/api";

export async function createRun(payload: ApiRunCreateRequest): Promise<ApiRunRecord | { status: "rejected"; validation_errors: string[] }> {
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

export async function getRun(runId: string): Promise<ApiRunRecord> {
  const response = await fetch(`${API_BASE}/runs/${runId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch run: ${response.status}`);
  }
  return response.json();
}

export async function stopRun(runId: string): Promise<ApiRunRecord> {
  const response = await fetch(`${API_BASE}/runs/${runId}/stop`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to stop run: ${response.status}`);
  }
  return response.json();
}

export async function getRunRecommendations(runId: string): Promise<Recommendation[]> {
  const response = await fetch(`${API_BASE}/runs/${runId}/recommendations`);
  if (!response.ok) {
    throw new Error(`Failed to fetch recommendations: ${response.status}`);
  }
  const body = (await response.json()) as { items: Recommendation[] };
  return body.items;
}

export async function analyzeRun(runId: string): Promise<Recommendation[]> {
  const response = await fetch(`${API_BASE}/runs/${runId}/analyze`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to analyze run: ${response.status}`);
  }
  const body = (await response.json()) as { recommendations: Recommendation[] };
  return body.recommendations;
}

export function runStreamUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/stream`;
}

export async function createScenario(
  projectId: string,
  payload: { name: string; description?: string }
): Promise<ScenarioRecord> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/scenarios`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`Failed to create scenario: ${response.status}`);
  }
  return response.json();
}

export async function saveScenarioRequirements(
  scenarioId: string,
  payload: {
    functional_requirements: string[];
    non_functional_requirements: Record<string, unknown>;
  }
): Promise<{ scenario_id: string; requirement_set_id: string }> {
  const response = await fetch(`${API_BASE}/scenarios/${scenarioId}/requirements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`Failed to save requirements: ${response.status}`);
  }
  return response.json();
}

export async function generateScenarioDesign(
  scenarioId: string
): Promise<{ scenario_id: string; variants: GeneratedVariant[]; error?: string }> {
  const response = await fetch(`${API_BASE}/scenarios/${scenarioId}/designs:generate`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(`Failed to generate design: ${response.status}`);
  }
  return response.json();
}
