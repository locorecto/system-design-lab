export function ScenarioBuilder() {
  return (
    <div className="panel">
      <label htmlFor="functional">Functional requirements</label>
      <textarea
        id="functional"
        rows={6}
        defaultValue={"- User can create posts\n- User can read feed\n- User can like posts"}
      />
      <div style={{ height: 8 }} />
      <label htmlFor="nfr">Non-functional requirements</label>
      <textarea
        id="nfr"
        rows={5}
        defaultValue={"throughput: 5k rps\nlatency: p95 < 200ms\nconsistency: eventual for feed reads"}
      />
      <div style={{ height: 12 }} />
      <button type="button">Generate Design (stub)</button>
    </div>
  );
}

