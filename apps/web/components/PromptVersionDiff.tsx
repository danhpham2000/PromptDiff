"use client";

import { useEffect, useState } from "react";

import { PromptVersion } from "../lib/api";

type DiffMode = "system" | "user";

type PromptVersionDiffProps = {
  versions: PromptVersion[];
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function textFor(version: PromptVersion, mode: DiffMode) {
  return mode === "system" ? version.system_prompt || "" : version.user_template || "";
}

function diffLines(baseline: string, candidate: string) {
  const baselineLines = baseline.split(/\r?\n/);
  const candidateLines = candidate.split(/\r?\n/);
  const maxLength = Math.max(baselineLines.length, candidateLines.length);
  const rows = [];

  for (let index = 0; index < maxLength; index += 1) {
    const left = baselineLines[index] ?? "";
    const right = candidateLines[index] ?? "";
    const status = left === right ? "same" : "changed";
    rows.push({ id: `${index}-${status}`, left, right, status });
  }

  return rows.length ? rows : [{ id: "empty", left: "", right: "", status: "same" }];
}

function VersionSummary({ label, version }: { label: string; version: PromptVersion }) {
  return (
    <div className="diff-summary-card">
      <span>{label}</span>
      <strong>Version {version.version_number}</strong>
      <dl className="version-meta">
        <div>
          <dt>Hash</dt>
          <dd>{version.content_hash.slice(0, 12)}</dd>
        </div>
        <div>
          <dt>Schema</dt>
          <dd>{version.schema_version}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDate(version.created_at)}</dd>
        </div>
      </dl>
    </div>
  );
}

export function PromptVersionDiff({ versions }: PromptVersionDiffProps) {
  const [baselineId, setBaselineId] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [mode, setMode] = useState<DiffMode>("system");

  useEffect(() => {
    if (versions.length < 2) {
      setBaselineId(versions[0]?.id || "");
      setCandidateId("");
      return;
    }
    setBaselineId((current) => (versions.some((version) => version.id === current) ? current : versions[versions.length - 2].id));
    setCandidateId((current) => (versions.some((version) => version.id === current) ? current : versions[versions.length - 1].id));
  }, [versions]);

  if (versions.length < 2) {
    return (
      <section className="prompt-diff-panel">
        <div className="section-heading">
          <h3>Prompt diff</h3>
          <p>Create another version to compare prompt changes.</p>
        </div>
      </section>
    );
  }

  const baseline = versions.find((version) => version.id === baselineId) || versions[0];
  const candidate = versions.find((version) => version.id === candidateId) || versions[versions.length - 1];
  const rows = diffLines(textFor(baseline, mode), textFor(candidate, mode));

  return (
    <section className="prompt-diff-panel">
      <div className="list-header">
        <div className="section-heading">
          <h3>Prompt diff</h3>
          <p>Compare immutable prompt versions before running an experiment.</p>
        </div>
        <div className="diff-mode-tabs" aria-label="Prompt diff text">
          <button className={mode === "system" ? "active" : ""} onClick={() => setMode("system")} type="button">
            System prompt
          </button>
          <button className={mode === "user" ? "active" : ""} onClick={() => setMode("user")} type="button">
            User template
          </button>
        </div>
      </div>

      <div className="two-column">
        <label>
          Baseline version
          <select onChange={(event) => setBaselineId(event.target.value)} value={baseline.id}>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                Version {version.version_number}
              </option>
            ))}
          </select>
        </label>
        <label>
          Candidate version
          <select onChange={(event) => setCandidateId(event.target.value)} value={candidate.id}>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                Version {version.version_number}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="diff-summary-grid">
        <VersionSummary label="Baseline" version={baseline} />
        <VersionSummary label="Candidate" version={candidate} />
      </div>

      <div className="prompt-diff-table" aria-label="Prompt version line diff">
        <div className="prompt-diff-table-header">
          <span>Baseline</span>
          <span>Candidate</span>
        </div>
        {rows.map((row, index) => (
          <div className={`prompt-diff-row ${row.status}`} key={row.id}>
            <pre className={row.status === "changed" ? "removed" : ""}>
              <span>{index + 1}</span>
              {row.left || " "}
            </pre>
            <pre className={row.status === "changed" ? "added" : ""}>
              <span>{index + 1}</span>
              {row.right || " "}
            </pre>
          </div>
        ))}
      </div>
    </section>
  );
}
