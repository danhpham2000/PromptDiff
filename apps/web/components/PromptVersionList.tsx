import { Prompt, PromptVersion } from "../lib/api";
import { CreatePromptVersionForm } from "./CreatePromptVersionForm";
import { PromptVersionDiff } from "./PromptVersionDiff";

type PromptVersionListProps = {
  isLoading: boolean;
  onCreated: (version: PromptVersion) => void;
  onError: (message: string) => void;
  onRefresh: () => void;
  prompt: Prompt | null;
  versions: PromptVersion[];
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function preview(value: string | null) {
  const normalized = (value || "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "Empty";
  }
  return normalized.length > 160 ? `${normalized.slice(0, 157)}...` : normalized;
}

export function PromptVersionList({ isLoading, onCreated, onError, onRefresh, prompt, versions }: PromptVersionListProps) {
  if (!prompt) {
    return (
      <section className="panel stack">
        <div className="section-heading">
          <h2>Versions</h2>
          <p>Select a prompt to manage immutable versions.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel stack">
      <div className="list-header">
        <div className="section-heading">
          <h2>Versions</h2>
          <p>
            {prompt.name}: {versions.length ? `${versions.length} version${versions.length === 1 ? "" : "s"}` : "No versions yet"}
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <CreatePromptVersionForm promptId={prompt.id} onCreated={onCreated} onError={onError} />

      {isLoading && !versions.length ? <div className="empty-state compact">Loading versions...</div> : null}

      {!isLoading && !versions.length ? (
        <div className="empty-state compact">
          <strong>No versions yet</strong>
          <span>Create a version to lock prompt behavior for experiments.</span>
        </div>
      ) : null}

      {versions.length ? (
        <div className="version-list" aria-label="Prompt versions">
          {versions.map((version) => (
            <article className="version-row" key={version.id}>
              <div className="version-header">
                <strong>Version {version.version_number}</strong>
                <span>Created {formatDate(version.created_at)}</span>
              </div>
              <dl className="version-meta">
                <div>
                  <dt>Hash</dt>
                  <dd>{version.content_hash.slice(0, 12)}</dd>
                </div>
                <div>
                  <dt>Schema</dt>
                  <dd>{version.schema_version}</dd>
                </div>
              </dl>
              <div className="version-preview">
                <span>System</span>
                <p>{preview(version.system_prompt)}</p>
              </div>
              <div className="version-preview">
                <span>User</span>
                <p>{preview(version.user_template)}</p>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {versions.length ? <PromptVersionDiff versions={versions} /> : null}
    </section>
  );
}
