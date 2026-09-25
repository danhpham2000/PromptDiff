from pathlib import Path

import yaml

from promptdiff_cli.__main__ import EXIT_PASS, main


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
