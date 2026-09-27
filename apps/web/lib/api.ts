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
