from pathlib import Path

import nbformat
import pytest
from langgraph.stream import GraphRunStream


@pytest.fixture
def experiment(monkeypatch):
    monkeypatch.setenv("COURSE_MODE", "offline")
    nb = nbformat.read(Path(__file__).parents[1] / "ch14/01-streaming-projections.ipynb", as_version=4)
    sources = {tag: c.source for c in nb.cells if c.cell_type == "code"
               for tag in c.metadata.get("tags", [])}
    scope = {}
    for tag in ("ch14-imports", "ch14-tool", "ch14-agent"):
        exec(sources[tag], scope)
    return scope, sources


def test_typed_stream_checks_actual_delegation_and_tool_result(experiment):
    scope, sources = experiment
    exec(sources["ch14-typed-run"], scope)
    exec(sources["ch14-typed-check"], scope)


def test_raw_order_progress_and_namespace(experiment):
    scope, sources = experiment
    for tag in ("ch14-typed-run", "ch14-typed-check", "ch14-raw-run", "ch14-raw-check"):
        exec(sources[tag], scope)


def test_late_subscription_does_not_mean_no_execution(experiment):
    scope, sources = experiment
    exec(sources["ch14-late-subscription"], scope)


def test_exercise_fails_after_real_run_has_finished(experiment):
    scope, sources = experiment
    with pytest.raises(AssertionError, match="晚订阅可能漏掉委派"):
        exec(sources["ch14-raw-run"].replace("SUBSCRIBE_EARLY = True", "SUBSCRIBE_EARLY = False"), scope)
    assert scope["raw_events"] and len(scope["raw_executions"]) == 1
    assert scope["raw_final_state"]["messages"][-1].text


@pytest.mark.parametrize("update", [{"tool_call_id": "unrelated"}, {"status": "error"}])
def test_terminal_check_rejects_wrong_or_failed_tool_result(experiment, update):
    scope, sources = experiment
    exec(sources["ch14-typed-run"], scope)
    call = scope["child_calls"][0]
    call.output = call.output.model_copy(update=update)
    with pytest.raises(AssertionError):
        exec(sources["ch14-typed-check"], scope)


def test_path_prefix_keeps_deeper_events_and_excludes_siblings(experiment):
    scope, sources = experiment
    exec(sources["ch14-raw-check"].split("sequences =", 1)[0], scope)
    belongs = scope["belongs_to"]
    path = ("tools:child",)
    assert belongs(list(path), path)
    assert belongs([*path, "model_request:inner"], path)
    assert not belongs([], path)
    assert not belongs(["tools:sibling"], path)


def test_stream_context_aborts_on_consumer_error(experiment, monkeypatch):
    scope, sources = experiment
    aborted = []
    original_abort = GraphRunStream.abort

    def track_abort(stream):
        aborted.append(stream)
        original_abort(stream)

    def fail_display(*args, **kwargs):
        raise RuntimeError("consumer failed")

    monkeypatch.setattr(GraphRunStream, "abort", track_abort)
    scope["show_text"] = fail_display
    with pytest.raises(RuntimeError, match="consumer failed"):
        exec(sources["ch14-typed-run"], scope)
    assert scope["run"] in aborted


@pytest.mark.parametrize("heading, label", [
    ("## 4. 第二个修复", "[researcher]"),
    ("## 5. 第三个修复", "[researcher tool]"),
])
def test_tutorial_examples_do_not_lose_child_projection(experiment, capsys, heading, label):
    scope, _ = experiment
    content = Path(__file__).parents[2] / "content/ch14-streaming.md"
    section = content.read_text().split(heading, 1)[1]
    source = section.split("```python\n", 1)[1].split("\n```", 1)[0]
    scope["agent"], executions = scope["make_agent"]()
    scope["request"] = scope["REQUEST"]
    exec(source, scope)
    assert len(executions) == 1
    assert label in capsys.readouterr().out
