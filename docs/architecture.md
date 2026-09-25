# Architecture

PromptDiff v0.1 is local-first:

- FastAPI owns persistence and experiment execution.
- PostgreSQL stores projects, prompts, datasets, snapshots, runs, comparisons, and regression configs.
- Next.js is a thin UI over the API.
- The CLI reads `promptdiff.yaml` and can run deterministic local checks without hosted auth.

Hosted Neon Auth, Upstash Redis workers, RBAC, encrypted provider secrets, audit logs, and retention controls start in v0.2.

