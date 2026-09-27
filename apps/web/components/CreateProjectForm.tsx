"use client";

import { FormEvent, useState } from "react";

import { createProject, Project } from "../lib/api";

type CreateProjectFormProps = {
  onCreated: (project: Project) => void;
  onError: (message: string) => void;
};

export function CreateProjectForm({ onCreated, onError }: CreateProjectFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      onError("Project name is required.");
      return;
    }

    setIsCreating(true);
    onError("");
    try {
      const project = await createProject({
        name: trimmedName,
        description: description.trim() || undefined,
      });
      onCreated(project);
      setName("");
      setDescription("");
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not create project.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <form className="panel stack" onSubmit={handleSubmit}>
      <div className="section-heading">
        <h2>Create Project</h2>
        <p>Start a workspace for prompts, datasets, and experiments.</p>
      </div>

      <label>
        Name
        <input
          autoComplete="off"
          maxLength={200}
          onChange={(event) => setName(event.target.value)}
          placeholder="Support regression suite"
          value={name}
        />
      </label>

      <label>
        Description
        <textarea
          maxLength={2000}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Optional context for this project"
          rows={4}
          value={description}
        />
      </label>

      <button type="submit" disabled={isCreating}>
        {isCreating ? "Creating..." : "Create project"}
      </button>
    </form>
  );
}
