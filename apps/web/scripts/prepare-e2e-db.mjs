import { existsSync, unlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDir, "..");
const repoRoot = resolve(webRoot, "../..");
const dbPath = join(webRoot, "promptdiff_e2e.db");
const python = process.env.PYTHON || join(repoRoot, ".venv/bin/python");

if (existsSync(dbPath)) {
  unlinkSync(dbPath);
}

const result = spawnSync(
  python,
  [
    "-c",
    [
      "from app.db import engine",
      "from app.models import Base",
      "Base.metadata.create_all(bind=engine)",
      "print('e2e database ready')",
    ].join("; "),
  ],
  {
    cwd: repoRoot,
    env: {
      ...process.env,
      PROMPTDIFF_MODE: "local",
      DATABASE_URL: "sqlite:///./apps/web/promptdiff_e2e.db",
      PYTHONPATH: "apps/api",
    },
    stdio: "inherit",
  },
);

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}
