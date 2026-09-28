"use client";

import { useEffect, useState } from "react";

import { ComparisonEvaluation, ComparisonItem, ComparisonRunDetail, Experiment, ExperimentComparison, ExperimentProgress, experimentExportUrl, Dataset, Prompt } from "../lib/api";
import { CreateExperimentForm } from "./CreateExperimentForm";

type ExperimentPanelProps = {
  comparison: ExperimentComparison | null;
  datasets: Dataset[];
  experiments: Experiment[];
  isLoadingComparison: boolean;
  isLoadingExperiments: boolean;
  isLoadingProgress: boolean;
  onCancel: (experimentId: string) => void;
  onCreated: (experiment: Experiment) => void;
  onError: (message: string) => void;
  onRefresh: () => void;
  onRefreshComparison: () => void;
  onSelectExperiment: (experimentId: string) => void;
  progress: ExperimentProgress | null;
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

function formatElapsed(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) {
    return "n/a";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
}

function canCancel(experiment: Experiment) {
  return ["created", "queued", "running", "cancelling"].includes(experiment.status);
}

function ExperimentProgressPanel({ isLoading, progress }: { isLoading: boolean; progress: ExperimentProgress | null }) {
  if (!progress) {
    return (
      <div className="progress-card">
        <div className="version-header">
          <strong>Progress</strong>
          <span>{isLoading ? "Loading..." : "Pending"}</span>
        </div>
        <div className="progress-bar" aria-label="Experiment progress">
          <span style={{ width: "0%" }} />
        </div>
      </div>
    );
  }

  const percent = progress.progress_percent ?? 0;
  const progressText = progress.progress_percent === null ? "Waiting for runs" : `${progress.progress_percent}%`;

  return (
    <div className="progress-card">
      <div className="version-header">
        <strong>Progress</strong>
        <span>{isLoading ? "Refreshing..." : progressText}</span>
      </div>
      <div className="progress-bar" aria-label="Experiment progress">
        <span style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }} />
      </div>
      <dl className="metric-grid progress-grid">
        <div>
          <dt>Status</dt>
          <dd>{progress.status}</dd>
        </div>
        <div>
          <dt>Verdict</dt>
          <dd>{progress.verdict || "Pending"}</dd>
        </div>
        <div>
          <dt>Elapsed</dt>
          <dd>{formatElapsed(progress.elapsed_seconds)}</dd>
        </div>
        <div>
          <dt>Completed runs</dt>
          <dd>{progress.completed_runs}</dd>
        </div>
        <div>
          <dt>Failed runs</dt>
          <dd>{progress.failed_runs}</dd>
        </div>
        <div>
          <dt>Pending runs</dt>
          <dd>{progress.pending_runs}</dd>
        </div>
      </dl>
      {progress.status === "cancelled" ? (
        <p className="status-note">The experiment was stopped. Completed partial results are still available.</p>
      ) : null}
    </div>
  );
}

function metric(value: number | null) {
  return value === null ? "n/a" : value.toString();
}

function money(value: number | null) {
  return value === null ? "n/a" : `$${value.toFixed(6)}`;
}

function signedMetric(value: number | null, suffix = "") {
  if (value === null) {
    return "n/a";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value}${suffix}`;
}

function signedMoney(value: number | null) {
  if (value === null) {
    return "n/a";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}$${value.toFixed(6)}`;
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

function meanNullable(values: Array<number | null>) {
  const numbers = values.filter((value): value is number => value !== null);
  if (!numbers.length) {
    return null;
  }
  return numbers.reduce((sum, value) => sum + value, 0) / numbers.length;
}

function allEvaluations(item: ComparisonItem) {
  return [...(item.baseline?.evaluations || []), ...(item.candidate?.evaluations || [])];
}

function countHardGateFailures(items: ComparisonItem[]) {
  return items.reduce(
    (count, item) => count + allEvaluations(item).filter((evaluation) => evaluation.hard_gate && evaluation.passed === false).length,
    0,
  );
}

function countEvaluatorFailures(items: ComparisonItem[]) {
  return items.reduce(
    (count, item) =>
      count +
      allEvaluations(item).filter((evaluation) => !evaluation.hard_gate && (evaluation.passed === false || evaluation.state === "error")).length,
    0,
  );
}

function summarizeComparison(items: ComparisonItem[]) {
  const changed = items.filter((item) => item.regression_status === "changed").length;
  const unchanged = items.filter((item) => item.regression_status === "unchanged").length;
  return {
    cases: items.length,
    changed,
    unchanged,
    meanTokenDelta: meanNullable(items.map((item) => item.token_delta)),
    meanLatencyDelta: meanNullable(items.map((item) => item.latency_delta_ms)),
    meanCostDelta: meanNullable(items.map((item) => item.cost_delta_usd)),
    hardGateFailures: countHardGateFailures(items),
    evaluatorFailures: countEvaluatorFailures(items),
  };
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

function ResultsSummary({ comparison }: { comparison: ExperimentComparison | null }) {
  const summary = summarizeComparison(comparison?.items || []);
  const verdict = comparison?.experiment.verdict || "Pending";

  return (
    <section className="results-summary" aria-label="Results summary">
      <div className="version-header">
        <strong>Results summary</strong>
        <span>Verdict: {verdict}</span>
      </div>
      <dl className="summary-grid">
        <div className="summary-card verdict-card">
          <dt>Verdict</dt>
          <dd>{verdict}</dd>
        </div>
        <div className="summary-card">
          <dt>Cases</dt>
          <dd>{summary.cases}</dd>
        </div>
        <div className="summary-card">
          <dt>Changed</dt>
          <dd>
            {summary.changed} changed / {summary.unchanged} unchanged
          </dd>
        </div>
        <div className="summary-card">
          <dt>Token delta</dt>
          <dd>{signedMetric(summary.meanTokenDelta)}</dd>
        </div>
        <div className="summary-card">
          <dt>Latency delta</dt>
          <dd>{signedMetric(summary.meanLatencyDelta, " ms")}</dd>
        </div>
        <div className="summary-card">
          <dt>Cost delta</dt>
          <dd>{signedMoney(summary.meanCostDelta)}</dd>
        </div>
        <div className="summary-card">
          <dt>Hard gates</dt>
          <dd>{summary.hardGateFailures} failed</dd>
        </div>
        <div className="summary-card">
          <dt>Evaluator failures</dt>
          <dd>{summary.evaluatorFailures} failed or errored</dd>
        </div>
      </dl>
    </section>
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
  isLoadingProgress,
  onCancel,
  onCreated,
  onError,
  onRefresh,
  onRefreshComparison,
  onSelectExperiment,
  progress,
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

            <ExperimentProgressPanel isLoading={isLoadingProgress} progress={progress} />

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

            {comparison ? <ResultsSummary comparison={comparison} /> : null}

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
