const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export type Project = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectCreateInput = {
  name: string;
  slug?: string;
  description?: string;
};

export type Prompt = {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
};

export type PromptCreateInput = {
  project_id: string;
  name: string;
  description?: string;
};

export type PromptVersion = {
  id: string;
  prompt_id: string;
  version_number: number;
  system_prompt: string | null;
  user_template: string | null;
  tool_definitions: Record<string, unknown>[] | null;
  metadata_json: Record<string, unknown> | null;
  schema_version: number;
  content_hash: string;
  created_at: string;
};

export type PromptVersionCreateInput = {
  system_prompt?: string;
  user_template?: string;
  tool_definitions?: Record<string, unknown>[];
  metadata?: Record<string, unknown>;
  schema_version?: number;
};

export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
};

export type DatasetCreateInput = {
  project_id: string;
  name: string;
  description?: string;
};

export type DatasetImportInput = {
  project_id: string;
  content: string;
  format: "yaml" | "json";
};

export type DatasetCase = {
  id: string;
  dataset_id: string;
  name: string | null;
  input: Record<string, unknown>;
  expected_output: Record<string, unknown> | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
};

export type DatasetCaseCreateInput = {
  name?: string;
  input: Record<string, unknown>;
  expected_output?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type EvaluatorConfig = {
  name: string;
  type: string;
  category?: string;
  weight?: number;
  include_in_quality_score?: boolean;
  required?: boolean;
  threshold?: number;
  hard_gate?: boolean;
};

export type Experiment = {
  id: string;
  project_id: string;
  name: string;
  status: string;
  verdict: string | null;
  dataset_snapshot_id: string | null;
  created_at: string;
  completed_at: string | null;
};

export type ExperimentCreateInput = {
  project_id: string;
  name: string;
  baseline_prompt_version_id: string;
  candidate_prompt_version_id: string;
  dataset_id: string;
  provider: "mock" | "groq";
  model: string;
  repetitions: number;
  timeout_seconds: number;
  concurrency?: number;
  evaluators?: EvaluatorConfig[];
  regression?: Record<string, unknown>;
};

export type ComparisonItem = {
  id: string;
  baseline_run_id: string;
  candidate_run_id: string;
  output_diff: unknown;
  tool_diff: unknown;
  token_delta: number | null;
  latency_delta_ms: number | null;
  cost_delta_usd: number | null;
  regression_status: string | null;
};

export type ExperimentComparison = {
  experiment: {
    id: string;
    status: string;
    verdict: string | null;
  };
  items: ComparisonItem[];
};

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "content-type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listProjects(): Promise<Project[]> {
  return apiRequest<Project[]>("/api/v1/projects");
}

export function createProject(input: ProjectCreateInput): Promise<Project> {
  return apiRequest<Project>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listPrompts(projectId: string): Promise<Prompt[]> {
  return apiRequest<Prompt[]>(`/api/v1/prompts?project_id=${encodeURIComponent(projectId)}`);
}

export function createPrompt(input: PromptCreateInput): Promise<Prompt> {
  return apiRequest<Prompt>("/api/v1/prompts", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listPromptVersions(promptId: string): Promise<PromptVersion[]> {
  return apiRequest<PromptVersion[]>(`/api/v1/prompts/${encodeURIComponent(promptId)}/versions`);
}

export function createPromptVersion(promptId: string, input: PromptVersionCreateInput): Promise<PromptVersion> {
  return apiRequest<PromptVersion>(`/api/v1/prompts/${encodeURIComponent(promptId)}/versions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listDatasets(projectId: string): Promise<Dataset[]> {
  return apiRequest<Dataset[]>(`/api/v1/datasets?project_id=${encodeURIComponent(projectId)}`);
}

export function createDataset(input: DatasetCreateInput): Promise<Dataset> {
  return apiRequest<Dataset>("/api/v1/datasets", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function importDataset(input: DatasetImportInput): Promise<Dataset> {
  return apiRequest<Dataset>("/api/v1/datasets/import", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listDatasetCases(datasetId: string): Promise<DatasetCase[]> {
  return apiRequest<DatasetCase[]>(`/api/v1/datasets/${encodeURIComponent(datasetId)}/cases`);
}

export function createDatasetCase(datasetId: string, input: DatasetCaseCreateInput): Promise<DatasetCase> {
  return apiRequest<DatasetCase>(`/api/v1/datasets/${encodeURIComponent(datasetId)}/cases`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listExperiments(projectId: string): Promise<Experiment[]> {
  return apiRequest<Experiment[]>(`/api/v1/experiments?project_id=${encodeURIComponent(projectId)}`);
}

export function createExperiment(input: ExperimentCreateInput): Promise<Experiment> {
  return apiRequest<Experiment>("/api/v1/experiments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function cancelExperiment(experimentId: string): Promise<{ id: string; status: string }> {
  return apiRequest<{ id: string; status: string }>(`/api/v1/experiments/${encodeURIComponent(experimentId)}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason: "cancelled_from_web" }),
  });
}

export function getExperimentComparison(experimentId: string): Promise<ExperimentComparison> {
  return apiRequest<ExperimentComparison>(`/api/v1/experiments/${encodeURIComponent(experimentId)}/comparison`);
}

export function experimentExportUrl(experimentId: string, format: "json" | "markdown" | "csv" | "junit") {
  return `${API_BASE_URL}/api/v1/experiments/${encodeURIComponent(experimentId)}/export?format=${encodeURIComponent(format)}`;
}
