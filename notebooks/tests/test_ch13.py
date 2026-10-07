from pathlib import Path

import json

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


def test_acceptance_requires_current_explicit_pass_and_actual_evidence(experiment):
    scope, _ = experiment
    result, evaluations, records = scope["run_report"]()
    accept = scope["accepted"]
    assert accept(result, evaluations, records)
    assert not accept(result, [], records)
    for verdict in ("needs_revision", "max_iterations_reached", "failed", "grader_error", "unknown"):
        assert not accept(result, [{"result": "satisfied"}, {"result": verdict}], records)


@pytest.mark.parametrize("tag", ["ch13-budget", "ch13-revision"])
@pytest.mark.parametrize("fault,reason", [
    ("no-tool", "没有实际执行检查工具"),
    ("stale-report", "最后取证不对应最新候选"),
    ("failed-evidence", "最后工具证据未通过"),
])
def test_nonoffline_cells_reject_false_satisfied_from_real_middleware(experiment, tag, fault, reason, capsys):
    scope, sources = experiment
    # 仅替换两个模型；Middleware、工具、回调和最终状态真实执行。
    # 选择非 offline 验证分支，不请求真实模型 API。
    scope["selected_mode"] = lambda: "live"

    def false_grader(messages, tool_names):
        assert "GraderResponse" in tool_names
        if fault != "no-tool" and not isinstance(messages[-1], scope["ToolMessage"]):
            assert "check_report" in tool_names
            report = scope["GOOD_REPORT"] if fault == "stale-report" else scope["BAD_REPORT"]
            return scope["AIMessage"](content="", tool_calls=[{
                "id": "controlled-check", "name": "check_report", "args": {"report": report},
            }])
        return scope["AIMessage"](content="", tool_calls=[{
            "id": "false-verdict", "name": "GraderResponse",
            "args": {
                "result": "satisfied", "explanation": "声称通过，但没有可靠的最新候选证据。",
                "criteria": scope["assess_report"](scope["GOOD_REPORT"])["criteria"],
            },
        }])

    def controlled_model(scripted):
        if scripted.responder is not None:
            return scope["ScriptedChatModel"](responder=false_grader)
        return scope["ScriptedChatModel"](responses=[scope["AIMessage"](content=scope["BAD_REPORT"])])

    scope["create_model"] = controlled_model
    with pytest.raises(AssertionError, match=reason):
        exec(sources[tag], scope)
    prefix = "limited_" if tag == "ch13-budget" else ""
    assert scope[prefix + "evaluations"][-1]["result"] == "satisfied"
    records = scope[prefix + "records"]
    candidates = [m for m in scope[prefix + "result"]["messages"] if isinstance(m, scope["AIMessage"])]
    assert not scope["assess_report"](candidates[-1].text)["ok"]
    if fault == "no-tool":
        assert records == []
    else:
        assert records[-1]["call_id"] == "controlled-check"
        assert records[-1]["evidence"]["ok"] is (fault == "stale-report")
    assert "是否交付： True" not in capsys.readouterr().out


@pytest.mark.parametrize("tag", ["ch13-budget", "ch13-revision"])
def test_nonoffline_cells_accept_legitimate_first_round_pass(experiment, tag):
    scope, sources = experiment
    scope["selected_mode"] = lambda: "live"

    def controlled_model(scripted):
        if scripted.responder is not None:
            return scripted
        return scope["ScriptedChatModel"](responses=[scope["AIMessage"](content=scope["GOOD_REPORT"])])

    scope["create_model"] = controlled_model
    exec(sources[tag], scope)
    prefix = "limited_" if tag == "ch13-budget" else ""
    assert len(scope[prefix + "evaluations"]) == 1
    assert scope["accepted"](scope[prefix + "result"], scope[prefix + "evaluations"], scope[prefix + "records"])


def test_nonoffline_budget_exhaustion_does_not_require_a_pass(experiment):
    scope, sources = experiment
    scope["selected_mode"] = lambda: "live"
    exec(sources["ch13-budget"], scope)
    assert scope["limited_evaluations"][-1]["result"] == "max_iterations_reached"
    assert not scope["accepted"](scope["limited_result"], scope["limited_evaluations"], scope["limited_records"])


@pytest.mark.parametrize("fault", ["missing-id", "failed-evidence", "bad-latest"])
def test_delivery_gate_checks_each_obligation_even_when_others_pass(experiment, fault):
    scope, _ = experiment
    result, evaluations, records = scope["run_report"]()
    if fault == "missing-id":
        records[-1]["call_id"] = ""
    elif fault == "failed-evidence":
        records[-1]["evidence"]["ok"] = False
    else:
        # 即使记录声称通过且版本一致，也独立验证最新报告的业务字段。
        result["messages"][-1] = scope["AIMessage"](content=scope["BAD_REPORT"])
        records[-1]["report"] = scope["BAD_REPORT"]
    with pytest.raises(AssertionError):
        scope["accepted"](result, evaluations, records)


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


def _repeat_happy_grader(scope, *, always_repeat):
    """Once evidence exists, ask for check_report again unless it was hidden."""

    def grader(messages, tool_names):
        if isinstance(messages[-1], scope["ToolMessage"]):
            requests = [
                call for message in messages if isinstance(message, scope["AIMessage"])
                for call in message.tool_calls if call["name"] == "check_report"
            ]
            if always_repeat or "check_report" in tool_names:
                return scope["AIMessage"](content="", tool_calls=[{
                    "id": f"repeat-{len(requests)}", "name": "check_report",
                    "args": dict(requests[-1]["args"]),
                }])
            evidence = json.loads(messages[-1].text)
            return scope["AIMessage"](content="", tool_calls=[{
                "id": "grader-verdict", "name": "GraderResponse",
                "args": {
                    "result": "satisfied" if evidence["ok"] else "needs_revision",
                    "explanation": "证据齐全，返回结论。" if evidence["ok"] else "请修订。",
                    "criteria": evidence["criteria"],
                },
            }])
        transcript = messages[-1].text
        latest = transcript.rsplit("[assistant] ", 1)[-1]
        data, _ = json.JSONDecoder().raw_decode(latest)
        return scope["AIMessage"](content="", tool_calls=[{
            "id": "check-1", "name": "check_report",
            "args": {"report": json.dumps(data, ensure_ascii=False, indent=2)},
        }])

    return grader


def test_repeated_evidence_is_narrowed_and_still_grades(experiment):
    """评分模型在已有本候选证据后仍重复取证：收窄可见工具后仍完成结构化评分。"""
    scope, _ = experiment
    result, evaluations, records = scope["run_report"](
        grader=_repeat_happy_grader(scope, always_repeat=False),
    )
    assert scope["accepted"](result, evaluations, records)
    assert [e["result"] for e in evaluations] == ["needs_revision", "satisfied"]
    # 每个候选只真实执行一次检查；重复请求没有被再次执行。
    assert [record["evidence"]["ok"] for record in records] == [False, True]


def test_unbounded_evidence_repetition_fails_closed(experiment):
    """评分模型无视收窄、一直重复取证时，本次评分必须明确结束并拒绝交付。"""
    scope, _ = experiment
    result, evaluations, records = scope["run_report"](
        grader=_repeat_happy_grader(scope, always_repeat=True),
    )
    assert evaluations[-1]["result"] == "grader_error"
    assert not scope["accepted"](result, evaluations, records)
    # 有上限：重复取证被截断，而不是无限制调用检查工具。
    assert 1 <= len(records) <= 7


def test_schema_retries_before_evidence_are_bounded(experiment):
    """没有取证时的结构化输出错误也必须在六次模型请求后拒绝交付。"""
    scope, _ = experiment
    calls = []

    def invalid_grader(messages, tool_names):
        assert "check_report" in tool_names and "GraderResponse" in tool_names
        if calls:
            reply = messages[-1]
            assert isinstance(reply, scope["ToolMessage"])
            assert reply.name == "GraderResponse"
            assert "explanation" in reply.text and "criteria" in reply.text
        calls.append(messages)
        if len(calls) > 6:
            raise AssertionError("不应发出第七次模型请求")
        return scope["AIMessage"](content="", tool_calls=[{
            "id": f"invalid-{len(calls)}", "name": "GraderResponse",
            "args": {"result": "satisfied"},
        }])

    result, evaluations, records = scope["run_report"](grader=invalid_grader)
    assert len(calls) == 6
    assert records == []
    assert evaluations[-1]["result"] == "grader_error"
    assert "模型调用超过上限" in evaluations[-1]["explanation"]
    assert not scope["accepted"](result, evaluations, records)


def test_each_candidate_has_its_own_model_call_budget(experiment):
    """两个候选各自经历 schema 重试后仍可取证评分，不共用六次预算。"""
    scope, _ = experiment
    calls_per_candidate = []

    def retrying_grader(messages, tool_names):
        if isinstance(messages[-1], scope["HumanMessage"]):
            calls_per_candidate.append(0)
        calls_per_candidate[-1] += 1
        attempt = calls_per_candidate[-1]
        if attempt <= 3:
            assert "check_report" in tool_names
            if attempt > 1:
                assert messages[-1].name == "GraderResponse"
                assert "explanation" in messages[-1].text
            return scope["AIMessage"](content="", tool_calls=[{
                "id": f"invalid-{attempt}", "name": "GraderResponse",
                "args": {"result": "satisfied"},
            }])
        if attempt == 4:
            # 从本次评分的输入读取最新候选，工具仍由真实框架执行。
            inputs = [m for m in messages if isinstance(m, scope["HumanMessage"])]
            return scope["scripted_grader"](inputs, tool_names)
        assert "check_report" not in tool_names
        return scope["scripted_grader"](messages, tool_names)

    result, evaluations, records = scope["run_report"](grader=retrying_grader)
    assert calls_per_candidate == [5, 5]
    assert [e["result"] for e in evaluations] == ["needs_revision", "satisfied"]
    assert [r["evidence"]["ok"] for r in records] == [False, True]
    assert scope["accepted"](result, evaluations, records)


def test_invalid_evidence_arguments_can_be_corrected(experiment):
    """缺 report 的校验错误不能隐藏检查工具；修正后取证一次并交付。"""
    scope, _ = experiment
    replies = []

    def correcting_grader(messages, tool_names):
        if isinstance(messages[-1], scope["HumanMessage"]):
            return scope["AIMessage"](content="", tool_calls=[{
                "id": "missing-report", "name": "check_report", "args": {},
            }])
        reply = messages[-1]
        replies.append(reply)
        assert reply.name == "check_report"
        if reply.status == "error":
            assert reply.tool_call_id == "missing-report" and "report" in reply.text
            assert "check_report" in tool_names
            inputs = [m for m in messages if isinstance(m, scope["HumanMessage"])]
            return scope["scripted_grader"](inputs, tool_names)
        assert "check_report" not in tool_names
        return scope["scripted_grader"](messages, tool_names)

    def controlled_model(scripted):
        if scripted.responder is not None:
            return scripted
        return scope["ScriptedChatModel"](responses=[scope["AIMessage"](content=scope["GOOD_REPORT"])])

    scope["create_model"] = controlled_model
    result, evaluations, records = scope["run_report"](grader=correcting_grader)
    assert [reply.status for reply in replies] == ["error", "success"]
    assert len(records) == 1
    assert records[0]["call_id"] == "check-complete"
    assert evaluations[-1]["result"] == "satisfied"
    assert scope["accepted"](result, evaluations, records)
