const metrics = [
  { label: "RPS", value: "0" },
  { label: "P95 Latency", value: "N/A" },
  { label: "Error Rate", value: "0%" },
  { label: "CPU", value: "0%" },
  { label: "Memory", value: "0 MB" },
  { label: "Status", value: "idle" }
];

export function RunDashboard() {
  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <strong>Live Monitoring</strong>
        <button type="button">Start Run (stub)</button>
      </div>
      <div className="metric-grid">
        {metrics.map((metric) => (
          <div key={metric.label} className="metric-card">
            <div className="muted">{metric.label}</div>
            <div>{metric.value}</div>
          </div>
        ))}
      </div>
      <p className="muted" style={{ marginTop: 12 }}>
        Replace with WebSocket/SSE metric streams and charts from `GET /api/runs/{'{run_id}'}/stream`.
      </p>
    </div>
  );
}

