const sampleRecommendations = [
  {
    technology: "Redis",
    why: "Reduce repeated read latency under read-heavy traffic",
    tradeoff: "Cache invalidation complexity"
  },
  {
    technology: "Kafka",
    why: "Move expensive writes/side effects off synchronous request path",
    tradeoff: "Operational complexity and eventual consistency"
  }
];

export function RecommendationsPanel() {
  return (
    <div className="panel">
      <p className="muted">Post-test technology recommendations (stub output)</p>
      <ul>
        {sampleRecommendations.map((item) => (
          <li key={item.technology}>
            <strong>{item.technology}</strong>: {item.why} ({item.tradeoff})
          </li>
        ))}
      </ul>
    </div>
  );
}

