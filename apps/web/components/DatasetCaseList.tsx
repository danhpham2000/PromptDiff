"use client";

import { FormEvent, useState } from "react";

import { createDatasetCase, Dataset, DatasetCase } from "../lib/api";

type DatasetCaseListProps = {
  cases: DatasetCase[];
  dataset: Dataset | null;
  isLoading: boolean;
  onCreated: (datasetCase: DatasetCase) => void;
  onError: (message: string) => void;
  onRefresh: () => void;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function parseObjectField(label: string, value: string, allowEmpty: boolean) {
  const trimmed = value.trim();
  if (!trimmed && allowEmpty) {
    return undefined;
  }
  if (!trimmed) {
    throw new Error(`${label} is required.`);
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (Array.isArray(parsed) || parsed === null || typeof parsed !== "object") {
      throw new Error(`${label} must be a JSON object.`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof Error && error.message.endsWith("JSON object.")) {
      throw error;
    }
    throw new Error(`${label} must be valid JSON.`);
  }
}

function preview(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function CreateDatasetCaseForm({
  datasetId,
  onCreated,
  onError,
}: {
  datasetId: string;
  onCreated: (datasetCase: DatasetCase) => void;
  onError: (message: string) => void;
}) {
  const [name, setName] = useState("");
  const [input, setInput] = useState('{"message": ""}');
  const [expectedOutput, setExpectedOutput] = useState("");
  const [metadata, setMetadata] = useState("{}");
  const [isCreating, setIsCreating] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    let parsedInput: Record<string, unknown>;
    let parsedExpected: Record<string, unknown> | undefined;
    let parsedMetadata: Record<string, unknown> | undefined;

    try {
      parsedInput = parseObjectField("Input", input, false) as Record<string, unknown>;
      parsedExpected = parseObjectField("Expected output", expectedOutput, true);
      parsedMetadata = parseObjectField("Metadata", metadata, true);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Invalid JSON.");
      return;
    }

    setIsCreating(true);
    onError("");
    try {
      const datasetCase = await createDatasetCase(datasetId, {
        name: name.trim() || undefined,
        input: parsedInput,
        expected_output: parsedExpected,
        metadata: parsedMetadata,
      });
      onCreated(datasetCase);
      setName("");
      setInput('{"message": ""}');
      setExpectedOutput("");
      setMetadata("{}");
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not create dataset case.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit}>
      <label>
        Case name
        <input autoComplete="off" maxLength={200} onChange={(event) => setName(event.target.value)} placeholder="monthly refund" value={name} />
      </label>

      <label>
        Input JSON
        <textarea onChange={(event) => setInput(event.target.value)} rows={4} value={input} />
      </label>

      <div className="two-column">
        <label>
          Expected output JSON
          <textarea onChange={(event) => setExpectedOutput(event.target.value)} placeholder='{"tool":{"name":"refund_customer"}}' rows={4} value={expectedOutput} />
        </label>
        <label>
          Metadata JSON
          <textarea onChange={(event) => setMetadata(event.target.value)} rows={4} value={metadata} />
        </label>
      </div>

      <button type="submit" disabled={isCreating}>
        {isCreating ? "Adding..." : "Add case"}
      </button>
    </form>
  );
}

export function DatasetCaseList({ cases, dataset, isLoading, onCreated, onError, onRefresh }: DatasetCaseListProps) {
  if (!dataset) {
    return (
      <section className="panel stack">
        <div className="section-heading">
          <h2>Cases</h2>
          <p>Select a dataset to manage cases.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel stack">
      <div className="list-header">
        <div className="section-heading">
          <h2>Cases</h2>
          <p>
            {dataset.name}: {cases.length ? `${cases.length} case${cases.length === 1 ? "" : "s"}` : "No cases yet"}
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <CreateDatasetCaseForm datasetId={dataset.id} onCreated={onCreated} onError={onError} />

      {isLoading && !cases.length ? <div className="empty-state compact">Loading cases...</div> : null}

      {!isLoading && !cases.length ? (
        <div className="empty-state compact">
          <strong>No cases yet</strong>
          <span>Add a case to make this dataset useful in experiments.</span>
        </div>
      ) : null}

      {cases.length ? (
        <div className="case-list" aria-label="Dataset cases">
          {cases.map((datasetCase) => (
            <article className="case-row" key={datasetCase.id}>
              <div className="version-header">
                <strong>{datasetCase.name || "Untitled case"}</strong>
                <span>Created {formatDate(datasetCase.created_at)}</span>
              </div>
              <div className="version-preview">
                <span>Input</span>
                <pre>{preview(datasetCase.input)}</pre>
              </div>
              {datasetCase.expected_output ? (
                <div className="version-preview">
                  <span>Expected</span>
                  <pre>{preview(datasetCase.expected_output)}</pre>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
