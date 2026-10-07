import json
from pathlib import Path

import nbformat
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


NOTEBOOK = Path(__file__).parents[1] / "ch08/01-long-term-memory.ipynb"


def execute_tag(namespace, tag):
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    cells = [cell for cell in notebook.cells if tag in cell.metadata.get("tags", [])]
    assert cells, f"Missing notebook tag: {tag}"
    for cell in cells:
        exec(compile(cell.source, f"{NOTEBOOK.name}:{cell.id}", "exec"), namespace)


@pytest.fixture
def chapter(monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    namespace = {}
    execute_tag(namespace, "ch08-definitions")
    return namespace


def memory_prompt(chapter, content):
    return f"<agent_memory>\n{chapter['MEMORY_PATH']}\n\n{content}\n\n</agent_memory>"


def file_reply(content):
    lines = content.splitlines()
    return ToolMessage(content=f"@@ lines 1-{len(lines)} of {len(lines)} @@\n" + "\n".join(lines),
                       name="read_file", tool_call_id="read-1")


def controlled_run(chapter, content):
    messages = [HumanMessage(content="read preferences"),
                AIMessage(content="", tool_calls=[{
                    "id": "read-1", "name": "read_file",
                    "args": {"file_path": chapter["MEMORY_PATH"]},
                }]), file_reply(content)]
    calls, returns = chapter["scene_evidence"](messages)
    return {"calls": calls, "returns": returns,
            "first_request": [SystemMessage(content=memory_prompt(chapter, content))]}


def tool_error_agent(chapter, responder):
    """Rebuild the notebook Agent with the repeated-tool-error guard and a scripted model."""
    model = chapter["create_model"](chapter["ScriptedChatModel"](responder=responder))
    chapter["agent"] = chapter["create_deep_agent"](
        model=model, backend=chapter["backend"], store=chapter["store"],
        checkpointer=chapter["InMemorySaver"](), context_schema=chapter["UserContext"],
        memory=[chapter["MEMORY_PATH"]], middleware=[chapter["tool_error_guard"]],
        system_prompt=(
            "保存偏好时先读取偏好文件，再用 edit_file 更新；"
            "edit_file 的两个正文参数必须是字符串。"
        ),
    )


def edit_file_call(chapter, *, as_string):
    args = {"file_path": chapter["MEMORY_PATH"]}
    if as_string:
        args.update({"old_string": "{}", "new_string": chapter["PREFERENCE_JSON"]})
    else:
        # 评审复现的错误形态：把 JSON 对象直接传给文本参数。
        args.update({"old_string": {},
                     "new_string": chapter["EXPECTED_PREFERENCES"]})
    return args


def scripted_save(chapter, *, object_attempts):
    """Run read_file, N object-argument edit_file attempts, then a string one."""

    def responder(messages, tool_names):
        latest = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        returned = [m for m in messages[latest + 1:] if isinstance(m, ToolMessage)]
        steps = [("read_file", {"file_path": chapter["MEMORY_PATH"]})]
        steps += [("edit_file", edit_file_call(chapter, as_string=False))] * object_attempts
        steps += [("edit_file", edit_file_call(chapter, as_string=True)),
                  ("write_file", {"file_path": chapter["DRAFT_PATH"],
                                  "content": chapter["DRAFT_TEXT"]})]
        if len(returned) >= len(steps):
            return AIMessage(content="已完成保存；请检查工具结果。")
        name, args = steps[len(returned)]
        assert name in tool_names
        return AIMessage(content="", tool_calls=[{
            "id": f"retry-{len(returned)}", "name": name, "args": args,
        }])

    return responder


def test_object_arguments_are_rejected_then_string_arguments_save(chapter):
    """错误对象参数被真实工具拒绝后，同一场景能用字符串参数完成保存。"""
    chapter["store"].put(("alice", "memories"), chapter["STORE_KEY"],
                         chapter["create_file_data"]("{}"))
    tool_error_agent(chapter, scripted_save(chapter, object_attempts=1))
    run = chapter["run_scene"]("保存", "retry-ok", "alice", "保存偏好")
    edits = [reply for reply in run["returns"] if reply.name == "edit_file"]
    assert [reply.status for reply in edits] == ["error", "success"]
    assert "valid string" in edits[0].text
    chapter["validate_saved"](run)
    assert chapter["tool_error_guard"].stopped == []
    assert chapter["store"].get(("alice", "memories"), chapter["STORE_KEY"]) is not None


def test_repeated_object_arguments_stop_and_show_requests(chapter, capsys):
    """同一组错误参数反复失败时，执行按上限显式结束并展示实际请求与返回。"""
    chapter["store"].put(("alice", "memories"), chapter["STORE_KEY"],
                         chapter["create_file_data"]("{}"))
    tool_error_agent(chapter, scripted_save(chapter, object_attempts=5))
    with pytest.raises(AssertionError, match="同一个工具以相同参数反复失败"):
        chapter["run_scene"]("保存", "retry-stop", "alice", "保存偏好")
    output = capsys.readouterr().out
    assert "重复失败的 edit_file 请求" in output
    assert "valid string" in output
    assert len(chapter["tool_error_guard"].stopped) == 1
    # 已按 stop_after 截断，不会把 5 次错误参数全部重试完。
    state = chapter["agent"].get_state({"configurable": {"thread_id": "retry-stop"}})
    edit_calls = [call for message in state.values["messages"]
                  if isinstance(message, AIMessage)
                  for call in message.tool_calls if call["name"] == "edit_file"]
    assert len(edit_calls) == chapter["tool_error_guard"].stop_after


def test_same_thread_recovers_after_repeated_tool_errors(chapter):
    """保留失败历史后，同 Agent、同线程的修正请求仍能保存偏好和草稿。"""
    chapter["store"].put(("alice", "memories"), chapter["STORE_KEY"],
                         chapter["create_file_data"]("{}"))
    broken = scripted_save(chapter, object_attempts=5)
    corrected = scripted_save(chapter, object_attempts=0)

    def responder(messages, tool_names):
        latest = next(m for m in reversed(messages) if isinstance(m, HumanMessage))
        reply = corrected if "修正" in latest.text else broken
        return reply(messages, tool_names)

    tool_error_agent(chapter, responder)
    thread_id = "recover-same-thread"
    with pytest.raises(AssertionError, match="同一个工具以相同参数反复失败"):
        chapter["run_scene"]("保存", thread_id, "alice", "保存偏好")
    state = chapter["agent"].get_state({"configurable": {"thread_id": thread_id}})
    errors = [m for m in state.values["messages"]
              if isinstance(m, ToolMessage) and m.status == "error"]
    assert len(errors) == chapter["tool_error_guard"].stop_after

    run = chapter["run_scene"]("保存", thread_id, "alice", "修正文本参数后保存偏好")
    chapter["validate_saved"](run)
    assert chapter["tool_error_guard"].stopped == []
    assert [call["name"] for call in run["calls"]] == ["read_file", "edit_file", "write_file"]
    # 首次模型请求及最终 checkpoint 都保留旧错误，恢复不是靠清空线程实现的。
    assert all(error in run["first_request"] for error in errors)
    restored = chapter["agent"].get_state({"configurable": {"thread_id": thread_id}})
    assert all(error in restored.values["messages"] for error in errors)
    assert restored.values["files"][chapter["DRAFT_PATH"]]["content"] == chapter["DRAFT_TEXT"]


def test_real_offline_scenes_preserve_thread_and_user_boundaries(chapter):
    # Execute the notebook's own assertions against real tools, backends and checkpoints.
    execute_tag(chapter, "ch08-scenarios")
    assert chapter["alice_evidence"] == {
        source: chapter["EXPECTED_PREFERENCES"] for source in ("store", "read_file", "agent_memory")
    }
    assert chapter["bob_evidence"] == {
        source: chapter["BOB_PREFERENCES"] for source in ("store", "read_file", "agent_memory")
    }
    assert chapter["draft_miss"].status == "error"
    assert chapter["old_state"].values["files"][chapter["DRAFT_PATH"]]["content"] == chapter["DRAFT_TEXT"]
    # Latest-turn evidence must not accidentally include the saved turn's calls.
    assert [call["name"] for call in chapter["resumed"]["calls"]] == ["read_file"]


def test_reordered_whitespace_json_passes_all_three_evidence_sources(chapter):
    content = ' \n{\n  "variable_language" : "en",\n  "comment_language" : "zh"\n}\n '
    run = controlled_run(chapter, content)
    chapter["store"].put(("alice", "memories"), chapter["STORE_KEY"], chapter["create_file_data"](content))
    evidence = chapter["validate_preferences"](run, "alice", chapter["EXPECTED_PREFERENCES"])
    assert all(value == chapter["EXPECTED_PREFERENCES"] for value in evidence.values())


@pytest.mark.parametrize("bad", [
    {"comment_language": "zh"},
    {"comment_language": "en", "variable_language": "en"},
    {"comment_language": "zh", "variable_language": "en", "date": "2026-01-01"},
    ["zh", "en"],
])
@pytest.mark.parametrize("source", ["store", "read_file", "agent_memory"])
def test_each_evidence_source_rejects_inexact_object(chapter, source, bad):
    content = json.dumps(chapter["EXPECTED_PREFERENCES"])
    run = controlled_run(chapter, content)
    chapter["store"].put(("alice", "memories"), chapter["STORE_KEY"], chapter["create_file_data"](content))
    bad_content = json.dumps(bad)
    if source == "store":
        chapter["store"].put(("alice", "memories"), chapter["STORE_KEY"], chapter["create_file_data"](bad_content))
    elif source == "read_file":
        run["returns"] = [file_reply(bad_content)]
    else:
        run["first_request"] = [SystemMessage(content=memory_prompt(chapter, bad_content))]
    with pytest.raises(AssertionError, match="JSON 对象"):
        chapter["validate_preferences"](run, "alice", chapter["EXPECTED_PREFERENCES"])


@pytest.mark.parametrize("header", [
    "@@ lines 1-1 of 2 @@", "@@ lines 2-2 of 2 @@",
    "@@ lines 1-1 of 2 | next offset 1 @@", "@@ lines 1-1 @@",
    "@@ lines 1-2 of 2 @@", "",
])
def test_read_file_rejects_partial_or_unknown_range_even_with_valid_json(chapter, header):
    reply = file_reply(json.dumps(chapter["EXPECTED_PREFERENCES"]))
    reply.content = header + "\n" + json.dumps(chapter["EXPECTED_PREFERENCES"])
    with pytest.raises(AssertionError):
        chapter["read_file_content"](reply)


@pytest.mark.parametrize("system_memory", [None, "(No memory loaded)", "{}", "wrong-path"])
def test_user_json_and_system_instructions_cannot_impersonate_memory(chapter, system_memory):
    content = json.dumps(chapter["EXPECTED_PREFERENCES"])
    # Correct JSON also appears outside agent_memory in the system instructions.
    prompt = f"Save {chapter['MEMORY_PATH']} as {content}."
    if system_memory == "(No memory loaded)":
        prompt += "\n<agent_memory>\n(No memory loaded)\n\n</agent_memory>"
    elif system_memory is not None:
        block = memory_prompt(chapter, "{}" if system_memory == "{}" else content)
        if system_memory == "wrong-path":
            block = block.replace(chapter["MEMORY_PATH"], "/memories/other.json")
        prompt += "\n" + block
    recorder = chapter["ModelRequestRecorder"]()
    recorder.on_chat_model_start({}, [[SystemMessage(content=prompt), HumanMessage(content=content)]])
    with pytest.raises(AssertionError):
        chapter["parse_preferences"](chapter["memory_content"](recorder.requests[0]), chapter["EXPECTED_PREFERENCES"])


def misroute_agent(chapter):
    backend = chapter["CompositeBackend"](
        default=chapter["StateBackend"](),
        routes={"/memories/": chapter["StoreBackend"](namespace=lambda runtime: ("alice", "memories"))},
    )
    chapter["agent"] = chapter["create_deep_agent"](
        model=chapter["model"], backend=backend, store=chapter["store"],
        checkpointer=chapter["InMemorySaver"](), context_schema=chapter["UserContext"],
        memory=[chapter["MEMORY_PATH"]],
    )


def test_real_wrong_namespace_fails_despite_successful_read(chapter):
    chapter["store"].put(("alice", "memories"), chapter["STORE_KEY"],
                         chapter["create_file_data"](json.dumps(chapter["EXPECTED_PREFERENCES"])))
    misroute_agent(chapter)
    run = chapter["run_scene"]("其他用户", "misrouted-bob", "bob", "read my preferences")
    assert chapter["tool_reply"](run, "read_file", chapter["MEMORY_PATH"]).status == "success"
    # Bob's Store record is still correct, but Alice leaked through the actual tool and prompt.
    with pytest.raises(AssertionError, match="JSON 对象"):
        chapter["validate_preferences"](run, "bob", chapter["BOB_PREFERENCES"])


@pytest.mark.parametrize("source", ["store", "read_file", "agent_memory"])
def test_bob_rejects_alice_in_each_evidence_source(chapter, source):
    bob_content = json.dumps(chapter["BOB_PREFERENCES"])
    alice_content = json.dumps(chapter["EXPECTED_PREFERENCES"])
    run = controlled_run(chapter, bob_content)
    if source == "store":
        chapter["store"].put(("bob", "memories"), chapter["STORE_KEY"], chapter["create_file_data"](alice_content))
    elif source == "read_file":
        run["returns"] = [file_reply(alice_content)]
    else:
        run["first_request"] = [SystemMessage(content=memory_prompt(chapter, alice_content))]
    with pytest.raises(AssertionError, match="JSON 对象"):
        chapter["validate_preferences"](run, "bob", chapter["BOB_PREFERENCES"])


@pytest.mark.parametrize("fault", ["wrong-id", "wrong-name", "duplicate-return", "missing-return", "duplicate-call", "early-return"])
def test_tool_evidence_requires_unique_ordered_call_id_association(chapter, fault):
    user = HumanMessage(content="read")
    call = AIMessage(content="", tool_calls=[{
        "id": "read-1", "name": "read_file", "args": {"file_path": chapter["MEMORY_PATH"]},
    }])
    reply = file_reply("{}")
    messages = [user, call, reply]
    if fault == "wrong-id":
        reply.tool_call_id = "unrelated"
    elif fault == "wrong-name":
        reply.name = "edit_file"
    elif fault == "duplicate-return":
        messages.append(reply)
    elif fault == "missing-return":
        messages.pop()
    elif fault == "duplicate-call":
        messages.insert(2, call)
    else:
        messages = [user, reply, call]
    with pytest.raises(AssertionError):
        chapter["scene_evidence"](messages)
