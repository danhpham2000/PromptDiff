"use client";

import { FormEvent, useState } from "react";

import { createPromptVersion, PromptVersion } from "../lib/api";

type CreatePromptVersionFormProps = {
  onCreated: (version: PromptVersion) => void;
  onError: (message: string) => void;
  promptId: string;
};

function parseJsonField<T>(label: string, value: string, fallback: T): T {
  const trimmed = value.trim();
  if (!trimmed) {
    return fallback;
  }

  try {
    return JSON.parse(trimmed) as T;
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
}

export function CreatePromptVersionForm({ onCreated, onError, promptId }: CreatePromptVersionFormProps) {
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userTemplate, setUserTemplate] = useState("");
  const [toolDefinitions, setToolDefinitions] = useState("[]");
  const [metadata, setMetadata] = useState("{}");
  const [schemaVersion, setSchemaVersion] = useState(1);
  const [isCreating, setIsCreating] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    let parsedTools: Record<string, unknown>[];
    let parsedMetadata: Record<string, unknown>;

    try {
      parsedTools = parseJsonField<Record<string, unknown>[]>("Tool definitions", toolDefinitions, []);
      parsedMetadata = parseJsonField<Record<string, unknown>>("Metadata", metadata, {});
      if (!Array.isArray(parsedTools)) {
        onError("Tool definitions must be a JSON array.");
        return;
      }
      if (Array.isArray(parsedMetadata) || parsedMetadata === null || typeof parsedMetadata !== "object") {
        onError("Metadata must be a JSON object.");
        return;
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : "Invalid JSON.");
      return;
    }

    setIsCreating(true);
    onError("");
    try {
      const version = await createPromptVersion(promptId, {
        system_prompt: systemPrompt,
        user_template: userTemplate,
        tool_definitions: parsedTools,
        metadata: parsedMetadata,
        schema_version: schemaVersion,
      });
      onCreated(version);
      setSystemPrompt("");
      setUserTemplate("");
      setToolDefinitions("[]");
      setMetadata("{}");
      setSchemaVersion(1);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not create prompt version.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <form className="version-form" onSubmit={handleSubmit}>
      <label>
        System prompt
        <textarea
          maxLength={100000}
          onChange={(event) => setSystemPrompt(event.target.value)}
          placeholder="You are a support agent..."
          rows={4}
          value={systemPrompt}
        />
      </label>

      <label>
        User template
        <textarea
          maxLength={100000}
          onChange={(event) => setUserTemplate(event.target.value)}
          placeholder="{{message}}"
          rows={3}
          value={userTemplate}
        />
      </label>

      <div className="two-column">
        <label>
          Tool definitions JSON
          <textarea onChange={(event) => setToolDefinitions(event.target.value)} rows={4} value={toolDefinitions} />
        </label>
        <label>
          Metadata JSON
          <textarea onChange={(event) => setMetadata(event.target.value)} rows={4} value={metadata} />
        </label>
      </div>

      <label>
        Schema version
        <input min={1} onChange={(event) => setSchemaVersion(Number(event.target.value) || 1)} type="number" value={schemaVersion} />
      </label>

      <button type="submit" disabled={isCreating}>
        {isCreating ? "Creating..." : "Create version"}
      </button>
    </form>
  );
}
