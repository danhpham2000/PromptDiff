"use client";

import { FormEvent, useState } from "react";

import { createPrompt, Prompt } from "../lib/api";

type CreatePromptFormProps = {
  projectId: string;
  onCreated: (prompt: Prompt) => void;
  onError: (message: string) => void;
};

export function CreatePromptForm({ projectId, onCreated, onError }: CreatePromptFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      onError("Prompt name is required.");
      return;
    }

    setIsCreating(true);
    onError("");
    try {
      const prompt = await createPrompt({
        project_id: projectId,
        name: trimmedName,
        description: description.trim() || undefined,
      });
      onCreated(prompt);
      setName("");
      setDescription("");
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not create prompt.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <form className="prompt-form" onSubmit={handleSubmit}>
      <label>
        Prompt name
        <input
          autoComplete="off"
          maxLength={200}
          onChange={(event) => setName(event.target.value)}
          placeholder="Refund policy responder"
          value={name}
        />
      </label>

      <label>
        Description
        <textarea
          maxLength={2000}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Optional context for this prompt"
          rows={3}
          value={description}
        />
      </label>

      <button type="submit" disabled={isCreating}>
        {isCreating ? "Creating..." : "Create prompt"}
      </button>
    </form>
  );
}
