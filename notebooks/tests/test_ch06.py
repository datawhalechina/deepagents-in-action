import asyncio
import importlib.util
from pathlib import Path
import socket
from types import SimpleNamespace

import nbformat
import pytest


def server_class():
    chapter = Path(__file__).parents[1] / "ch06"
    spec = importlib.util.spec_from_file_location("chapter_server", chapter / "local_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LocalAgentServer, chapter


def test_pending_task_failure_closes_real_server(monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    cls, chapter = server_class()
    server = cls(chapter, chapter.parents[1])

    async def fail_after_start():
        async with server:
            state = await server.client.runs.wait(server.parent_id, "supervisor", input={"messages": [{"role": "user", "content": "START|cleanup regression"}]})
            assert state["async_tasks"]
            assert any(task["status"] == "running" for task in state["async_tasks"].values())
            # Do not manually register task IDs: cleanup must recover them from parent state.
            raise ValueError("injected notebook failure")

    with pytest.raises(ValueError, match="injected notebook failure"):
        asyncio.run(fail_after_start())
    assert server.process.poll() is not None
    assert not server.workdir.exists()
    with socket.socket() as sock:
        sock.settimeout(1)
        assert sock.connect_ex(("127.0.0.1", server.port)) != 0
    assert server.cleaned_task_ids
    assert server.log_path.exists()
    server.log_path.unlink()


def test_startup_failure_cleans_temporary_directory(tmp_path):
    cls, _ = server_class()
    server = cls(tmp_path / "missing-chapter", tmp_path)

    async def start():
        async with server:
            pytest.fail("missing service source must not start")

    with pytest.raises(FileNotFoundError):
        asyncio.run(start())
    assert not server.workdir.exists()
    server.log_path.unlink()


def validate_exchange(calls, *, text="LIST", expected="list_async_tasks", bad_output=None):
    """Exercise the notebook's validation against a controlled SDK response."""
    nb = nbformat.read(Path(__file__).parents[1] / "ch06/01-async-subagent-lifecycle.ipynb", as_version=4)
    cell = next(c for c in nb.cells if "async def ask(" in c.source)
    namespace = {"asyncio": asyncio}
    exec(cell.source, namespace)
    messages = [{"type": "human", "content": text}]
    for index, call in enumerate(calls):
        name, args = (call, {}) if isinstance(call, str) else call
        call_id = f"call-{index}"
        messages.extend([
            {"type": "ai", "tool_calls": [{"id": call_id, "name": name, "args": args}]},
            {"type": "tool", "tool_call_id": call_id, "name": name,
             "status": "success", "content": f"result-{index}"},
        ])
    if bad_output:
        messages[2].update(bad_output)

    async def wait(*args, **kwargs):
        return {"messages": messages, "async_tasks": {}}

    server = SimpleNamespace(parent_id="parent", task_ids=set(),
                             client=SimpleNamespace(runs=SimpleNamespace(wait=wait)))
    return asyncio.run(namespace["ask"](server, text, expected, show=False))


def test_read_request_accepts_successful_status_followup():
    _, output = validate_exchange(["list_async_tasks", "check_async_task"])
    assert output == "result-0"


def test_check_returns_latest_result_for_requested_task():
    _, output = validate_exchange([
        ("check_async_task", {"task_id": "requested-task"}),
        ("check_async_task", {"task_id": "requested-task"}),
        ("check_async_task", {"task_id": "other-task"}),
    ], text="CHECK|requested-task", expected="check_async_task")
    assert output == "result-1"


@pytest.mark.parametrize("all_filter", [{}, {"status_filter": None}, {"status_filter": "all"}])
def test_list_returns_unfiltered_result_after_filtered_followup(all_filter):
    _, output = validate_exchange([
        ("list_async_tasks", all_filter),
        ("list_async_tasks", {"status_filter": "running"}),
    ])
    assert output == "result-0"


@pytest.mark.parametrize("text, expected, wrong_args, requested_args", [
    ("CHECK|requested-task", "check_async_task", {"task_id": "other-task"},
     {"task_id": "requested-task"}),
    ("LIST", "list_async_tasks", {"status_filter": "running"}, {"status_filter": "all"}),
])
def test_read_request_must_query_requested_arguments_first(text, expected, wrong_args, requested_args):
    with pytest.raises(AssertionError):
        validate_exchange([(expected, wrong_args), (expected, requested_args)],
                          text=text, expected=expected)


@pytest.mark.parametrize("calls", [[], ["check_async_task"],
                                      ["list_async_tasks", "start_async_task"],
                                      ["list_async_tasks", "cancel_async_task"]])
def test_read_request_rejects_missing_action_or_extra_mutation(calls):
    with pytest.raises(AssertionError):
        validate_exchange(calls)


@pytest.mark.parametrize("bad_output", [{"status": "error"}, {"tool_call_id": "unrelated"},
                                       {"name": "check_async_task"}])
def test_read_request_rejects_failed_or_mismatched_result(bad_output):
    with pytest.raises(AssertionError):
        validate_exchange(["list_async_tasks"], bad_output=bad_output)


def test_mutation_must_remain_one_operation():
    with pytest.raises(AssertionError):
        validate_exchange(["start_async_task", "check_async_task"], expected="start_async_task")
