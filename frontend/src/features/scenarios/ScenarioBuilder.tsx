import { useState } from "react";

import { createScenario, generateScenarioDesign, saveScenarioRequirements, type GeneratedVariant } from "../../api/client";
import { publishGeneratedScenario } from "./scenarioEvents";

export function ScenarioBuilder() {
  const [scenarioName, setScenarioName] = useState("Feed System Practice");
  const [scenarioDescription, setScenarioDescription] = useState("Read-heavy social feed with search");
  const [functionalText, setFunctionalText] = useState("- User can create posts\n- User can read feed\n- User can like posts\n- User can search posts");
  const [nfrText, setNfrText] = useState("throughput_rps: 5000\nlatency_p95_ms: 200\nconsistency: eventual\navailability: 99.9%");
  const [isGenerating, setIsGenerating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [generatedVariant, setGeneratedVariant] = useState<GeneratedVariant | null>(null);

  async function handleGenerate() {
    setIsGenerating(true);
    setMessage(null);
    setGeneratedVariant(null);
    try {
      const functionalRequirements = parseFunctionalRequirements(functionalText);
      const nonFunctionalRequirements = parseNonFunctionalRequirements(nfrText);
      const scenario = await createScenario("prj_local", {
        name: scenarioName,
        description: scenarioDescription
      });
      await saveScenarioRequirements(scenario.scenario_id, {
        functional_requirements: functionalRequirements,
        non_functional_requirements: nonFunctionalRequirements
      });
      const generated = await generateScenarioDesign(scenario.scenario_id);
      if (generated.error) {
        setMessage(generated.error);
        return;
      }
      const variant = generated.variants[0];
      if (!variant) {
        setMessage("No variant generated.");
        return;
      }
      setGeneratedVariant(variant);
      publishGeneratedScenario({ scenarioId: scenario.scenario_id, variant });
      setMessage(`Generated variant ${variant.variant_id} for scenario ${scenario.scenario_id}. Run Dashboard updated.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to generate design");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div className="panel">
      <label htmlFor="scenario-name">Scenario name</label>
      <input id="scenario-name" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} />
      <div style={{ height: 8 }} />
      <label htmlFor="scenario-description">Description</label>
      <input id="scenario-description" value={scenarioDescription} onChange={(e) => setScenarioDescription(e.target.value)} />
      <div style={{ height: 8 }} />

      <label htmlFor="functional">Functional requirements (one per line)</label>
      <textarea id="functional" rows={6} value={functionalText} onChange={(e) => setFunctionalText(e.target.value)} />
      <div style={{ height: 8 }} />
      <label htmlFor="nfr">Non-functional requirements (`key: value` per line)</label>
      <textarea id="nfr" rows={5} value={nfrText} onChange={(e) => setNfrText(e.target.value)} />
      <div style={{ height: 12 }} />
      <button type="button" onClick={() => void handleGenerate()} disabled={isGenerating}>
        {isGenerating ? "Generating..." : "Generate Testable System"}
      </button>

      {message ? <p className="muted" style={{ marginTop: 8 }}>{message}</p> : null}

      {generatedVariant ? (
        <div className="config-panel" style={{ marginTop: 10 }}>
          <div className="muted">Generated Variant</div>
          <div><strong>{generatedVariant.name}</strong> ({generatedVariant.variant_id})</div>
          <div className="muted" style={{ marginTop: 6 }}>{generatedVariant.rationale}</div>
          <div style={{ marginTop: 6 }}>
            <strong>Components:</strong> {generatedVariant.components.join(", ")}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function parseFunctionalRequirements(input: string): string[] {
  return input
    .split(/\r?\n/)
    .map((line) => line.replace(/^\s*[-*]\s*/, "").trim())
    .filter(Boolean);
}

function parseNonFunctionalRequirements(input: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const rawLine of input.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const idx = line.indexOf(":");
    if (idx < 0) {
      continue;
    }
    const key = line.slice(0, idx).trim();
    const valueRaw = line.slice(idx + 1).trim();
    if (!key) continue;
    const numeric = Number.parseFloat(valueRaw.replace(/,/g, ""));
    result[key] = Number.isFinite(numeric) && /^\d+(\.\d+)?$/.test(valueRaw) ? numeric : valueRaw;
  }
  return result;
}
