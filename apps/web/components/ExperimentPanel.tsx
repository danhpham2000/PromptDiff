"use client";

import { useEffect, useState } from "react";

import { ComparisonEvaluation, ComparisonItem, ComparisonRunDetail, Experiment, ExperimentComparison, experimentExportUrl, Dataset, Prompt } from "../lib/api";
import { CreateExperimentForm } from "./CreateExperimentForm";

type ExperimentPanelProps = {
  comparison: ExperimentComparison | null;
  datasets: Dataset[];
  experiments: Experiment[];
  isLoadingComparison: boolean;
  isLoadingExperiments: boolean;
  onCancel: (experimentId: string) => void;
  onCreated: (experiment: Experiment) => void;
  onError: (message: string) => void;
  onRefresh: () => void;
  onRefreshComparison: () => void;
  onSelectExperiment: (experimentId: string) => void;
  projectId: string | null;
  prompts: Prompt[];
  selectedExperimentId: string | null;
};

function formatDate(value: string | null) {
  if (!value) {
    return "Not completed";
  }
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function canCancel(experiment: Experiment) {
  return ["created", "queued", "running", "cancelling"].includes(experiment.status);
}

function metric(value: number | null) {
  return value === null ? "n/a" : value.toString();
}

function money(value: number | null) {
  return value === null ? "n/a" : `$${value.toFixed(6)}`;
}

function prettyJson(value: unknown) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "string") {
    return value || "n/a";
  }
  return JSON.stringify(value, null, 2);
}

function runContent(run: ComparisonRunDetail | null) {
  return run?.output?.content || run?.error_message || "n/a";
}

function evaluationLabel(evaluation: ComparisonEvaluation) {
  if (evaluation.hard_gate && evaluation.passed === false) {
    return "Hard gate failed";
  }
  if (evaluation.hard_gate && evaluation.passed === true) {
    return "Hard gate passed";
  }
  return evaluation.state;
}

function RunMetricSummary({ run }: { run: ComparisonRunDetail | null }) {
  return (
    <dl className="version-meta">
      <div>
        <dt>Status</dt>
        <dd>{run?.status || "n/a"}</dd>
      </div>
      <div>
        <dt>Tokens</dt>
        <dd>{metric(run?.total_tokens ?? null)}</dd>
      </div>
      <div>
        <dt>Latency</dt>
        <dd>{metric(run?.latency_ms ?? null)} ms</dd>
      </div>
      <div>
        <dt>Cost</dt>
        <dd>{money(run?.estimated_cost_usd ?? null)}</dd>
      </div>
    </dl>
  );
}

function RunEvaluations({ label, run }: { label: string; run: ComparisonRunDetail | null }) {
  if (!run?.evaluations.length) {
    return (
      <div className="empty-state compact">
        <strong>{label}</strong>
        <span>No evaluator results.</span>
      </div>
    );
  }

  return (
    <div className="result-column">
      <h3>{label}</h3>
      {run.evaluations.map((evaluation) => (
        <article className="mini-card" key={`${run.id}-${evaluation.evaluator_name}`}>
          <div className="version-header">
            <strong>{evaluation.evaluator_name}</strong>
            <span>{evaluationLabel(evaluation)}</span>
          </div>
          <dl className="version-meta">
            <div>
              <dt>Score</dt>
              <dd>{metric(evaluation.score)}</dd>
            </div>
            <div>
              <dt>Category</dt>
              <dd>{evaluation.category || "n/a"}</dd>
            </div>
          </dl>
          <pre className="json-block">{prettyJson(evaluation.details)}</pre>
        </article>
      ))}
    </div>
  );
}

function RunToolCalls({ label, run }: { label: string; run: ComparisonRunDetail | null }) {
  if (!run?.tool_calls.length) {
    return (
      <div className="empty-state compact">
        <strong>{label}</strong>
        <span>No tool calls.</span>
      </div>
    );
  }

  return (
    <div className="result-column">
      <h3>{label}</h3>
      {run.tool_calls.map((call) => (
        <article className="mini-card" key={`${run.id}-${call.sequence_number}`}>
          <div className="version-header">
            <strong>{call.name}</strong>
            <span>#{call.sequence_number}</span>
          </div>
          <pre className="json-block">{prettyJson(call.arguments)}</pre>
        </article>
      ))}
    </div>
  );
}

function ComparisonRows({ items }: { items: ComparisonItem[] }) {
  const [selectedItemId, setSelectedItemId] = useState(items[0]?.id || "");

  useEffect(() => {
    if (!items.some((item) => item.id === selectedItemId)) {
      setSelectedItemId(items[0]?.id || "");
    }
  }, [items, selectedItemId]);

  const selectedItem = items.find((item) => item.id === selectedItemId) || items[0] || null;

  if (!items.length) {
    return (
      <div className="empty-state compact">
        <strong>No comparison rows</strong>
        <span>This experiment has no case-level comparison output yet.</span>
      </div>
    );
  }

  return (
    <div className="case-detail-grid">
      <div className="case-selector-list" aria-label="Experiment comparison rows">
        {items.map((item, index) => (
          <button
            aria-pressed={item.id === selectedItem?.id}
            className={`case-selector-row ${item.id === selectedItem?.id ? "selected" : ""}`}
            key={item.id}
            onClick={() => setSelectedItemId(item.id)}
            type="button"
          >
            <span>
              <strong>Case {index + 1}</strong>
              <span>Repetition {item.repetition}</span>
            </span>
            <span>{item.regression_status || "unknown"}</span>
          </button>
        ))}
      </div>

      {selectedItem ? (
        <article className="case-detail">
          <div className="section-heading">
            <h3>Case detail</h3>
            <p>{selectedItem.regression_status || "No regression status"} · {selectedItem.dataset_case_id.slice(0, 8)}</p>
          </div>

          <section className="result-section">
            <h3>Input</h3>
            <pre className="json-block">{prettyJson(selectedItem.input)}</pre>
          </section>

          <section className="result-section">
            <h3>Metrics</h3>
            <dl className="metric-grid">
              <div>
                <dt>Token delta</dt>
                <dd>{metric(selectedItem.token_delta)}</dd>
              </div>
              <div>
                <dt>Latency delta</dt>
                <dd>{metric(selectedItem.latency_delta_ms)} ms</dd>
              </div>
              <div>
                <dt>Cost delta</dt>
                <dd>{money(selectedItem.cost_delta_usd)}</dd>
              </div>
            </dl>
          </section>

          <section className="result-section">
            <div className="run-output-grid">
              <div className="result-column">
                <h3>Baseline output</h3>
                <RunMetricSummary run={selectedItem.baseline} />
                <pre className="json-block">{runContent(selectedItem.baseline)}</pre>
              </div>
              <div className="result-column">
                <h3>Candidate output</h3>
                <RunMetricSummary run={selectedItem.candidate} />
                <pre className="json-block">{runContent(selectedItem.candidate)}</pre>
              </div>
            </div>
          </section>

          <section className="result-section">
            <h3>Output diff</h3>
            <pre className="json-block">{prettyJson(selectedItem.output_diff)}</pre>
          </section>

          <section className="result-section">
            <h3>Tool calls</h3>
            <div className="run-output-grid">
              <RunToolCalls label="Baseline tools" run={selectedItem.baseline} />
              <RunToolCalls label="Candidate tools" run={selectedItem.candidate} />
            </div>
          </section>

          <section className="result-section">
            <h3>Tool diff</h3>
            <pre className="json-block">{prettyJson(selectedItem.tool_diff)}</pre>
          </section>

          <section className="result-section">
            <h3>Evaluator results</h3>
            <div className="run-output-grid">
              <RunEvaluations label="Baseline evaluators" run={selectedItem.baseline} />
              <RunEvaluations label="Candidate evaluators" run={selectedItem.candidate} />
            </div>
          </section>
        </article>
      ) : null}
    </div>
  );
}

export function ExperimentPanel({
  comparison,
  datasets,
  experiments,
  isLoadingComparison,
  isLoadingExperiments,
  onCancel,
  onCreated,
  onError,
  onRefresh,
  onRefreshComparison,
  onSelectExperiment,
  projectId,
  prompts,
  selectedExperimentId,
}: ExperimentPanelProps) {
  const selectedExperiment = experiments.find((experiment) => experiment.id === selectedExperimentId) || null;

  if (!projectId) {
    return (
      <section className="panel stack">
        <div className="section-heading">
          <h2>Experiments</h2>
          <p>Select a project to run experiments.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <section className="panel stack">
        <div className="list-header">
          <div className="section-heading">
            <h2>Experiments</h2>
            <p>{experiments.length ? `${experiments.length} experiment${experiments.length === 1 ? "" : "s"}` : "No experiments yet"}</p>
          </div>
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoadingExperiments}>
            {isLoadingExperiments ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <CreateExperimentForm datasets={datasets} onCreated={onCreated} onError={onError} projectId={projectId} prompts={prompts} />

        {isLoadingExperiments && !experiments.length ? <div className="empty-state compact">Loading experiments...</div> : null}

        {!isLoadingExperiments && !experiments.length ? (
          <div className="empty-state compact">
            <strong>No experiments yet</strong>
            <span>Run one from existing prompt versions and datasets.</span>
          </div>
        ) : null}

        {experiments.length ? (
          <div className="experiment-list" aria-label="Experiments">
            {experiments.map((experiment) => (
              <button
                aria-pressed={experiment.id === selectedExperimentId}
                className={`experiment-row ${experiment.id === selectedExperimentId ? "selected" : ""}`}
                key={experiment.id}
                onClick={() => onSelectExperiment(experiment.id)}
                type="button"
              >
                <span>
                  <strong>{experiment.name}</strong>
                  <span>{experiment.status}</span>
                </span>
                <span>{experiment.verdict || "No verdict"}</span>
              </button>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel stack">
        <div className="list-header">
          <div className="section-heading">
            <h2>Results</h2>
            <p>{selectedExperiment ? `${selectedExperiment.name}: ${selectedExperiment.status}` : "Select an experiment to inspect results."}</p>
          </div>
          {selectedExperiment ? (
            <button className="secondary-button" type="button" onClick={onRefreshComparison} disabled={isLoadingComparison}>
              {isLoadingComparison ? "Refreshing..." : "Refresh"}
            </button>
          ) : null}
        </div>

        {selectedExperiment ? (
          <>
            <dl className="detail-list">
              <div>
                <dt>Verdict</dt>
                <dd>{selectedExperiment.verdict || "Pending"}</dd>
              </div>
              <div>
                <dt>Dataset snapshot</dt>
                <dd>{selectedExperiment.dataset_snapshot_id || "Pending"}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{formatDate(selectedExperiment.created_at)}</dd>
              </div>
              <div>
                <dt>Completed</dt>
                <dd>{formatDate(selectedExperiment.completed_at)}</dd>
              </div>
            </dl>

            <div className="button-row">
              {canCancel(selectedExperiment) ? (
                <button className="secondary-button" type="button" onClick={() => onCancel(selectedExperiment.id)}>
                  Cancel
                </button>
              ) : null}
              {(["json", "markdown", "csv", "junit"] as const).map((format) => (
                <a className="export-link" href={experimentExportUrl(selectedExperiment.id, format)} key={format}>
                  {format}
                </a>
              ))}
            </div>

            {isLoadingComparison ? <div className="empty-state compact">Loading comparison...</div> : <ComparisonRows items={comparison?.items || []} />}
          </>
        ) : (
          <div className="empty-state compact">
            <strong>No experiment selected</strong>
            <span>Run or select an experiment to view comparison rows.</span>
          </div>
        )}
      </section>
    </>
  );
}
