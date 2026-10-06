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
