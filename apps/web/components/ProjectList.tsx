import { Project } from "../lib/api";

type ProjectListProps = {
  isLoading: boolean;
  onSelectProject: (projectId: string) => void;
  projects: Project[];
  selectedProjectId: string | null;
  onRefresh: () => void;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function ProjectList({ isLoading, onSelectProject, projects, selectedProjectId, onRefresh }: ProjectListProps) {
  return (
    <section className="panel stack">
      <div className="list-header">
        <div className="section-heading">
          <h2>Projects</h2>
          <p>{projects.length ? `${projects.length} project${projects.length === 1 ? "" : "s"}` : "No projects yet"}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {isLoading && !projects.length ? <div className="empty-state">Loading projects...</div> : null}

      {!isLoading && !projects.length ? (
        <div className="empty-state">
          <strong>No projects yet</strong>
          <span>Create your first project to begin tracking prompt changes.</span>
        </div>
      ) : null}

      {projects.length ? (
        <div className="project-list" aria-label="Projects">
          {projects.map((project) => (
            <button
              aria-pressed={project.id === selectedProjectId}
              className={`project-row ${project.id === selectedProjectId ? "selected" : ""}`}
              key={project.id}
              onClick={() => onSelectProject(project.id)}
              type="button"
            >
              <span className="project-main">
                <strong>{project.name}</strong>
                <span>{project.description || "No description"}</span>
              </span>
              <span className="project-meta" aria-label={`${project.slug}, created ${formatDate(project.created_at)}`}>
                <span>
                  <span>Slug</span>
                  <strong>{project.slug}</strong>
                </span>
                <span>
                  <span>Created</span>
                  <strong>{formatDate(project.created_at)}</strong>
                </span>
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
