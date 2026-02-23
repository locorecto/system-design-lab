import type { GeneratedVariant } from "../../api/client";

export type GeneratedScenarioEvent = {
  scenarioId: string;
  variant: GeneratedVariant;
};

const EVENT_NAME = "system-design-lab:scenario-generated";

export function publishGeneratedScenario(event: GeneratedScenarioEvent) {
  window.dispatchEvent(new CustomEvent<GeneratedScenarioEvent>(EVENT_NAME, { detail: event }));
}

export function subscribeGeneratedScenario(listener: (event: GeneratedScenarioEvent) => void): () => void {
  const handler = (raw: Event) => {
    listener((raw as CustomEvent<GeneratedScenarioEvent>).detail);
  };
  window.addEventListener(EVENT_NAME, handler);
  return () => window.removeEventListener(EVENT_NAME, handler);
}

