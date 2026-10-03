"""Ensure the notebook rejects misleading evidence of progressive disclosure."""
from copy import deepcopy
from pathlib import Path

import nbformat
import pytest


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    path = Path(__file__).parents[1] / "ch07/01-skills-progressive-disclosure.ipynb"
    nb = nbformat.read(path, as_version=4)
    namespace = {}
    for cell in nb.cells:
        if any(tag.startswith("ch07-") for tag in cell.metadata.get("tags", [])):
            exec(cell.source, namespace)
    for name, content in [("SKILL_PATH", "SKILL_TEXT"),
                          ("REFERENCE_PATH", "REFERENCE_TEXT")]:
        file = tmp_path / namespace[name].lstrip("/")
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(namespace[content], encoding="utf-8")
    result, requests = namespace["run_agent"](tmp_path)
    namespace["check_disclosure"](result, requests, resource_exists=True)
    return namespace, result, requests, tmp_path


@pytest.mark.parametrize("damage", [
    "early_body", "early_reference", "missing_read", "wrong_id", "wrong_content",
])
def test_disclosure_checks_reject_misleading_evidence(experiment, damage):
    ns, result, requests, _ = experiment
    result, requests = deepcopy(result), deepcopy(requests)
    replies = [m for m in result["messages"] if isinstance(m, ns["ToolMessage"])]
    if damage == "early_body":
        requests[0]["context"] += ns["BODY_MARKER"]
    elif damage == "early_reference":
        requests[1]["context"] += ns["REFERENCE_MARKER"]
    elif damage == "missing_read":
        result["messages"] = result["messages"][:3]
    elif damage == "wrong_id":
        replies[-1].tool_call_id = "unrelated-call"
    elif damage == "wrong_content":
        replies[-1].content = "The file was read successfully."
    with pytest.raises(AssertionError):
        ns["check_disclosure"](result, requests, resource_exists=True)


def test_missing_resource_requires_a_real_error(experiment):
    ns, _, _, root = experiment
    (root / ns["REFERENCE_PATH"].lstrip("/")).unlink()
    result, requests = ns["run_agent"](root)
    ns["check_disclosure"](result, requests, resource_exists=False)
    replies = [m for m in result["messages"] if isinstance(m, ns["ToolMessage"])]
    replies[-1].status = "success"
    with pytest.raises(AssertionError):
        ns["check_disclosure"](result, requests, resource_exists=False)
