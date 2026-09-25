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

Local mode has no login and uses one implicit workspace. Hosted Neon/Upstash support is intentionally deferred to v0.2.

## CLI

```bash
python -m promptdiff_cli init
python -m promptdiff_cli validate --config promptdiff.yaml
python -m promptdiff_cli test --config promptdiff.yaml
```

