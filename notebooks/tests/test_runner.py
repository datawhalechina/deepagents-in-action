import json
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
    assert "[local_server.py](https://github.com/" in (output / "ok.md").read_text()


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
        reading = path.with_suffix(suffix).read_text()
        assert "visible tool result" in reading
        assert "offline" in reading
    assert "[helper](helper.py)" in path.with_suffix(".md").read_text()
    assert 'href="helper.py"' in path.with_suffix(".html").read_text()
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
        assert path.with_suffix(suffix).read_text() == "previous reading copy"
