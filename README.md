# PromptDiff

Git-style diffs for AI behavior.

PromptDiff compares prompt versions, model outputs, tool calls, latency, token usage, cost, and evaluator results so regressions are visible before deployment.

## Local v0.1

```bash
docker compose up
```

- Web: http://localhost:3000
- API: http://localhost:8000
- API health: http://localhost:8000/health

Local mode has no login and uses one implicit workspace. Docker Compose binds web, API, and Postgres to `127.0.0.1` only; do not expose the v0.1 API on a public network.

## Hosted v0.2 foundation

Hosted mode expects Neon Postgres, Neon Auth, and Upstash Redis settings from `.env.hosted.example`.

```bash
PROMPTDIFF_MODE=hosted
DATABASE_URL=postgresql+psycopg://...
NEON_AUTH_BASE_URL=...
NEON_AUTH_JWKS_URL=...
NEON_AUTH_AUDIENCE=...
UPSTASH_REDIS_REST_URL=...
UPSTASH_REDIS_REST_TOKEN=...
PROMPTDIFF_JWT_PRIVATE_KEY=...
PROMPTDIFF_JWT_PUBLIC_KEY=...
PROMPTDIFF_SECRET_ENCRYPTION_KEY=...
```

FastAPI accepts PromptDiff Ed25519 JWTs, scopes projects/prompts/datasets/experiments by workspace membership, stores Groq provider keys encrypted, writes audit events for hosted mutations, and queues hosted experiments to Upstash.

## CLI

```bash
python -m promptdiff_cli init
python -m promptdiff_cli validate --config promptdiff.yaml
python -m promptdiff_cli test --config promptdiff.yaml
```
