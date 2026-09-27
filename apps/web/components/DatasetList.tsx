import { Dataset } from "../lib/api";
import { CreateDatasetForm } from "./CreateDatasetForm";
import { ImportDatasetForm } from "./ImportDatasetForm";

type DatasetListProps = {
  datasets: Dataset[];
  isLoading: boolean;
  onCreated: (dataset: Dataset) => void;
  onError: (message: string) => void;
  onRefresh: () => void;
  onSelectDataset: (datasetId: string) => void;
  projectId: string | null;
  selectedDatasetId: string | null;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function DatasetList({
  datasets,
  isLoading,
  onCreated,
  onError,
  onRefresh,
  onSelectDataset,
  projectId,
  selectedDatasetId,
}: DatasetListProps) {
  if (!projectId) {
    return (
      <section className="panel stack">
        <div className="section-heading">
          <h2>Datasets</h2>
          <p>Select a project to manage datasets.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel stack">
      <div className="list-header">
        <div className="section-heading">
          <h2>Datasets</h2>
          <p>{datasets.length ? `${datasets.length} dataset${datasets.length === 1 ? "" : "s"}` : "No datasets yet"}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <CreateDatasetForm projectId={projectId} onCreated={onCreated} onError={onError} />
      <ImportDatasetForm projectId={projectId} onImported={onCreated} onError={onError} />

      {isLoading && !datasets.length ? <div className="empty-state compact">Loading datasets...</div> : null}

      {!isLoading && !datasets.length ? (
        <div className="empty-state compact">
          <strong>No datasets yet</strong>
          <span>Create or import a dataset to add cases.</span>
        </div>
      ) : null}

      {datasets.length ? (
        <div className="dataset-list" aria-label="Datasets">
          {datasets.map((dataset) => (
            <button
              aria-pressed={dataset.id === selectedDatasetId}
              className={`dataset-row ${dataset.id === selectedDatasetId ? "selected" : ""}`}
              key={dataset.id}
              onClick={() => onSelectDataset(dataset.id)}
              type="button"
            >
              <span>
                <strong>{dataset.name}</strong>
                <span>{dataset.description || "No description"}</span>
              </span>
              <span>Created {formatDate(dataset.created_at)}</span>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
