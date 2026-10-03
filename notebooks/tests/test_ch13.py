from pathlib import Path

import nbformat
import pytest


@pytest.fixture
def experiment(monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    nb = nbformat.read(Path(__file__).parents[1] / "ch13/01-rubric-revision.ipynb", as_version=4)
    sources = {
        tag: cell.source for cell in nb.cells if cell.cell_type == "code"
        for tag in cell.metadata.get("tags", [])
    }
    scope = {}
    for tag in ("ch13-imports", "ch13-inputs", "ch13-assessment", "ch13-evidence",
                "ch13-scripted-grader", "ch13-runner"):
        exec(sources[tag], scope)
    return scope, sources


@pytest.mark.parametrize("tag", ["ch13-revision", "ch13-budget", "ch13-no-rubric"])
def test_real_rubric_loop_and_acceptance(experiment, tag):
    scope, sources = experiment
    exec(sources[tag], scope)


def test_exercise_budget_cannot_deliver_unrevised_report(experiment):
    scope, sources = experiment
    source = sources["ch13-revision"].replace("run_report(max_iterations=2)", "run_report(max_iterations=1)")
    with pytest.raises(AssertionError, match="没有明确通过"):
        exec(source, scope)
    assert scope["evaluations"][-1]["result"] == "max_iterations_reached"
    assert len(scope["records"]) == 1


@pytest.mark.parametrize("report", [
    "not JSON", "[]",
    '{"items": [], "total": 80}',
    '{"items": [{"name": "茶", "amount": 30}, {"name": "咖啡", "amount": 50}], "total": 81}',
])
def test_evidence_rejects_invalid_structure_or_business_values(experiment, report):
    scope, _ = experiment
    evidence = scope["assess_report"](report)
    assert not evidence["ok"]
    assert any(not c["passed"] and c["gap"] for c in evidence["criteria"])


def test_acceptance_requires_current_explicit_pass(experiment):
    scope, _ = experiment
    accept = scope["accepted"]
    assert not accept([])
    for result in ("needs_revision", "max_iterations_reached", "failed", "grader_error", "unknown"):
        assert not accept([{"result": "satisfied"}, {"result": result}])
    assert accept([{"result": "needs_revision"}, {"result": "satisfied"}])


def test_scripted_grader_rejects_unrelated_tool_evidence(experiment):
    scope, _ = experiment
    messages = [
        scope["AIMessage"](content="", tool_calls=[{
            "id": "expected-check", "name": "check_report", "args": {"report": scope["GOOD_REPORT"]},
        }]),
        scope["ToolMessage"](content='{"ok": true}', name="check_report", tool_call_id="other-check"),
    ]
    with pytest.raises(AssertionError):
        scope["scripted_grader"](messages, ("check_report", "GraderResponse"))
