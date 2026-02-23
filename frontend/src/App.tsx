import { AppShell } from "./components/layout/AppShell";
import { ScenarioBuilder } from "./features/scenarios/ScenarioBuilder";
import { RunDashboard } from "./features/runs/RunDashboard";
import { RecommendationsPanel } from "./features/recommendations/RecommendationsPanel";

export default function App() {
  return (
    <AppShell>
      <section>
        <h2>Scenario Builder</h2>
        <ScenarioBuilder />
      </section>
      <section>
        <h2>Run Monitor</h2>
        <RunDashboard />
      </section>
      <section>
        <h2>Recommendations</h2>
        <RecommendationsPanel />
      </section>
    </AppShell>
  );
}

