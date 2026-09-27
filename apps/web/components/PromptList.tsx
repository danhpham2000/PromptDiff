import { Prompt } from "../lib/api";
import { CreatePromptForm } from "./CreatePromptForm";

type PromptListProps = {
  isLoading: boolean;
  onCreated: (prompt: Prompt) => void;
  onError: (message: string) => void;
  onRefresh: () => void;
  onSelectPrompt: (promptId: string) => void;
  projectId: string | null;
  prompts: Prompt[];
  selectedPromptId: string | null;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function PromptList({ isLoading, onCreated, onError, onRefresh, onSelectPrompt, projectId, prompts, selectedPromptId }: PromptListProps) {
  if (!projectId) {
    return (
      <section className="panel stack">
        <div className="section-heading">
          <h2>Prompts</h2>
          <p>Select a project to manage prompts.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel stack">
      <div className="list-header">
        <div className="section-heading">
          <h2>Prompts</h2>
          <p>{prompts.length ? `${prompts.length} prompt${prompts.length === 1 ? "" : "s"}` : "No prompts yet"}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <CreatePromptForm projectId={projectId} onCreated={onCreated} onError={onError} />

      {isLoading && !prompts.length ? <div className="empty-state compact">Loading prompts...</div> : null}

      {!isLoading && !prompts.length ? (
        <div className="empty-state compact">
          <strong>No prompts yet</strong>
          <span>Create a prompt to start versioning behavior.</span>
        </div>
      ) : null}

      {prompts.length ? (
        <div className="prompt-list" aria-label="Prompts">
          {prompts.map((prompt) => (
            <button
              aria-pressed={prompt.id === selectedPromptId}
              className={`prompt-row ${prompt.id === selectedPromptId ? "selected" : ""}`}
              key={prompt.id}
              onClick={() => onSelectPrompt(prompt.id)}
              type="button"
            >
              <span>
                <strong>{prompt.name}</strong>
                <span>{prompt.description || "No description"}</span>
              </span>
              <span>Created {formatDate(prompt.created_at)}</span>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
