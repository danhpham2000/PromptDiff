"use client";

import { useCallback, useEffect, useState } from "react";

import { CreateProjectForm } from "../components/CreateProjectForm";
import { ProjectDetails } from "../components/ProjectDetails";
import { ProjectList } from "../components/ProjectList";
import { PromptList } from "../components/PromptList";
import { listProjects, listPrompts, Project, Prompt } from "../lib/api";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingPrompts, setIsLoadingPrompts] = useState(false);
  const [error, setError] = useState("");

  const refreshProjects = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      setProjects(await listProjects());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load projects.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    if (!projects.length) {
      setSelectedProjectId(null);
      return;
    }
    if (!projects.some((project) => project.id === selectedProjectId)) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const refreshPrompts = useCallback(async () => {
    if (!selectedProjectId) {
      setPrompts([]);
      return;
    }

    setIsLoadingPrompts(true);
    setError("");
    try {
      setPrompts(await listPrompts(selectedProjectId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load prompts.");
    } finally {
      setIsLoadingPrompts(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    let isCurrentProject = true;
    async function loadSelectedProjectPrompts() {
      if (!selectedProjectId) {
        setPrompts([]);
        return;
      }

      setPrompts([]);
      setIsLoadingPrompts(true);
      setError("");
      try {
        const nextPrompts = await listPrompts(selectedProjectId);
        if (isCurrentProject) {
          setPrompts(nextPrompts);
        }
      } catch (requestError) {
        if (isCurrentProject) {
          setError(requestError instanceof Error ? requestError.message : "Could not load prompts.");
        }
      } finally {
        if (isCurrentProject) {
          setIsLoadingPrompts(false);
        }
      }
    }

    void loadSelectedProjectPrompts();
    return () => {
      isCurrentProject = false;
    };
  }, [selectedProjectId]);

  function handleProjectCreated(project: Project) {
    setProjects((currentProjects) => [project, ...currentProjects.filter((item) => item.id !== project.id)]);
    setSelectedProjectId(project.id);
  }

  function handlePromptCreated(prompt: Prompt) {
    setPrompts((currentPrompts) => [prompt, ...currentPrompts.filter((item) => item.id !== prompt.id)]);
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) || null;

  return (
    <main>
      <header className="app-header">
        <div>
          <p className="eyebrow">Local v0.1</p>
          <h1>PromptDiff</h1>
          <p>Track prompt versions, datasets, experiments, and regression gates.</p>
        </div>
      </header>

      {error ? (
        <div className="alert" role="alert">
          <strong>Request failed</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="dashboard-grid">
        <ProjectList
          isLoading={isLoading}
          onSelectProject={setSelectedProjectId}
          projects={projects}
          selectedProjectId={selectedProjectId}
          onRefresh={refreshProjects}
        />
        <aside className="side-stack">
          <ProjectDetails project={selectedProject} />
          <PromptList
            isLoading={isLoadingPrompts}
            onCreated={handlePromptCreated}
            onError={setError}
            onRefresh={refreshPrompts}
            projectId={selectedProjectId}
            prompts={prompts}
          />
          <CreateProjectForm onCreated={handleProjectCreated} onError={setError} />
        </aside>
      </div>
    </main>
  );
}
