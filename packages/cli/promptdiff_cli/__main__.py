import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml

DEFAULT_API = "http://localhost:8000"

EXIT_PASS = 0
EXIT_REGRESSION = 1
EXIT_CONFIG = 2
EXIT_PROVIDER = 3
EXIT_CANCELLED = 4
EXIT_AUTH = 5
EXIT_INTERNAL = 10


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"config not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    for key in ["project", "providers", "baseline", "candidate", "dataset"]:
        if key not in data:
            raise ValueError(f"missing required key: {key}")
    return data


def validate_paths(config: dict[str, Any], base: Path) -> None:
    for section in ["baseline", "candidate", "dataset"]:
        path = base / config[section]["prompt"] if section in {"baseline", "candidate"} else base / config[section]["path"]
        if not path.exists():
            raise ValueError(f"{section} path not found: {path}")


def init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    for name in ["prompts", "datasets", ".promptdiff", ".promptdiff/results", ".promptdiff/runs", ".promptdiff/cache"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    config_path = root / "promptdiff.yaml"
    if config_path.exists() and not args.force:
        print("promptdiff.yaml already exists; use --force to overwrite", file=sys.stderr)
        return EXIT_CONFIG
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": {"name": root.name},
                "providers": {"default": {"name": "mock", "model": "mock-support"}},
                "baseline": {"prompt": "prompts/baseline.md"},
                "candidate": {"prompt": "prompts/candidate.md"},
                "dataset": {"path": "datasets/cases.yaml"},
                "evaluators": [],
                "execution": {"repetitions": 1, "concurrency": 5, "timeout_seconds": 60},
                "regression": {},
                "output": {"directory": ".promptdiff/results", "formats": ["json", "markdown"]},
            },
            sort_keys=False,
        )
    )
    return EXIT_PASS


def validate(args: argparse.Namespace) -> int:
    try:
        config = load_config(Path(args.config))
        validate_paths(config, Path(args.config).resolve().parent)
        print("OK")
        return EXIT_PASS
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_CONFIG


def run(args: argparse.Namespace) -> int:
    try:
        config_path = Path(args.config)
        config = load_config(config_path)
        base = config_path.resolve().parent
        validate_paths(config, base)
        api = args.api_url
        with httpx.Client(base_url=api, timeout=120) as client:
            project = client.post("/api/v1/projects", json={"name": config["project"]["name"]}).raise_for_status()
            project_id = project.json()["id"]

            baseline_prompt_id = client.post("/api/v1/prompts", json={"project_id": project_id, "name": "baseline"}).raise_for_status().json()["id"]
            candidate_prompt_id = client.post("/api/v1/prompts", json={"project_id": project_id, "name": "candidate"}).raise_for_status().json()["id"]
            baseline_text = (base / config["baseline"]["prompt"]).read_text()
            candidate_text = (base / config["candidate"]["prompt"]).read_text()
            baseline_version = client.post(
                f"/api/v1/prompts/{baseline_prompt_id}/versions",
                json={"system_prompt": baseline_text, "user_template": "{{message}}", "tool_definitions": [], "metadata": {}},
            ).raise_for_status().json()
            candidate_version = client.post(
                f"/api/v1/prompts/{candidate_prompt_id}/versions",
                json={"system_prompt": candidate_text, "user_template": "{{message}}", "tool_definitions": [], "metadata": {}},
            ).raise_for_status().json()
            dataset_content = (base / config["dataset"]["path"]).read_text()
            dataset = client.post(
                "/api/v1/datasets/import",
                json={"project_id": project_id, "content": dataset_content, "format": "yaml"},
            ).raise_for_status().json()
            provider = config["providers"]["default"]
            execution = config.get("execution", {})
            experiment = client.post(
                "/api/v1/experiments",
                json={
                    "project_id": project_id,
                    "name": "cli-run",
                    "baseline_prompt_version_id": baseline_version["id"],
                    "candidate_prompt_version_id": candidate_version["id"],
                    "dataset_id": dataset["id"],
                    "provider": provider.get("name", "mock"),
                    "model": provider.get("model", "mock-support"),
                    "temperature": provider.get("temperature"),
                    "max_tokens": provider.get("max_tokens"),
                    "repetitions": execution.get("repetitions", 1),
                    "concurrency": execution.get("concurrency", 5),
                    "timeout_seconds": execution.get("timeout_seconds", 60),
                    "evaluators": config.get("evaluators", []),
                    "regression": config.get("regression", {}),
                },
            ).raise_for_status().json()
            result = client.get(f"/api/v1/experiments/{experiment['id']}/comparison").raise_for_status().json()
        out_dir = base / config.get("output", {}).get("directory", ".promptdiff/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{experiment['id']}.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({"experiment_id": experiment["id"], "verdict": experiment["verdict"]}, indent=2))
        if experiment["verdict"] == "FAIL":
            return EXIT_REGRESSION
        if experiment["verdict"] == "CANCELLED":
            return EXIT_CANCELLED
        if experiment["verdict"] == "ERROR":
            return EXIT_PROVIDER
        return EXIT_PASS
    except httpx.HTTPStatusError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_AUTH if exc.response.status_code in {401, 403} else EXIT_PROVIDER
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_CONFIG
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INTERNAL


def doctor(args: argparse.Namespace) -> int:
    try:
        response = httpx.get(f"{args.api_url}/health", timeout=5)
        response.raise_for_status()
        print(response.text)
        return EXIT_PASS
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_PROVIDER


def export_config(args: argparse.Namespace) -> int:
    try:
        config = load_config(Path(args.config))
        print(yaml.safe_dump(config, sort_keys=False), end="")
        return EXIT_PASS
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_CONFIG


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="promptdiff")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--force", action="store_true")
    init_p.set_defaults(func=init)

    for name, func in [("validate", validate), ("run", run), ("test", run), ("compare", run)]:
        p = sub.add_parser(name)
        p.add_argument("--config", default="promptdiff.yaml")
        p.add_argument("--api-url", default=DEFAULT_API)
        p.set_defaults(func=func)

    p = sub.add_parser("export")
    p.add_argument("--config", default="promptdiff.yaml")
    p.add_argument("--api-url", default=DEFAULT_API)
    p.set_defaults(func=run)

    p = sub.add_parser("config")
    p.add_argument("action", choices=["export"])
    p.add_argument("--config", default="promptdiff.yaml")
    p.set_defaults(func=export_config)

    p = sub.add_parser("doctor")
    p.add_argument("--api-url", default=DEFAULT_API)
    p.set_defaults(func=doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
