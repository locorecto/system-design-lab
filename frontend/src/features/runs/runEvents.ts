export type RunTerminalStatus = "completed" | "failed" | "stopped" | "throttled";

export type RunLifecycleEvent = {
  runId: string;
  status: string;
  phase: string;
};

const RUN_EVENT_NAME = "system-design-lab:run-lifecycle";

export function publishRunLifecycle(event: RunLifecycleEvent) {
  window.dispatchEvent(new CustomEvent<RunLifecycleEvent>(RUN_EVENT_NAME, { detail: event }));
}

export function subscribeRunLifecycle(listener: (event: RunLifecycleEvent) => void): () => void {
  const handler = (raw: Event) => {
    const event = raw as CustomEvent<RunLifecycleEvent>;
    listener(event.detail);
  };
  window.addEventListener(RUN_EVENT_NAME, handler);
  return () => window.removeEventListener(RUN_EVENT_NAME, handler);
}

