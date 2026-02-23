import { useEffect, useMemo, useRef, useState } from "react";

import { analyzeRun, createRun, getRun, runStreamUrl, stopRun, type MetricAggregateEvent } from "../../api/client";
import { subscribeGeneratedScenario } from "../scenarios/scenarioEvents";
import { publishRunLifecycle } from "./runEvents";

type MetricState = {
  rps: number[];
  p95: number[];
  cpu: number[];
  memory: number[];
  errorRate: number[];
};

type RunConfig = {
  scenarioId: string;
  variantId: string;
  sandboxBackend: "process" | "container";
  sandboxProfile: "low" | "medium" | "high";
  profileType: "constant" | "ramp" | "spike" | "step" | "soak";
  durationSec: number;
  concurrency: number;
  targetRps: number;
  startRps: number;
  endRps: number;
  readRatio: number;
  writeRatio: number;
  searchRatio: number;
  maxCpuPct: number;
  maxMemoryMb: number;
};

const HISTORY_LIMIT = 40;
const STORAGE_KEY = "system-design-lab:run-config";

const DEFAULT_CONFIG: RunConfig = {
  scenarioId: "scn_demo",
  variantId: "var_baseline",
  sandboxBackend: "process",
  sandboxProfile: "medium",
  profileType: "ramp",
  durationSec: 20,
  concurrency: 200,
  targetRps: 300,
  startRps: 50,
  endRps: 1200,
  readRatio: 0.75,
  writeRatio: 0.2,
  searchRatio: 0.05,
  maxCpuPct: 90,
  maxMemoryMb: 1024
};

export function RunDashboard() {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [phase, setPhase] = useState("idle");
  const [warning, setWarning] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [config, setConfig] = useState<RunConfig>(loadConfig);
  const [metrics, setMetrics] = useState<MetricState>({ rps: [], p95: [], cpu: [], memory: [], errorRate: [] });
  const sourceRef = useRef<EventSource | null>(null);
  const lastAnalyzedRunRef = useRef<string | null>(null);

  const latest = useMemo(
    () => ({
      rps: last(metrics.rps) ?? 0,
      p95: last(metrics.p95),
      errorRate: last(metrics.errorRate) ?? 0,
      cpu: last(metrics.cpu) ?? 0,
      memory: last(metrics.memory) ?? 0
    }),
    [metrics]
  );

  const requestMixTotal = config.readRatio + config.writeRatio + config.searchRatio;
  const canStart = !isBusy && !isActiveStatus(status);
  const canStop = Boolean(runId) && isActiveStatus(status);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch {
      // ignore localStorage unavailability
    }
  }, [config]);

  useEffect(() => {
    return subscribeGeneratedScenario(({ scenarioId, variant }) => {
      const defaults = variant.target_profile?.default_run_config;
      const workload = variant.target_profile?.workload;
      setConfig((prev) => ({
        ...prev,
        scenarioId,
        variantId: variant.variant_id,
        sandboxProfile: defaults?.sandbox_profile ?? prev.sandboxProfile,
        sandboxBackend: defaults?.sandbox_backend ?? prev.sandboxBackend,
        profileType: (defaults?.load_profile?.type as RunConfig["profileType"] | undefined) ?? prev.profileType,
        durationSec: numberOr(prev.durationSec, defaults?.load_profile?.duration_sec),
        concurrency: numberOr(prev.concurrency, defaults?.load_profile?.concurrency),
        targetRps: numberOr(prev.targetRps, defaults?.load_profile?.target_rps),
        startRps: numberOr(prev.startRps, defaults?.load_profile?.start_rps),
        endRps: numberOr(prev.endRps, defaults?.load_profile?.end_rps),
        readRatio: numberOr(prev.readRatio, workload?.read_ratio),
        writeRatio: numberOr(prev.writeRatio, workload?.write_ratio),
        searchRatio: numberOr(prev.searchRatio, workload?.search_ratio),
        maxCpuPct: numberOr(prev.maxCpuPct, defaults?.safety_overrides?.max_cpu_pct),
        maxMemoryMb: numberOr(prev.maxMemoryMb, defaults?.safety_overrides?.max_memory_mb)
      }));
      setWarning(null);
    });
  }, []);

  async function startRun() {
    if (Math.abs(requestMixTotal - 1) > 0.001) {
      setWarning(`Request mix must sum to 1.0 (current: ${requestMixTotal.toFixed(2)})`);
      return;
    }

    setIsBusy(true);
    setWarning(null);
    setMetrics({ rps: [], p95: [], cpu: [], memory: [], errorRate: [] });
    lastAnalyzedRunRef.current = null;

    try {
      const result = await createRun({
        scenario_id: config.scenarioId,
        variant_id: config.variantId,
        sandbox_backend: config.sandboxBackend,
        sandbox_profile: config.sandboxProfile,
        load_profile: {
          type: config.profileType,
          duration_sec: config.durationSec,
          concurrency: config.concurrency,
          request_mix: { read: config.readRatio, write: config.writeRatio, search: config.searchRatio },
          target_rps: config.profileType === "constant" || config.profileType === "spike" || config.profileType === "soak" ? config.targetRps : undefined,
          start_rps: config.profileType === "ramp" || config.profileType === "step" ? config.startRps : undefined,
          end_rps: config.profileType === "ramp" || config.profileType === "step" ? config.endRps : undefined
        },
        safety_overrides: { max_cpu_pct: config.maxCpuPct, max_memory_mb: config.maxMemoryMb }
      });

      if ("status" in result && result.status === "rejected") {
        setWarning(result.validation_errors.join(", "));
        return;
      }

      setRunId(result.run_id);
      setStatus(result.status);
      setPhase(result.phase);
      publishRunLifecycle({ runId: result.run_id, status: result.status, phase: result.phase });
    } catch (error) {
      setWarning(error instanceof Error ? error.message : "Failed to start run");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleStopRun() {
    if (!runId) {
      return;
    }
    setIsBusy(true);
    try {
      const result = await stopRun(runId);
      setStatus(result.status);
      setPhase(result.phase);
      publishRunLifecycle({ runId, status: result.status, phase: result.phase });
    } catch (error) {
      setWarning(error instanceof Error ? error.message : "Failed to stop run");
    } finally {
      setIsBusy(false);
    }
  }

  async function maybeAnalyzeTerminalRun(targetRunId: string, nextStatus: string, nextPhase: string) {
    publishRunLifecycle({ runId: targetRunId, status: nextStatus, phase: nextPhase });
    if (!["completed", "throttled", "failed", "stopped"].includes(nextStatus)) {
      return;
    }
    if (lastAnalyzedRunRef.current === `${targetRunId}:${nextStatus}`) {
      return;
    }
    lastAnalyzedRunRef.current = `${targetRunId}:${nextStatus}`;
    try {
      await analyzeRun(targetRunId);
      const latestRun = await getRun(targetRunId);
      setStatus(latestRun.status);
      setPhase(latestRun.phase);
    } catch {
      // keep streamed state
    }
  }

  useEffect(() => {
    if (!runId) {
      return;
    }

    sourceRef.current?.close();
    const source = new EventSource(runStreamUrl(runId));
    sourceRef.current = source;

    source.addEventListener("metric.aggregate", (raw) => {
      const evt = JSON.parse((raw as MessageEvent).data) as MetricAggregateEvent;
      setMetrics((prev) => ({
        rps: append(prev.rps, evt.metrics.rps),
        p95: append(prev.p95, evt.metrics.latency_ms.p95),
        cpu: append(prev.cpu, evt.metrics.cpu_pct),
        memory: append(prev.memory, evt.metrics.memory_mb),
        errorRate: append(prev.errorRate, evt.metrics.error_rate * 100)
      }));
    });

    source.addEventListener("run.status_changed", (raw) => {
      const payload = JSON.parse((raw as MessageEvent).data) as { status?: string; phase?: string; stop_reason?: string };
      const nextStatus = payload.status ?? "unknown";
      const nextPhase = payload.phase ?? "unknown";
      setStatus(nextStatus);
      setPhase(nextPhase);
      void maybeAnalyzeTerminalRun(runId, nextStatus, nextPhase);
    });

    source.addEventListener("run.warning", (raw) => {
      const payload = JSON.parse((raw as MessageEvent).data) as { message?: string };
      if (payload.message) {
        setWarning(payload.message);
      }
    });

    source.addEventListener("run.throttled", () => {
      setStatus("throttled");
      setPhase("safety_stop");
      void maybeAnalyzeTerminalRun(runId, "throttled", "safety_stop");
    });

    source.addEventListener("run.completed", () => {
      setStatus("completed");
      setPhase("completed");
      void maybeAnalyzeTerminalRun(runId, "completed", "completed");
    });

    source.onerror = () => {
      // Stream may close normally on terminal state.
    };

    return () => source.close();
  }, [runId]);

  return (
    <div className="panel">
      <div className="toolbar">
        <strong>Live Monitoring</strong>
        <div className="toolbar-actions">
          <button type="button" onClick={() => void startRun()} disabled={!canStart}>
            {isBusy && !canStop ? "Starting..." : "Start Run"}
          </button>
          <button type="button" className="secondary-btn" onClick={() => void handleStopRun()} disabled={!canStop || isBusy}>
            {isBusy && canStop ? "Stopping..." : "Stop Run"}
          </button>
        </div>
      </div>

      <RunConfigEditor config={config} onChange={setConfig} requestMixTotal={requestMixTotal} />

      <div className="metric-grid">
        <MetricCard label="RPS" value={latest.rps.toFixed(0)} />
        <MetricCard label="P95 Latency" value={latest.p95 ? `${latest.p95.toFixed(0)} ms` : "N/A"} />
        <MetricCard label="Error Rate" value={`${latest.errorRate.toFixed(2)}%`} />
        <MetricCard label="CPU" value={`${latest.cpu.toFixed(0)}%`} />
        <MetricCard label="Memory" value={`${latest.memory.toFixed(0)} MB`} />
        <MetricCard label="Status" value={`${status} / ${phase}`} />
      </div>

      <div className="chart-grid">
        <MiniChart title="RPS" data={metrics.rps} color="#1f7a8c" />
        <MiniChart title="P95 (ms)" data={metrics.p95} color="#c85f2f" />
        <MiniChart title="CPU %" data={metrics.cpu} color="#9c6644" />
        <MiniChart title="Memory (MB)" data={metrics.memory} color="#588157" />
      </div>

      {runId ? <p className="muted">Active run: `{runId}`</p> : null}
      {warning ? <p className="warning-text">Warning: {warning}</p> : null}
      <p className="muted" style={{ marginTop: 8 }}>
        SSE stream: `GET /api/runs/{'{run_id}'}/stream` (metrics + lifecycle events)
      </p>
    </div>
  );
}

function loadConfig(): RunConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_CONFIG;
    }
    const parsed = JSON.parse(raw) as Partial<RunConfig>;
    return { ...DEFAULT_CONFIG, ...parsed };
  } catch {
    return DEFAULT_CONFIG;
  }
}

function isActiveStatus(status: string): boolean {
  return ["run_queued", "run_provisioning", "running"].includes(status);
}

function append(series: number[], value: number): number[] {
  const next = [...series, value];
  return next.length > HISTORY_LIMIT ? next.slice(next.length - HISTORY_LIMIT) : next;
}

function last(series: number[]): number | undefined {
  return series.length ? series[series.length - 1] : undefined;
}

function RunConfigEditor({
  config,
  onChange,
  requestMixTotal
}: {
  config: RunConfig;
  onChange: (next: RunConfig) => void;
  requestMixTotal: number;
}) {
  function set<K extends keyof RunConfig>(key: K, value: RunConfig[K]) {
    onChange({ ...config, [key]: value });
  }

  return (
    <div className="config-panel">
      <div className="config-grid">
        <label>
          Scenario ID
          <input value={config.scenarioId} onChange={(e) => set("scenarioId", e.target.value)} />
        </label>
        <label>
          Variant ID
          <input value={config.variantId} onChange={(e) => set("variantId", e.target.value)} />
        </label>
        <label>
          Sandbox Backend
          <select value={config.sandboxBackend} onChange={(e) => set("sandboxBackend", e.target.value as RunConfig["sandboxBackend"])}>
            <option value="process">process</option>
            <option value="container">container</option>
          </select>
        </label>
        <label>
          Sandbox
          <select value={config.sandboxProfile} onChange={(e) => set("sandboxProfile", e.target.value as RunConfig["sandboxProfile"])}>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </label>
        <label>
          Profile Type
          <select value={config.profileType} onChange={(e) => set("profileType", e.target.value as RunConfig["profileType"])}>
            <option value="constant">constant</option>
            <option value="ramp">ramp</option>
            <option value="spike">spike</option>
            <option value="step">step</option>
            <option value="soak">soak</option>
          </select>
        </label>

        <label>
          Duration (sec)
          <input type="number" min={1} value={config.durationSec} onChange={(e) => set("durationSec", toInt(e.target.value, 1))} />
        </label>
        <label>
          Concurrency
          <input type="number" min={1} value={config.concurrency} onChange={(e) => set("concurrency", toInt(e.target.value, 1))} />
        </label>
        <label>
          Target RPS
          <input type="number" min={1} value={config.targetRps} onChange={(e) => set("targetRps", toInt(e.target.value, 1))} />
        </label>
        <label>
          Start RPS
          <input type="number" min={1} value={config.startRps} onChange={(e) => set("startRps", toInt(e.target.value, 1))} />
        </label>
        <label>
          End RPS
          <input type="number" min={1} value={config.endRps} onChange={(e) => set("endRps", toInt(e.target.value, 1))} />
        </label>
        <label>
          Max CPU %
          <input type="number" min={1} max={95} value={config.maxCpuPct} onChange={(e) => set("maxCpuPct", toInt(e.target.value, 1))} />
        </label>
        <label>
          Max Memory (MB)
          <input type="number" min={128} value={config.maxMemoryMb} onChange={(e) => set("maxMemoryMb", toInt(e.target.value, 128))} />
        </label>
      </div>

      <div className="ratio-grid">
        <label>
          Read Ratio
          <input type="number" step="0.05" min={0} max={1} value={config.readRatio} onChange={(e) => set("readRatio", toFloat(e.target.value, 0))} />
        </label>
        <label>
          Write Ratio
          <input type="number" step="0.05" min={0} max={1} value={config.writeRatio} onChange={(e) => set("writeRatio", toFloat(e.target.value, 0))} />
        </label>
        <label>
          Search Ratio
          <input type="number" step="0.05" min={0} max={1} value={config.searchRatio} onChange={(e) => set("searchRatio", toFloat(e.target.value, 0))} />
        </label>
      </div>
      <p className={`muted ${Math.abs(requestMixTotal - 1) > 0.001 ? "warning-text" : ""}`}>Request mix sum: {requestMixTotal.toFixed(2)} (must equal 1.00)</p>
    </div>
  );
}

function toInt(value: string, fallback: number): number {
  const next = Number.parseInt(value, 10);
  return Number.isFinite(next) ? next : fallback;
}

function toFloat(value: string, fallback: number): number {
  const next = Number.parseFloat(value);
  return Number.isFinite(next) ? next : fallback;
}

function numberOr(fallback: number, value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="muted">{label}</div>
      <div>{value}</div>
    </div>
  );
}

function MiniChart({ title, data, color }: { title: string; data: number[]; color: string }) {
  const width = 220;
  const height = 90;
  const pad = 8;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const span = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = pad + (i * (width - pad * 2)) / Math.max(data.length - 1, 1);
      const y = height - pad - ((v - min) / span) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="chart-card">
      <div className="chart-title">{title}</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="mini-chart" aria-label={`${title} chart`}>
        <rect x="0" y="0" width={width} height={height} fill="transparent" />
        <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#ddd3c7" />
        {data.length > 1 ? <polyline points={points} fill="none" stroke={color} strokeWidth="2.5" /> : null}
      </svg>
      <div className="muted chart-caption">{data.length ? `min ${min.toFixed(0)} / max ${max.toFixed(0)}` : "No samples yet"}</div>
    </div>
  );
}
