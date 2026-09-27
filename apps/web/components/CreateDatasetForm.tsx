"use client";

import { FormEvent, useState } from "react";

import { createDataset, Dataset } from "../lib/api";

type CreateDatasetFormProps = {
  onCreated: (dataset: Dataset) => void;
  onError: (message: string) => void;
  projectId: string;
};

export function CreateDatasetForm({ onCreated, onError, projectId }: CreateDatasetFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      onError("Dataset name is required.");
      return;
    }

    setIsCreating(true);
    onError("");
    try {
      const dataset = await createDataset({
        project_id: projectId,
        name: trimmedName,
        description: description.trim() || undefined,
      });
      onCreated(dataset);
      setName("");
      setDescription("");
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not create dataset.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit}>
      <label>
        Dataset name
        <input
          autoComplete="off"
          maxLength={200}
          onChange={(event) => setName(event.target.value)}
          placeholder="Refund support cases"
          value={name}
        />
      </label>

      <label>
        Description
        <textarea
          maxLength={2000}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Optional context for this dataset"
          rows={3}
          value={description}
        />
      </label>

      <button type="submit" disabled={isCreating}>
        {isCreating ? "Creating..." : "Create dataset"}
      </button>
    </form>
  );
}
