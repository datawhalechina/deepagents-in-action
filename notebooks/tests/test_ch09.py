"""Verify approvals against real execution records, not the scripted final reply."""
from copy import deepcopy
from pathlib import Path

import nbformat
import pytest


@pytest.fixture
def experiment_api(monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    notebook = nbformat.read(
        Path(__file__).parents[1] / "ch09/01-tool-approval-and-resume.ipynb", as_version=4
    )
    namespace = {}
    for cell in notebook.cells:
        tags = cell.metadata.get("tags", [])
        if any(tag in tags for tag in (
            "ch09-imports", "ch09-tools", "ch09-agent", "ch09-outcome",
        )):
            exec(cell.source, namespace)
        elif "ch09-start" in tags:
            exec(cell.source.split("\napprove_case =", 1)[0], namespace)
    return namespace


@pytest.mark.parametrize("decision_type", ["approve", "edit", "reject", "respond"])
def test_decision_controls_actual_execution_and_preserves_model_result(experiment_api, decision_type):
    api = experiment_api
    original = api["ORIGINAL_ARGS"]
    changed = {**original, "to": "team@example.com"}
    reason = "取消发送，不要重试。"
    answer = "按季度汇总。"
    plan = api["ASK_CALL"] if decision_type == "respond" else api["EMAIL_CALL"]
    case = api["new_experiment"]([plan], f"decision-{decision_type}")
    api["start_experiment"](case)
    assert len(case["recorder"].inputs) == 1
    snapshot = case["agent"].get_state(case["config"])
    assert snapshot.interrupts and snapshot.values["messages"][-1].tool_calls == case["calls"]

    decisions = {
        "approve": {"type": "approve"},
        "edit": {"type": "edit", "edited_action": {"name": "send_email", "args": changed}},
        "reject": {"type": "reject", "message": reason},
        "respond": {"type": "respond", "message": answer},
    }
    result = case["agent"].invoke(
        api["Command"](resume={"decisions": [decisions[decision_type]]}),
        config=case["config"], version="v2",
    )
    expected_args = changed if decision_type == "edit" else original
    records = [{"name": "send_email", "args": expected_args}] if decision_type in {"approve", "edit"} else []
    feedback = [("error", reason)] if decision_type == "reject" else [
        ("success", answer if decision_type == "respond" else expected_args)
    ]
    api["check_outcome"](case, result, records, feedback)
    # A third request would mean the model step before approval was repeated.
    assert len(case["recorder"].inputs) == 2


@pytest.mark.parametrize("broken_evidence", ["execution", "call_id", "model_input"])
def test_successful_final_reply_cannot_mask_missing_evidence(experiment_api, broken_evidence):
    api = experiment_api
    case = api["new_experiment"]([api["EMAIL_CALL"]], "broken-evidence")
    api["start_experiment"](case)
    result = case["agent"].invoke(
        api["Command"](resume={"decisions": [{"type": "approve"}]}),
        config=case["config"], version="v2",
    )
    if broken_evidence == "execution":
        case["records"].clear()
    elif broken_evidence == "call_id":
        reply = next(m for m in result.value["messages"] if isinstance(m, api["ToolMessage"]))
        reply.tool_call_id = "unrelated-call"
    else:
        case["recorder"].inputs[-1] = [api["AIMessage"](content="done")]
    with pytest.raises(AssertionError):
        api["check_outcome"](
            case, result, [{"name": "send_email", "args": api["ORIGINAL_ARGS"]}],
            [("success", api["ORIGINAL_ARGS"])],
        )


def test_incomplete_batch_decisions_do_not_execute_any_tool(experiment_api):
    api = experiment_api
    second = deepcopy(api["EMAIL_CALL"])
    second.update(id="mail-2", args={**second["args"], "to": "team@example.com"})
    case = api["new_experiment"]([api["EMAIL_CALL"], second], "invalid-count")
    api["start_experiment"](case)
    with pytest.raises(ValueError, match="does not match"):
        case["agent"].invoke(
            api["Command"](resume={"decisions": [{"type": "approve"}]}),
            config=case["config"], version="v2",
        )
    assert case["records"] == []
    assert len(case["recorder"].inputs) == 1


def test_mail_policy_rejects_respond_without_executing_tool(experiment_api):
    api = experiment_api
    case = api["new_experiment"]([api["EMAIL_CALL"]], "invalid-type")
    api["start_experiment"](case)
    with pytest.raises(ValueError, match="not allowed"):
        case["agent"].invoke(
            api["Command"](resume={"decisions": [{"type": "respond", "message": "取消发送"}]}),
            config=case["config"], version="v2",
        )
    assert case["records"] == []


def test_default_invoke_supports_interrupt_and_resume(experiment_api):
    api = experiment_api
    case = api["new_experiment"]([api["EMAIL_CALL"]], "default-invoke")
    paused = case["agent"].invoke(
        {"messages": [("user", "发送教学邮件")]}, config=case["config"],
    )
    assert paused["__interrupt__"] and case["records"] == []
    result = case["agent"].invoke(
        api["Command"](resume={"decisions": [{"type": "approve"}]}), config=case["config"],
    )
    assert not result.get("__interrupt__")
    assert case["records"] == [{"name": "send_email", "args": api["ORIGINAL_ARGS"]}]
