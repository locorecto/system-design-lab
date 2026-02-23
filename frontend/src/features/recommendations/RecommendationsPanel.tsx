import { useEffect, useState } from "react";

import { getRunRecommendations, type Recommendation } from "../../api/client";
import { subscribeRunLifecycle } from "../runs/runEvents";

export function RecommendationsPanel() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    return subscribeRunLifecycle((evt) => {
      setActiveRunId(evt.runId);
      if (["completed", "throttled", "failed", "stopped"].includes(evt.status)) {
        setLoading(true);
        void getRunRecommendations(evt.runId)
          .then(setItems)
          .finally(() => setLoading(false));
      }
    });
  }, []);

  return (
    <div className="panel">
      <p className="muted">
        Post-test technology recommendations (metric-driven). {activeRunId ? `Run: ${activeRunId}` : "Start a run to populate."}
      </p>
      {loading ? <p>Analyzing...</p> : null}
      {items.length === 0 && !loading ? <p className="muted">No recommendations yet.</p> : null}
      <ul>
        {items.map((item) => (
          <li key={item.recommendation_id}>
            <strong>{item.technology}</strong>: {item.problem_observed} Suggested impact: {item.expected_impact}
          </li>
        ))}
      </ul>
    </div>
  );
}
