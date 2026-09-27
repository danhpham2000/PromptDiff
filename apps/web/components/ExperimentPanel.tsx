import { ComparisonItem, Experiment, ExperimentComparison, experimentExportUrl, Dataset, Prompt } from "../lib/api";
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

function summarizeDiff(value: unknown) {
  if (typeof value === "string") {
    return value || "No change";
  }
  if (value === null || value === undefined) {
    return "n/a";
  }
  return JSON.stringify(value);
}

function ComparisonRows({ items }: { items: ComparisonItem[] }) {
  if (!items.length) {
    return (
      <div className="empty-state compact">
        <strong>No comparison rows</strong>
        <span>This experiment has no case-level comparison output yet.</span>
      </div>
    );
  }

  return (
    <div className="comparison-list" aria-label="Experiment comparison rows">
      {items.map((item) => (
        <article className="comparison-row" key={item.id}>
          <div className="version-header">
            <strong>{item.regression_status || "unknown"}</strong>
            <span>{item.id.slice(0, 8)}</span>
          </div>
          <dl className="version-meta">
            <div>
              <dt>Tokens</dt>
              <dd>{metric(item.token_delta)}</dd>
            </div>
            <div>
              <dt>Latency</dt>
              <dd>{metric(item.latency_delta_ms)} ms</dd>
            </div>
          </dl>
          <div className="version-preview">
            <span>Output diff</span>
            <p>{summarizeDiff(item.output_diff)}</p>
          </div>
          <div className="version-preview">
            <span>Tool diff</span>
            <p>{summarizeDiff(item.tool_diff)}</p>
          </div>
        </article>
      ))}
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
