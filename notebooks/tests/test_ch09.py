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
    api["check_run_state"](case, result, expect_complete=True)
    assert case["model_tools"] == [[plan["name"]], []]
    # A third request would mean the model step before approval was repeated.
    assert len(case["recorder"].inputs) == 2


@pytest.mark.parametrize("broken_evidence", [
    "execution", "call_id", "model_input", "unauthorized_execution", "duplicate_execution",
])
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
    elif broken_evidence == "model_input":
        case["recorder"].inputs[-1] = [api["AIMessage"](content="done")]
    elif broken_evidence == "unauthorized_execution":
        case["records"].append({"name": "ask_user", "args": {"question": "unapproved"}})
    else:
        case["records"].append(deepcopy(case["records"][0]))
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
    assert case["model_tools"] == [["send_email"], []]


@pytest.mark.parametrize("location", ["reply", "first_main_input"])
def test_complete_human_answer_must_survive_resume(experiment_api, location):
    api = experiment_api
    case = api["new_experiment"]([api["ASK_CALL"]], "complete-answer")
    api["start_experiment"](case)
    answer = "按季度汇总。\n排除测试数据，并保留审计明细。"
    result = case["agent"].invoke(
        api["Command"](resume={"decisions": [{"type": "respond", "message": answer}]}),
        config=case["config"], version="v2",
    )
    if location == "reply":
        messages = result.value["messages"]
    else:
        messages = case["recorder"].inputs[case["model_calls_before"]]
        # A later good request must not mask the first main request's lost feedback.
        case["recorder"].inputs.append(deepcopy(messages))
        case["recorder"].requests.append(deepcopy(case["recorder"].requests[-1]))
    reply = next(m for m in messages if isinstance(m, api["ToolMessage"]))
    reply.content = "按季度汇总。"
    with pytest.raises(AssertionError):
        api["check_outcome"](case, result, [], [("success", answer)])


def test_second_interrupt_preserves_state_until_explicit_second_answer(experiment_api, monkeypatch):
    api = experiment_api
    bound_tools = []
    model_type = api["ScriptedChatModel"]
    generate = model_type._generate

    def observe_binding(self, messages, *args, **kwargs):
        bound_tools.append(kwargs.get("tool_names", ()))
        return generate(self, messages, *args, **kwargs)

    monkeypatch.setattr(model_type, "_generate", observe_binding)
    followup = {
        "name": "ask_user", "args": {"question": "报告输出 PDF 还是表格？"},
        "id": "question-2",
    }
    case = api["new_experiment"]([api["ASK_CALL"]], "second-interrupt", followup=followup)
    api["start_experiment"](case)
    first = "按季度汇总，并排除测试数据。"
    paused = case["agent"].invoke(
        api["Command"](resume={"decisions": [{"type": "respond", "message": first}]}),
        config=case["config"], version="v2",
    )
    api["check_outcome"](case, paused, [], [("success", first)])
    snapshot = api["check_run_state"](case, paused, expect_complete=False)
    with pytest.raises(AssertionError, match="尚未完成"):
        api["check_run_state"](case, paused, expect_complete=True)
    assert snapshot.values["messages"][-1].tool_calls == api["AIMessage"](
        content="", tool_calls=[followup],
    ).tool_calls
    assert snapshot.interrupts[0].value["action_requests"][0]["args"] == followup["args"]
    assert case["records"] == []
    assert len(case["recorder"].inputs) == 2

    before_second = len(case["recorder"].inputs)
    second = "输出 PDF，附上明细表格。"
    result = case["agent"].invoke(
        api["Command"](resume={"decisions": [{"type": "respond", "message": second}]}),
        config=case["config"], version="v2",
    )
    api["check_outcome"](
        case, result, [], [("success", first), ("success", second)],
        calls=case["calls"] + snapshot.values["messages"][-1].tool_calls,
        model_calls_before=before_second,
    )
    api["check_run_state"](case, result, expect_complete=True)
    # Observe the actual model binding, not just the middleware's intended list.
    assert bound_tools == [("ask_user",), ("ask_user",), ()]
    assert case["calls"] == api["AIMessage"](content="", tool_calls=[api["ASK_CALL"]]).tool_calls
    assert case["records"] == []


def test_graph_namespace_not_feedback_identifies_main_model_requests(experiment_api):
    api = experiment_api
    case = api["new_experiment"]([api["ASK_CALL"]], "namespace-regression")
    # Controlled regression only: bypass the notebook's teaching tool restriction
    # to exercise a real child graph; this is not an extra learner-facing scenario.
    main_model = api["ScriptedChatModel"](responses=[
        api["AIMessage"](content="", tool_calls=[deepcopy(api["ASK_CALL"])]),
        api["AIMessage"](content="", tool_calls=[{
            "name": "task", "args": {"description": "namespace probe", "subagent_type": "probe"},
            "id": "task-probe",
        }]),
        api["AIMessage"](content="done"),
    ])
    child_model = api["ScriptedChatModel"](responses=[api["AIMessage"](content="child done")])
    case["agent"] = api["create_deep_agent"](
        model=main_model, tools=api["make_tools"](case["records"]),
        subagents=[{
            "name": "probe", "description": "namespace probe", "system_prompt": "probe",
            "model": child_model, "tools": [],
        }],
        checkpointer=api["InMemorySaver"](),
        interrupt_on={"ask_user": {"allowed_decisions": ["respond"]}},
    )
    api["start_experiment"](case)
    answer = "按季度汇总，并保留完整回答。"
    result = case["agent"].invoke(
        api["Command"](resume={"decisions": [{"type": "respond", "message": answer}]}),
        config=case["config"], version="v2",
    )
    recorder = case["recorder"]
    assert [item["role"] for item in recorder.requests] == ["main", "main", "child", "main"]
    assert all(item["namespace"].startswith("model:") for item in recorder.requests
               if item["role"] == "main")
    assert recorder.requests[2]["namespace"].startswith("tools:")
    assert "|model:" in recorder.requests[2]["namespace"]
    assert not any(isinstance(m, api["ToolMessage"]) for m in recorder.inputs[2])
    # A child without the main agent's feedback must not cause a false failure.
    api["check_outcome"](case, result, [], [("success", answer)])
    api["check_run_state"](case, result, expect_complete=True)

    feedback = next(m for m in recorder.inputs[1] if isinstance(m, api["ToolMessage"]))
    recorder.inputs[2].append(deepcopy(feedback))
    recorder.inputs[1] = [m for m in recorder.inputs[1] if not isinstance(m, api["ToolMessage"])]
    # Neither a child nor the later main request can rescue missing first-main feedback.
    with pytest.raises(AssertionError, match="首个主模型"):
        api["check_outcome"](case, result, [], [("success", answer)])


def test_entire_batch_feedback_must_reach_first_resumed_main_input(experiment_api):
    api = experiment_api
    second = deepcopy(api["EMAIL_CALL"])
    second.update(id="mail-2", args={**second["args"], "to": "team@example.com"})
    case = api["new_experiment"]([api["EMAIL_CALL"], second], "batch-feedback")
    api["start_experiment"](case)
    reason = "取消第二封，不要重试。"
    result = case["agent"].invoke(
        api["Command"](resume={"decisions": [
            {"type": "approve"}, {"type": "reject", "message": reason},
        ]}),
        config=case["config"], version="v2",
    )
    records = [{"name": "send_email", "args": api["ORIGINAL_ARGS"]}]
    feedback = [("success", api["ORIGINAL_ARGS"]), ("error", reason)]
    api["check_outcome"](case, result, records, feedback)
    api["check_run_state"](case, result, expect_complete=True)
    recorder = case["recorder"]
    recorder.inputs[-1] = [
        m for m in recorder.inputs[-1]
        if not (isinstance(m, api["ToolMessage"]) and m.tool_call_id == "mail-2")
    ]
    with pytest.raises(AssertionError, match="首个主模型"):
        api["check_outcome"](case, result, records, feedback)
