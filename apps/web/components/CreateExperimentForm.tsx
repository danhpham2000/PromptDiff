"use client";

import { FormEvent, useEffect, useState } from "react";

import { createExperiment, Dataset, Experiment, listPromptVersions, Prompt, PromptVersion } from "../lib/api";

type CreateExperimentFormProps = {
  datasets: Dataset[];
  onCreated: (experiment: Experiment) => void;
  onError: (message: string) => void;
  projectId: string;
  prompts: Prompt[];
};

function latestVersionId(versions: PromptVersion[]) {
  return versions.at(-1)?.id || "";
}

export function CreateExperimentForm({ datasets, onCreated, onError, projectId, prompts }: CreateExperimentFormProps) {
  const [name, setName] = useState("web-comparison");
  const [baselinePromptId, setBaselinePromptId] = useState("");
  const [candidatePromptId, setCandidatePromptId] = useState("");
  const [baselineVersions, setBaselineVersions] = useState<PromptVersion[]>([]);
  const [candidateVersions, setCandidateVersions] = useState<PromptVersion[]>([]);
  const [baselineVersionId, setBaselineVersionId] = useState("");
  const [candidateVersionId, setCandidateVersionId] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [provider, setProvider] = useState<"mock" | "groq">("mock");
  const [model, setModel] = useState("mock-support");
  const [repetitions, setRepetitions] = useState(1);
  const [timeoutSeconds, setTimeoutSeconds] = useState(60);
  const [useToolGate, setUseToolGate] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (!prompts.length) {
      setBaselinePromptId("");
      setCandidatePromptId("");
      return;
    }
    setBaselinePromptId((current) => (prompts.some((prompt) => prompt.id === current) ? current : prompts[0].id));
    setCandidatePromptId((current) => (prompts.some((prompt) => prompt.id === current) ? current : prompts[1]?.id || prompts[0].id));
  }, [prompts]);

  useEffect(() => {
    setDatasetId((current) => (datasets.some((dataset) => dataset.id === current) ? current : datasets[0]?.id || ""));
  }, [datasets]);

  useEffect(() => {
    if (!baselinePromptId) {
      setBaselineVersions([]);
      setBaselineVersionId("");
      return;
    }
    let isCurrentPrompt = true;
    async function loadVersions() {
      try {
        const versions = await listPromptVersions(baselinePromptId);
        if (isCurrentPrompt) {
          setBaselineVersions(versions);
          setBaselineVersionId(latestVersionId(versions));
        }
      } catch (error) {
        if (isCurrentPrompt) {
          onError(error instanceof Error ? error.message : "Could not load baseline versions.");
        }
      }
    }
    void loadVersions();
    return () => {
      isCurrentPrompt = false;
    };
  }, [baselinePromptId, onError]);

  useEffect(() => {
    if (!candidatePromptId) {
      setCandidateVersions([]);
      setCandidateVersionId("");
      return;
    }
    let isCurrentPrompt = true;
    async function loadVersions() {
      try {
        const versions = await listPromptVersions(candidatePromptId);
        if (isCurrentPrompt) {
          setCandidateVersions(versions);
          setCandidateVersionId(latestVersionId(versions));
        }
      } catch (error) {
        if (isCurrentPrompt) {
          onError(error instanceof Error ? error.message : "Could not load candidate versions.");
        }
      }
    }
    void loadVersions();
    return () => {
      isCurrentPrompt = false;
    };
  }, [candidatePromptId, onError]);

  function handleProviderChange(nextProvider: "mock" | "groq") {
    setProvider(nextProvider);
    setModel(nextProvider === "mock" ? "mock-support" : "llama-3.1-8b-instant");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      onError("Experiment name is required.");
      return;
    }
    if (!baselineVersionId || !candidateVersionId) {
      onError("Baseline and candidate prompt versions are required.");
      return;
    }
    if (!datasetId) {
      onError("Dataset is required.");
      return;
    }

    setIsCreating(true);
    onError("");
    try {
      const experiment = await createExperiment({
        project_id: projectId,
        name: name.trim(),
        baseline_prompt_version_id: baselineVersionId,
        candidate_prompt_version_id: candidateVersionId,
        dataset_id: datasetId,
        provider,
        model: model.trim() || (provider === "mock" ? "mock-support" : "llama-3.1-8b-instant"),
        repetitions,
        timeout_seconds: timeoutSeconds,
        concurrency: 5,
        evaluators: useToolGate ? [{ name: "tool-selection", type: "tool_selection", category: "tool", hard_gate: true, required: true }] : [],
        regression: {},
      });
      onCreated(experiment);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not create experiment.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit}>
      <label>
        Experiment name
        <input maxLength={200} onChange={(event) => setName(event.target.value)} value={name} />
      </label>

      <div className="two-column">
        <label>
          Baseline prompt
          <select onChange={(event) => setBaselinePromptId(event.target.value)} value={baselinePromptId}>
            {prompts.map((prompt) => (
              <option key={prompt.id} value={prompt.id}>
                {prompt.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Candidate prompt
          <select onChange={(event) => setCandidatePromptId(event.target.value)} value={candidatePromptId}>
            {prompts.map((prompt) => (
              <option key={prompt.id} value={prompt.id}>
                {prompt.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="two-column">
        <label>
          Baseline version
          <select onChange={(event) => setBaselineVersionId(event.target.value)} value={baselineVersionId}>
            {baselineVersions.map((version) => (
              <option key={version.id} value={version.id}>
                Version {version.version_number}
              </option>
            ))}
          </select>
        </label>
        <label>
          Candidate version
          <select onChange={(event) => setCandidateVersionId(event.target.value)} value={candidateVersionId}>
            {candidateVersions.map((version) => (
              <option key={version.id} value={version.id}>
                Version {version.version_number}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label>
        Dataset
        <select onChange={(event) => setDatasetId(event.target.value)} value={datasetId}>
          {datasets.map((dataset) => (
            <option key={dataset.id} value={dataset.id}>
              {dataset.name}
            </option>
          ))}
        </select>
      </label>

      <div className="two-column">
        <label>
          Provider
          <select onChange={(event) => handleProviderChange(event.target.value as "mock" | "groq")} value={provider}>
            <option value="mock">mock</option>
            <option value="groq">groq</option>
          </select>
        </label>
        <label>
          Model
          <input onChange={(event) => setModel(event.target.value)} value={model} />
        </label>
      </div>

      <div className="two-column">
        <label>
          Repetitions
          <input min={1} max={5} onChange={(event) => setRepetitions(Number(event.target.value) || 1)} type="number" value={repetitions} />
        </label>
        <label>
          Timeout seconds
          <input min={5} max={300} onChange={(event) => setTimeoutSeconds(Number(event.target.value) || 60)} type="number" value={timeoutSeconds} />
        </label>
      </div>

      <label className="checkbox-row">
        <input checked={useToolGate} onChange={(event) => setUseToolGate(event.target.checked)} type="checkbox" />
        Use tool-selection hard gate
      </label>

      <button type="submit" disabled={isCreating || !prompts.length || !datasets.length}>
        {isCreating ? "Running..." : "Run experiment"}
      </button>
    </form>
  );
}
