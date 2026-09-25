"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Result = {
  experiment?: { id: string; status: string; verdict: string | null };
  items?: unknown[];
};

async function api(path: string, body?: unknown) {
  const response = await fetch(`${API}${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export default function Home() {
  const [baseline, setBaseline] = useState("You are a support agent. For enterprise refunds, escalate to a human.");
  const [candidate, setCandidate] = useState("You are a support agent. Refund monthly plans directly, but escalate enterprise refunds.");
  const [enterprise, setEnterprise] = useState("Refund my annual enterprise plan");
  const [monthly, setMonthly] = useState("Refund my monthly subscription");
  const [result, setResult] = useState<Result>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function runComparison() {
    setBusy(true);
    setError("");
    try {
      const project = await api("/api/v1/projects", { name: "Local PromptDiff Demo" });
      const promptA = await api("/api/v1/prompts", { project_id: project.id, name: "baseline" });
      const promptB = await api("/api/v1/prompts", { project_id: project.id, name: "candidate" });
      const versionA = await api(`/api/v1/prompts/${promptA.id}/versions`, {
        system_prompt: baseline,
        user_template: "{{message}}",
        tool_definitions: [],
        metadata: { source: "web" },
      });
      const versionB = await api(`/api/v1/prompts/${promptB.id}/versions`, {
        system_prompt: candidate,
        user_template: "{{message}}",
        tool_definitions: [],
        metadata: { source: "web" },
      });
      const dataset = await api("/api/v1/datasets", { project_id: project.id, name: "refunds" });
      await api(`/api/v1/datasets/${dataset.id}/cases`, {
        name: "enterprise refund",
        input: { message: enterprise },
        expected_output: { tool: { name: "escalate_to_human" } },
      });
      await api(`/api/v1/datasets/${dataset.id}/cases`, {
        name: "monthly refund",
        input: { message: monthly },
        expected_output: { tool: { name: "refund_customer" } },
      });
      const experiment = await api("/api/v1/experiments", {
        project_id: project.id,
        name: "web-comparison",
        baseline_prompt_version_id: versionA.id,
        candidate_prompt_version_id: versionB.id,
        dataset_id: dataset.id,
        provider: "mock",
        model: "mock-support",
        repetitions: 1,
        concurrency: 5,
        timeout_seconds: 60,
        evaluators: [{ name: "tool-selection", type: "tool_selection", category: "tool", hard_gate: true, required: true }],
        regression: { quality: { max_drop_points: 2 } },
      });
      const comparison = await api(`/api/v1/experiments/${experiment.id}/comparison`);
      setResult(comparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  const verdict = result.experiment?.verdict;

  return (
    <main>
      <header>
        <div>
          <h1>PromptDiff</h1>
          <p>Compare prompt behavior, tool calls, latency, tokens, and regression gates.</p>
        </div>
        <button onClick={runComparison} disabled={busy}>{busy ? "Running..." : "Run Comparison"}</button>
      </header>

      <section className="grid">
        <div className="panel stack">
          <h2>Baseline</h2>
          <label>
            System prompt
            <textarea rows={8} value={baseline} onChange={(event) => setBaseline(event.target.value)} />
          </label>
        </div>
        <div className="panel stack">
          <h2>Candidate</h2>
          <label>
            System prompt
            <textarea rows={8} value={candidate} onChange={(event) => setCandidate(event.target.value)} />
          </label>
        </div>
      </section>

      <section className="panel stack" style={{ marginTop: 16 }}>
        <h2>Dataset</h2>
        <div className="grid">
          <label>
            Enterprise case
            <input value={enterprise} onChange={(event) => setEnterprise(event.target.value)} />
          </label>
          <label>
            Monthly case
            <input value={monthly} onChange={(event) => setMonthly(event.target.value)} />
          </label>
        </div>
      </section>

      <section className="panel stack" style={{ marginTop: 16 }}>
        <div className="row">
          <h2>Results</h2>
          {verdict ? <span className={`status ${verdict === "FAIL" ? "fail" : ""}`}>{verdict}</span> : <span className="status">Not Run</span>}
        </div>
        {error ? <p role="alert">{error}</p> : null}
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </section>
    </main>
  );
}

