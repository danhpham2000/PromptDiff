
import yaml
from promptdiff_cli.__main__ import EXIT_CONFIG, EXIT_PASS, main


def write_valid_project(tmp_path, provider: str) -> str:
    (tmp_path / "prompts").mkdir(parents=True)
    (tmp_path / "datasets").mkdir()
    (tmp_path / "prompts" / "a.md").write_text("baseline")
    (tmp_path / "prompts" / "b.md").write_text("candidate")
    (tmp_path / "datasets" / "cases.yaml").write_text("name: cases\ncases: []\n")
    config = {
        "schema_version": 1,
        "project": {"name": "demo"},
        "providers": {"default": {"name": provider, "model": "mock-support"}},
        "baseline": {"prompt": "prompts/a.md"},
        "candidate": {"prompt": "prompts/b.md"},
        "dataset": {"path": "datasets/cases.yaml"},
    }
    config_path = tmp_path / "promptdiff.yaml"
    config_path.write_text(yaml.safe_dump(config))
    return str(config_path)


def test_config_export_prints_config(tmp_path, capsys):
    config = {
        "schema_version": 1,
        "project": {"name": "demo"},
        "providers": {"default": {"name": "mock", "model": "mock-support"}},
        "baseline": {"prompt": "prompts/a.md"},
        "candidate": {"prompt": "prompts/b.md"},
        "dataset": {"path": "datasets/cases.yaml"},
    }
    (tmp_path / "promptdiff.yaml").write_text(yaml.safe_dump(config))

    assert main(["config", "export", "--config", str(tmp_path / "promptdiff.yaml")]) == EXIT_PASS
    assert yaml.safe_load(capsys.readouterr().out) == config


def test_config_export_redacts_secrets(tmp_path, capsys):
    config = {
        "schema_version": 1,
        "project": {"name": "demo"},
        "providers": {"default": {"name": "groq", "model": "llama-3.1-8b-instant", "api_key": "gsk_secret12345678901234567890"}},
        "baseline": {"prompt": "prompts/a.md"},
        "candidate": {"prompt": "prompts/b.md"},
        "dataset": {"path": "datasets/cases.yaml"},
    }
    (tmp_path / "promptdiff.yaml").write_text(yaml.safe_dump(config))

    assert main(["config", "export", "--config", str(tmp_path / "promptdiff.yaml")]) == EXIT_PASS
    exported = yaml.safe_load(capsys.readouterr().out)

    assert exported["providers"]["default"]["api_key"] == "[REDACTED]"


def test_validate_accepts_mock_and_groq(tmp_path, capsys):
    assert main(["validate", "--config", write_valid_project(tmp_path / "mock", "mock")]) == EXIT_PASS
    assert main(["validate", "--config", write_valid_project(tmp_path / "groq", "groq")]) == EXIT_PASS

    assert capsys.readouterr().out == "OK\nOK\n"


def test_validate_rejects_openai_and_anthropic(tmp_path, capsys):
    assert main(["validate", "--config", write_valid_project(tmp_path / "openai", "openai")]) == EXIT_CONFIG
    assert main(["validate", "--config", write_valid_project(tmp_path / "anthropic", "anthropic")]) == EXIT_CONFIG

    assert "provider must be one of: mock, groq" in capsys.readouterr().err
