"use client";

import { FormEvent, useState } from "react";

import { Dataset, importDataset } from "../lib/api";

type ImportDatasetFormProps = {
  onImported: (dataset: Dataset) => void;
  onError: (message: string) => void;
  projectId: string;
};

export function ImportDatasetForm({ onImported, onError, projectId }: ImportDatasetFormProps) {
  const [format, setFormat] = useState<"yaml" | "json">("yaml");
  const [content, setContent] = useState("");
  const [isImporting, setIsImporting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!content.trim()) {
      onError("Dataset import content is required.");
      return;
    }

    setIsImporting(true);
    onError("");
    try {
      const dataset = await importDataset({ project_id: projectId, format, content });
      onImported(dataset);
      setContent("");
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not import dataset.");
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit}>
      <label>
        Format
        <select onChange={(event) => setFormat(event.target.value as "yaml" | "json")} value={format}>
          <option value="yaml">YAML</option>
          <option value="json">JSON</option>
        </select>
      </label>

      <label>
        Import content
        <textarea
          maxLength={1000000}
          onChange={(event) => setContent(event.target.value)}
          placeholder={'name: refunds\ncases:\n  - name: monthly\n    input:\n      message: "Refund my subscription"'}
          rows={6}
          value={content}
        />
      </label>

      <button type="submit" disabled={isImporting}>
        {isImporting ? "Importing..." : "Import dataset"}
      </button>
    </form>
  );
}
