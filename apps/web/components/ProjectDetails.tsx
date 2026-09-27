import { Project } from "../lib/api";

type ProjectDetailsProps = {
  project: Project | null;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ProjectDetails({ project }: ProjectDetailsProps) {
  if (!project) {
    return (
      <section className="panel stack">
        <div className="section-heading">
          <h2>Project</h2>
          <p>Select a project to view its details.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel stack">
      <div className="section-heading">
        <h2>{project.name}</h2>
        <p>{project.description || "No description"}</p>
      </div>

      <dl className="detail-list">
        <div>
          <dt>Slug</dt>
          <dd>{project.slug}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDate(project.created_at)}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatDate(project.updated_at)}</dd>
        </div>
      </dl>
    </section>
  );
}
