import type { PropsWithChildren } from "react";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <main className="app-shell">
      <header>
        <p className="pill">System Design Lab / Starter Scaffold</p>
        <h1>Design, Load Test, Observe, Improve</h1>
        <p className="muted">
          Frontend shell mapped to the architecture doc: scenario builder, run dashboard, and recommendations.
        </p>
      </header>
      <div className="grid">{children}</div>
    </main>
  );
}

