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
    # The approval cell defines its rules before entering the temporary directory.
    exec(cells["ch11-review"].split("\nwith TemporaryDirectory", 1)[0], namespace)
    return namespace, cells


@pytest.mark.parametrize("tag", [
    "ch11-readonly", "ch11-default-allow", "ch11-order", "ch11-private", "ch11-review",
    "ch11-review-fallback",
])
def test_notebook_checks_real_results_and_file_effects(chapter, tag):
    namespace, cells = chapter
    exec(cells[tag], namespace)


@pytest.mark.parametrize("tag", [
    "ch11-readonly", "ch11-default-allow", "ch11-order", "ch11-review",
])
def test_optional_single_newline_does_not_change_permission_or_approved_content(chapter, tag):
    namespace, cells = chapter

    def omit_newline(scripted):
        responses = deepcopy(scripted.responses)
        for message in responses:
            for call in message.tool_calls:
                if call["name"] == "write_file":
                    call["args"]["content"] = call["args"]["content"].removesuffix("\n")
        return scripted.model_copy(update={"responses": responses})

    namespace["create_model"] = omit_newline
    exec(cells[tag], namespace)
    if tag == "ch11-review":
        approved = namespace["approved_action"]["args"]["content"]
        assert not approved.endswith("\n")
        assert namespace["published_report"] == approved
        assert approved != namespace["WRITE_REVIEW"]["args"]["content"]
    elif tag == "ch11-readonly":
        assert namespace["readonly_case"]["files"] == namespace["SEED"]


def test_review_fallback_denies_wrong_path_with_real_permissions(chapter):
    """审批场景的兜底 deny 必须让写错路径失败，且不产生审批或写入。"""
    namespace, _ = chapter
    assert [rule.mode for rule in namespace["REVIEW_RULES"]] == ["interrupt", "deny"]
    wrong = deepcopy(namespace["WRITE_REVIEW"])
    wrong["args"]["file_path"] = "/report/report.txt"
    wrong["id"] = "write-wrong-review"
    case = namespace["run_case"]("写错路径", namespace["REVIEW_RULES"], [wrong])
    assert case["replies"][0].status == "error"
    assert "permission denied" in case["replies"][0].text
    assert case["files"] == namespace["SEED"]
    assert case["calls"][0]["args"]["file_path"] == "/report/report.txt"


def test_review_narrows_visible_tools_to_write_file(chapter):
    """审批场景只向模型暴露 write_file，避免只靠提示词约束目标路径。"""
    namespace, _ = chapter
    bound = []

    class RecordingModel(namespace["ScriptedChatModel"]):
        def bind_tools(self, tools, **kwargs):
            bound.append(tuple(
                tool["function"]["name"] if isinstance(tool, dict) else tool.name
                for tool in tools
            ))
            return super().bind_tools(tools, **kwargs)

    namespace["create_model"] = lambda scripted: RecordingModel(responses=scripted.responses)
    with namespace["TemporaryDirectory"]() as folder:
        root = namespace["Path"](folder)
        (root / "review").mkdir()
        (root / "review/report.txt").write_text(
            namespace["SEED"]["/review/report.txt"], encoding="utf-8",
        )
        backend = namespace["FilesystemBackend"](root_dir=root, virtual_mode=True)
        agent = namespace["make_agent"](
            backend, namespace["REVIEW_RULES"], [namespace["WRITE_REVIEW"]],
            tool_names={"write_file"},
        )
        paused = agent.invoke(
            namespace["task_input"]([namespace["WRITE_REVIEW"]]),
            config={"recursion_limit": 24}, version="v2",
        )
    assert bound and all(names == ("write_file",) for names in bound)
    assert len(paused.interrupts) == 1


def test_task_tolerance_does_not_rewrite_request_or_relax_actual_approval(chapter):
    namespace, _ = chapter
    planned = namespace["WRITE_REVIEW"]
    expected = [{"name": planned["name"], "args": planned["args"]}]
    actual = deepcopy(expected)
    actual[0]["args"]["content"] = actual[0]["args"]["content"].removesuffix("\n")
    unchanged = deepcopy(actual)
    namespace["check_task_match"](actual, expected)
    assert actual == unchanged
    with pytest.raises(AssertionError):
        namespace["check_task_match"](actual, expected, optional_newline=False)


@pytest.mark.parametrize("fault", [
    "two-newlines", "different-body", "leading-whitespace", "wrong-path",
    "wrong-tool", "extra-arg", "wrong-order", "extra-write",
])
def test_task_match_rejects_every_difference_outside_single_final_newline(chapter, fault, capsys):
    namespace, _ = chapter
    expected = [{"name": call["name"], "args": deepcopy(call["args"])}
                for call in (namespace["READ_NOTES"], namespace["WRITE_NOTES"])]
    actual = deepcopy(expected)
    if fault == "two-newlines":
        actual[1]["args"]["content"] += "\n"
    elif fault == "different-body":
        actual[1]["args"]["content"] = "其他正文\n"
    elif fault == "leading-whitespace":
        actual[1]["args"]["content"] = " " + actual[1]["args"]["content"]
    elif fault == "wrong-path":
        actual[1]["args"]["file_path"] = "/outside.txt"
    elif fault == "wrong-tool":
        actual[1]["name"] = "edit_file"
    elif fault == "extra-arg":
        actual[1]["args"]["append"] = True
    elif fault == "wrong-order":
        actual.reverse()
    else:
        actual.append(deepcopy(actual[1]))
    with pytest.raises(AssertionError):
        namespace["check_task_match"](actual, expected)
    output = capsys.readouterr().out
    assert "任务预期：" in output and "实际请求（差异先展示，再判断）：" in output


@pytest.mark.parametrize("fault", ["changed-file", "new-file"])
def test_denied_write_requires_all_files_to_remain_exactly_unchanged(chapter, fault):
    namespace, cells = chapter
    run_case = namespace["run_case"]

    def damaged_snapshot(*args, **kwargs):
        case = run_case(*args, **kwargs)
        path = "/workspace/notes.txt" if fault == "changed-file" else "/unexpected.txt"
        case["files"][path] = "unauthorized data"
        return case

    namespace["run_case"] = damaged_snapshot
    with pytest.raises(AssertionError, match="改变了文件"):
        exec(cells["ch11-readonly"], namespace)


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
