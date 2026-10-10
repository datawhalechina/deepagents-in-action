import json
import os
import subprocess
import sys
from pathlib import Path

import nbformat
import pytest

from course_notebooks.run import export_reading, run_entries, validate_catalog


def make_repo(tmp_path, sources):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/chapters.json").write_text(json.dumps({"ch01-agent-harness": {}}))
    entries = []
    for name, source in sources.items():
        relative = f"ch01/{name}.ipynb"
        path = tmp_path / "notebooks" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)]), path)
        entries.append({"id": name, "path": relative, "chapter_id": "ch01-agent-harness",
                        "title": name, "dependencies": [], "services": [], "model": "optional"})
    (tmp_path / "notebooks/catalog.json").write_text(json.dumps({"schema_version": 1, "notebooks": entries}))
    return entries


@pytest.mark.parametrize("export", [False, True])
def test_cli_preserves_unicode_without_utf8_mode(tmp_path, export):
    entries = make_repo(tmp_path, {"ok": "print('研究完成 🐳')"})
    (tmp_path / "scripts/chapters.json").write_text(
        json.dumps({"ch01-agent-harness": {"title": "智能体实验 🐳"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    entries[0]["title"] = "智能体实验 🐳"
    (tmp_path / "notebooks/catalog.json").write_text(
        json.dumps({"schema_version": 1, "notebooks": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    env = dict(os.environ, PYTHONUTF8="0", PYTHONCOERCECLOCALE="0",
               LC_ALL="C", PYTHONIOENCODING="utf-8")
    command = [sys.executable, "-X", "utf8=0", "-m", "course_notebooks.run", "ok"]
    result = subprocess.run(
        command + (["--write-back"] if export else ["--check-only"]),
        cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if export:
        for directory, stem in ((tmp_path / "artifacts/notebooks", "ok"),
                                (tmp_path / "notebooks/ch01", "ok")):
            for suffix in (".html", ".md"):
                assert "研究完成 🐳" in (directory / f"{stem}{suffix}").read_text(encoding="utf-8")
        checked = subprocess.run(
            command + ["--check-reading"], cwd=tmp_path, env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=90,
        )
        assert checked.returncode == 0, checked.stdout + checked.stderr


def test_project_kernel_ignores_user_kernel_and_offline_keys(tmp_path, monkeypatch):
    entries = make_repo(tmp_path, {"ok": f"import sys, os\nassert sys.executable == {sys.executable!r}\nassert not os.getenv('MODEL_API_KEY')\nassert os.getenv('COURSE_MODE') == 'offline'\nprint('isolated')"})
    bad = tmp_path / "foreign/kernels/course"
    bad.mkdir(parents=True)
    (bad / "kernel.json").write_text(json.dumps({"argv": ["/nonexistent/python", "{connection_file}"], "language": "python", "display_name": "bad"}))
    monkeypatch.setenv("JUPYTER_PATH", str(tmp_path / "foreign"))
    monkeypatch.setenv("MODEL_API_KEY", "must-not-reach-kernel")
    report = run_entries(entries, tmp_path, tmp_path / "output", mode="offline", timeout=30)
    assert report["results"][0]["status"] == "passed"
    assert (tmp_path / "output/ok.html").exists()
    assert (tmp_path / "output/ok.md").exists()
    assert report["results"][0]["source_hash"]


def test_failed_cell_stops_batch_and_does_not_reuse_saved_outputs(tmp_path):
    entries = make_repo(tmp_path, {"bad": "assert False, 'deliberate failure'", "later": "print('not run')"})
    report = run_entries(entries, tmp_path, tmp_path / "output", mode="offline", timeout=30)
    assert [r["status"] for r in report["results"]] == ["failed", "not_run"]
    saved = nbformat.read(tmp_path / "output/bad.ipynb", as_version=4)
    assert saved.cells[0].outputs[0].output_type == "error"
    assert not (tmp_path / "output/later.ipynb").exists()


def test_catalog_rejects_unknown_chapter_and_missing_local_link(tmp_path):
    entries = make_repo(tmp_path, {"ok": "print('ok')"})
    entries[0]["chapter_id"] = "ch99-missing"
    with pytest.raises(ValueError, match="chapter"):
        validate_catalog(tmp_path, entries)
    entries[0]["chapter_id"] = "ch01-agent-harness"
    path = tmp_path / "notebooks/ch01/ok.ipynb"
    nb = nbformat.read(path, as_version=4)
    nb.cells.append(nbformat.v4.new_markdown_cell("[missing](does-not-exist.md)"))
    nbformat.write(nb, path)
    with pytest.raises(ValueError, match="does-not-exist"):
        validate_catalog(tmp_path, entries)


def test_export_keeps_filename_label_when_resolving_relative_link(tmp_path):
    entries = make_repo(tmp_path, {"ok": "print('ok')"})
    path = tmp_path / "notebooks" / entries[0]["path"]
    nb = nbformat.read(path, as_version=4)
    nb.cells.append(nbformat.v4.new_markdown_cell("[local_server.py](local_server.py)"))
    nb.metadata["course_run"] = {"mode": "offline", "source_hash": "example-hash"}
    output = tmp_path / "output"
    output.mkdir()
    export_reading(nb, path, tmp_path, output, "ok", "test-commit")
    assert "[local_server.py](https://github.com/" in (output / "ok.md").read_text(encoding="utf-8")


def test_failed_batch_removes_previous_selected_artifacts(tmp_path):
    entries = make_repo(tmp_path, {"bad": "raise ValueError('failed')", "later": "print('later')"})
    output = tmp_path / "output"
    output.mkdir()
    for name in ("bad", "later"):
        for extension in ("ipynb", "html", "md"):
            (output / f"{name}.{extension}").write_text("stale success")
    report = run_entries(entries, tmp_path, output, mode="offline", timeout=30)
    assert report["results"][1]["status"] == "not_run"
    assert not (output / "later.html").exists()
    assert not (output / "later.ipynb").exists()


def test_write_back_saves_reading_formats_with_executed_output_and_local_links(tmp_path):
    entries = make_repo(tmp_path, {"ok": "print('visible tool result')"})
    path = tmp_path / "notebooks/ch01/ok.ipynb"
    nb = nbformat.read(path, as_version=4)
    nb.cells.append(nbformat.v4.new_markdown_cell("[helper](helper.py)"))
    nbformat.write(nb, path)
    (path.parent / "helper.py").write_text("# Chapter helper\n")
    report = run_entries(entries, tmp_path, tmp_path / "output", mode="offline", timeout=30, write_back=True)
    assert report["results"][0]["status"] == "passed"
    for suffix in (".html", ".md"):
        reading = path.with_suffix(suffix).read_text(encoding="utf-8")
        assert "visible tool result" in reading
        assert "offline" in reading
    assert "[helper](helper.py)" in path.with_suffix(".md").read_text(encoding="utf-8")
    assert 'href="helper.py"' in path.with_suffix(".html").read_text(encoding="utf-8")
    from course_notebooks.run import validate_reading
    validate_reading(tmp_path, entries)
    path.with_suffix(".md").write_text("stale reading copy")
    with pytest.raises(ValueError, match="reading copy"):
        validate_reading(tmp_path, entries)
    path.with_suffix(".html").unlink()
    with pytest.raises(ValueError, match="reading copy"):
        validate_reading(tmp_path, entries)


def test_failed_write_back_preserves_source_and_reading_copies(tmp_path):
    entries = make_repo(tmp_path, {"bad": "raise ValueError('deliberate failure')"})
    path = tmp_path / "notebooks/ch01/bad.ipynb"
    original = path.read_bytes()
    for suffix in (".html", ".md"):
        path.with_suffix(suffix).write_text("previous reading copy")
    report = run_entries(entries, tmp_path, tmp_path / "output", mode="offline", timeout=30, write_back=True)
    assert report["results"][0]["status"] == "failed"
    assert path.read_bytes() == original
    for suffix in (".html", ".md"):
        assert path.with_suffix(suffix).read_text(encoding="utf-8") == "previous reading copy"


@pytest.mark.parametrize("generic", [False, True])
def test_live_artifacts_record_the_kernel_model_without_credentials(tmp_path, monkeypatch, generic):
    import os
    for key in list(os.environ):
        if key.startswith(("MODEL_", "SILICONFLOW_", "OPENAI_", "COURSE_")):
            monkeypatch.delenv(key)
    # Construct the real client, but do not call an external API in this regression.
    entries = make_repo(tmp_path, {"configured": (
        "from course_notebooks.model_config import create_model\n"
        "from course_notebooks.nbtools import show_runtime\n"
        "model = create_model(None)\nshow_runtime()\nprint(model.model_name)"
    )})
    if generic:
        configuration = (
            "MODEL_API_KEY=runner-secret-key\n"
            "MODEL_BASE_URL=https://private-user:private-password@api.example.test/v1?token=url-secret-token\n"
        )
        provider, host = "openai-compatible", "api.example.test"
    else:
        configuration = "SILICONFLOW_API_KEY=runner-secret-key\n"
        provider, host = "siliconflow", "api.siliconflow.cn"
    (tmp_path / ".env").write_text(configuration + "MODEL_NAME=dotenv-model\n")
    monkeypatch.setenv("MODEL_NAME", "environment-model")
    output = tmp_path / "output"
    report = run_entries(entries, tmp_path, output, mode="live", timeout=30)
    result = report["results"][0]
    assert result["status"] == "passed"
    expected = {
        "provider": provider, "model_name": "environment-model", "api_host": host,
        "temperature": 0, "timeout_seconds": 60, "max_retries": 1,
    }
    assert result["model_configuration"] == expected
    saved = nbformat.read(output / "configured.ipynb", as_version=4)
    assert saved.metadata.course_run.model_configuration == expected
    for filename in ("report.json", "configured.ipynb", "configured.md", "configured.html"):
        text = (output / filename).read_text(encoding="utf-8")
        assert "environment-model" in text
        for secret in ("runner-secret-key", "private-user", "private-password", "url-secret-token"):
            assert secret not in text


def test_live_missing_model_fails_before_executing_cells(tmp_path, monkeypatch):
    import os
    for key in list(os.environ):
        if key.startswith(("MODEL_", "SILICONFLOW_", "OPENAI_", "COURSE_")):
            monkeypatch.delenv(key)
    entries = make_repo(tmp_path, {"bad": "raise RuntimeError('cell must not execute')"})
    (tmp_path / ".env").write_text("SILICONFLOW_API_KEY=runner-secret-key\n")
    report = run_entries(entries, tmp_path, tmp_path / "output", mode="live", timeout=30)
    assert report["results"][0]["status"] == "failed"
    assert report["results"][0]["error"] == "ValueError"
    saved = nbformat.read(tmp_path / "output/bad.ipynb", as_version=4)
    assert saved.cells[0].outputs == []


def test_credentials_in_model_metadata_withhold_artifacts_and_report_value(tmp_path, monkeypatch):
    import os
    for key in list(os.environ):
        if key.startswith(("MODEL_", "SILICONFLOW_", "OPENAI_", "COURSE_")):
            monkeypatch.delenv(key)
    entries = make_repo(tmp_path, {"bad": "print('no model name printed')"})
    (tmp_path / ".env").write_text("SILICONFLOW_API_KEY=runner-secret-key\nMODEL_NAME=runner-secret-key\n")
    output = tmp_path / "output"
    report = run_entries(entries, tmp_path, output, mode="live", timeout=30)
    assert report["results"][0]["status"] == "failed"
    assert "artifacts withheld" in report["results"][0]["error"]
    assert "runner-secret-key" not in (output / "report.json").read_text(encoding="utf-8")
    assert not (output / "bad.ipynb").exists()
