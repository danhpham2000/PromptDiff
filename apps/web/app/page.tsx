"use client";

import { useCallback, useEffect, useState } from "react";

import { CreateProjectForm } from "../components/CreateProjectForm";
import { DatasetCaseList } from "../components/DatasetCaseList";
import { DatasetList } from "../components/DatasetList";
import { ProjectDetails } from "../components/ProjectDetails";
import { ProjectList } from "../components/ProjectList";
import { PromptList } from "../components/PromptList";
import { PromptVersionList } from "../components/PromptVersionList";
import {
  Dataset,
  DatasetCase,
  listDatasetCases,
  listDatasets,
  listProjects,
  listPrompts,
  listPromptVersions,
  Project,
  Prompt,
  PromptVersion,
} from "../lib/api";

type ProjectPanel = "prompts" | "datasets";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [promptVersions, setPromptVersions] = useState<PromptVersion[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetCases, setDatasetCases] = useState<DatasetCase[]>([]);
  const [activePanel, setActivePanel] = useState<ProjectPanel>("prompts");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingPrompts, setIsLoadingPrompts] = useState(false);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
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
        setSelectedPromptId(null);
        setPromptVersions([]);
        setDatasets([]);
        setSelectedDatasetId(null);
        setDatasetCases([]);
        return;
      }

      setPrompts([]);
      setSelectedPromptId(null);
      setPromptVersions([]);
      setIsLoadingPrompts(true);
      setError("");
      try {
        const nextPrompts = await listPrompts(selectedProjectId);
        if (isCurrentProject) {
          setPrompts(nextPrompts);
          setSelectedPromptId(nextPrompts[0]?.id || null);
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

  const refreshDatasets = useCallback(async () => {
    if (!selectedProjectId) {
      setDatasets([]);
      return;
    }

    setIsLoadingDatasets(true);
    setError("");
    try {
      setDatasets(await listDatasets(selectedProjectId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load datasets.");
    } finally {
      setIsLoadingDatasets(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    let isCurrentProject = true;
    async function loadSelectedProjectDatasets() {
      if (!selectedProjectId) {
        setDatasets([]);
        setSelectedDatasetId(null);
        setDatasetCases([]);
        return;
      }

      setDatasets([]);
      setSelectedDatasetId(null);
      setDatasetCases([]);
      setIsLoadingDatasets(true);
      setError("");
      try {
        const nextDatasets = await listDatasets(selectedProjectId);
        if (isCurrentProject) {
          setDatasets(nextDatasets);
          setSelectedDatasetId(nextDatasets[0]?.id || null);
        }
      } catch (requestError) {
        if (isCurrentProject) {
          setError(requestError instanceof Error ? requestError.message : "Could not load datasets.");
        }
      } finally {
        if (isCurrentProject) {
          setIsLoadingDatasets(false);
        }
      }
    }

    void loadSelectedProjectDatasets();
    return () => {
      isCurrentProject = false;
    };
  }, [selectedProjectId]);

  const refreshVersions = useCallback(async () => {
    if (!selectedPromptId) {
      setPromptVersions([]);
      return;
    }

    setIsLoadingVersions(true);
    setError("");
    try {
      setPromptVersions(await listPromptVersions(selectedPromptId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load prompt versions.");
    } finally {
      setIsLoadingVersions(false);
    }
  }, [selectedPromptId]);

  useEffect(() => {
    let isCurrentPrompt = true;
    async function loadSelectedPromptVersions() {
      if (!selectedPromptId) {
        setPromptVersions([]);
        return;
      }

      setPromptVersions([]);
      setIsLoadingVersions(true);
      setError("");
      try {
        const nextVersions = await listPromptVersions(selectedPromptId);
        if (isCurrentPrompt) {
          setPromptVersions(nextVersions);
        }
      } catch (requestError) {
        if (isCurrentPrompt) {
          setError(requestError instanceof Error ? requestError.message : "Could not load prompt versions.");
        }
      } finally {
        if (isCurrentPrompt) {
          setIsLoadingVersions(false);
        }
      }
    }

    void loadSelectedPromptVersions();
    return () => {
      isCurrentPrompt = false;
    };
  }, [selectedPromptId]);

  const refreshCases = useCallback(async () => {
    if (!selectedDatasetId) {
      setDatasetCases([]);
      return;
    }

    setIsLoadingCases(true);
    setError("");
    try {
      setDatasetCases(await listDatasetCases(selectedDatasetId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load dataset cases.");
    } finally {
      setIsLoadingCases(false);
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    let isCurrentDataset = true;
    async function loadSelectedDatasetCases() {
      if (!selectedDatasetId) {
        setDatasetCases([]);
        return;
      }

      setDatasetCases([]);
      setIsLoadingCases(true);
      setError("");
      try {
        const nextCases = await listDatasetCases(selectedDatasetId);
        if (isCurrentDataset) {
          setDatasetCases(nextCases);
        }
      } catch (requestError) {
        if (isCurrentDataset) {
          setError(requestError instanceof Error ? requestError.message : "Could not load dataset cases.");
        }
      } finally {
        if (isCurrentDataset) {
          setIsLoadingCases(false);
        }
      }
    }

    void loadSelectedDatasetCases();
    return () => {
      isCurrentDataset = false;
    };
  }, [selectedDatasetId]);

  function handleProjectCreated(project: Project) {
    setProjects((currentProjects) => [project, ...currentProjects.filter((item) => item.id !== project.id)]);
    setSelectedProjectId(project.id);
  }

  function handlePromptCreated(prompt: Prompt) {
    setPrompts((currentPrompts) => [prompt, ...currentPrompts.filter((item) => item.id !== prompt.id)]);
    setSelectedPromptId(prompt.id);
  }

  function handleVersionCreated(version: PromptVersion) {
    setPromptVersions((currentVersions) =>
      [...currentVersions.filter((item) => item.id !== version.id), version].sort((left, right) => left.version_number - right.version_number),
    );
  }

  function handleDatasetCreated(dataset: Dataset) {
    setDatasets((currentDatasets) => [dataset, ...currentDatasets.filter((item) => item.id !== dataset.id)]);
    setSelectedDatasetId(dataset.id);
    setActivePanel("datasets");
  }

  function handleDatasetCaseCreated(datasetCase: DatasetCase) {
    setDatasetCases((currentCases) => [...currentCases, datasetCase]);
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) || null;
  const selectedPrompt = prompts.find((prompt) => prompt.id === selectedPromptId) || null;
  const selectedDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) || null;

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
          <div className="segmented-control" aria-label="Project resources">
            <button className={activePanel === "prompts" ? "active" : ""} onClick={() => setActivePanel("prompts")} type="button">
              Prompts
            </button>
            <button className={activePanel === "datasets" ? "active" : ""} onClick={() => setActivePanel("datasets")} type="button">
              Datasets
            </button>
          </div>
          {activePanel === "prompts" ? (
            <>
              <PromptList
                isLoading={isLoadingPrompts}
                onCreated={handlePromptCreated}
                onError={setError}
                onRefresh={refreshPrompts}
                onSelectPrompt={setSelectedPromptId}
                projectId={selectedProjectId}
                prompts={prompts}
                selectedPromptId={selectedPromptId}
              />
              <PromptVersionList
                isLoading={isLoadingVersions}
                onCreated={handleVersionCreated}
                onError={setError}
                onRefresh={refreshVersions}
                prompt={selectedPrompt}
                versions={promptVersions}
              />
            </>
          ) : (
            <>
              <DatasetList
                datasets={datasets}
                isLoading={isLoadingDatasets}
                onCreated={handleDatasetCreated}
                onError={setError}
                onRefresh={refreshDatasets}
                onSelectDataset={setSelectedDatasetId}
                projectId={selectedProjectId}
                selectedDatasetId={selectedDatasetId}
              />
              <DatasetCaseList
                cases={datasetCases}
                dataset={selectedDataset}
                isLoading={isLoadingCases}
                onCreated={handleDatasetCaseCreated}
                onError={setError}
                onRefresh={refreshCases}
              />
            </>
          )}
          <CreateProjectForm onCreated={handleProjectCreated} onError={setError} />
        </aside>
      </div>
    </main>
  );
}
