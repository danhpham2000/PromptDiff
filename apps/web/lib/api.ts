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
