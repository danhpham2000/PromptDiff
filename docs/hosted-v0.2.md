# Hosted v0.2 Boundary

Hosted mode starts after the local v0.1 loop is stable.

Required services:

- Vercel for `apps/web`
- Railway for `apps/api` and a Python worker
- Neon Postgres and Neon Managed Better Auth
- Upstash Redis for queueing and locks

Do not route FastAPI auth directly through Neon JWTs. Next.js validates the Neon session, mints a short-lived PromptDiff Ed25519 JWT, and FastAPI validates that application JWT.

Provider secrets must never reach the browser. Store only AES-256-GCM ciphertext, nonce, key version, and key hint.

