"""Chapter 11: real permission outcomes, tutorial exercise, and resource cleanup."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import nbformat
import pytest


@pytest.fixture
def chapter(monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    notebook = nbformat.read(
        Path(__file__).parents[1] / "ch11/01-filesystem-permissions.ipynb", as_version=4,
    )
    cells = {tag: c.source for c in notebook.cells for tag in c.metadata.get("tags", [])}
    namespace = {}
    for tag in ("ch11-imports", "ch11-inputs", "ch11-agent", "ch11-runner"):
        exec(cells[tag], namespace)
    # These cells define rules used by later experiments, without running cases.
    for tag in ("ch11-default-allow", "ch11-private"):
        exec(cells[tag].split("\nallow_only_case =", 1)[0].split("\nprotected_case =", 1)[0], namespace)
    return namespace, cells


@pytest.mark.parametrize("tag", [
    "ch11-readonly", "ch11-default-allow", "ch11-order", "ch11-private", "ch11-review",
])
def test_notebook_checks_real_results_and_file_effects(chapter, tag):
    namespace, cells = chapter
    exec(cells[tag], namespace)


def test_wrong_private_path_exposes_content_and_breaks_protection_check(chapter):
    namespace, cells = chapter
    changed = cells["ch11-private"].replace(
        'paths=["/workspace/private.txt"]', 'paths=["/workspace/other.txt"]', 1,
    )
    with pytest.raises(AssertionError):
        exec(changed, namespace)
    case = namespace["protected_case"]
    assert case["replies"][0].status == "success"
    assert "仅用于演示的私有资料" in case["replies"][0].text
    assert case["files"] == namespace["SEED"]


def test_success_reply_cannot_hide_wrong_call_correlation(chapter):
    namespace, _ = chapter
    case = namespace["run_case"]("关联检查", [], [namespace["READ_NOTES"]])
    messages = deepcopy(case["result"]["messages"])
    reply = next(m for m in messages if isinstance(m, namespace["ToolMessage"]))
    assert reply.status == "success"
    reply.tool_call_id = "unrelated-request"
    with pytest.raises(AssertionError):
        namespace["check_calls"](messages, [namespace["READ_NOTES"]])


def test_python_failure_inside_experiment_removes_temporary_files(chapter):
    namespace, _ = chapter
    created = []

    @contextmanager
    def tracked_directory(**kwargs):
        with TemporaryDirectory(**kwargs) as folder:
            created.append(Path(folder))
            yield folder

    def fail_before_invoke(*args, **kwargs):
        assert (created[-1] / "workspace/notes.txt").exists()
        raise ValueError("planned construction failure")

    namespace["TemporaryDirectory"] = tracked_directory
    namespace["make_agent"] = fail_before_invoke
    with pytest.raises(ValueError, match="planned construction failure"):
        namespace["run_case"]("异常清理", [], [namespace["WRITE_NOTES"]])
    assert len(created) == 1 and not created[0].exists()
