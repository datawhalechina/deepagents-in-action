import json
from pathlib import Path

import nbformat
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

CH02 = Path(__file__).parents[1] / "ch02"


def run_cell(notebook, tag, namespace):
    nb = nbformat.read(CH02 / notebook, as_version=4)
    cell = next(c for c in nb.cells if tag in c.metadata.get("tags", []))
    exec(cell.source, namespace)


def call(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"id": call_id, "name": name, "args": args}])


def reply(content, name, call_id, status="success"):
    return ToolMessage(content=content, name=name, tool_call_id=call_id, status=status)


FINAL = AIMessage(content="done")


def weather(*, city="北京", content=None, status="success", name="get_weather", call_id="w1"):
    return [HumanMessage(content="weather"), call("get_weather", {"city": city}, "w1"),
            reply(content or f"It's always sunny in {city}!", name, call_id, status), FINAL]


@pytest.mark.parametrize("city", ["北京", "Beijing", "beijing", " Beijing "])
def test_weather_accepts_result_matching_requested_city(city):
    run_cell("01-quickstart.ipynb", "weather-validation", {"result": {"messages": weather(city=city)}})


@pytest.mark.parametrize("messages", [
    [HumanMessage(content="weather"), AIMessage(content="It's sunny")],
    weather(status="error"),
    weather(content="It's always sunny in 上海!"),
    weather(city="上海"),
    weather(city="Shanghai"),
    weather(name="other_tool"),
    weather(call_id="unrelated"),
    weather()[:-1],
])
def test_weather_rejects_unverified_run(messages):
    with pytest.raises(AssertionError):
        run_cell("01-quickstart.ipynb", "weather-validation", {"result": {"messages": messages}})


def calculator(*, convert_args=None, converted=720.0, convert_status="success",
               expression="720.0 * 1.08", product="777.6", calc_status="success", final=FINAL,
               order="chained"):
    args = convert_args if convert_args is not None else {"amount": 100, "from_currency": "USD"}
    convert_reply = reply(json.dumps({"amount": converted, "currency": "CNY"}), "convert_currency", "c1",
                          convert_status)
    calc_reply = reply(product, "calculate", "c2", calc_status)
    if order == "chained":
        messages = [call("convert_currency", args, "c1"), convert_reply,
                    call("calculate", {"expression": expression}, "c2"), calc_reply]
    elif order == "parallel":
        messages = [AIMessage(content="", tool_calls=[
                        {"id": "c1", "name": "convert_currency", "args": args},
                        {"id": "c2", "name": "calculate", "args": {"expression": expression}}]),
                    convert_reply, calc_reply]
    else:  # calculate first, then convert
        messages = [call("calculate", {"expression": expression}, "c2"), calc_reply,
                    call("convert_currency", args, "c1"), convert_reply]
    return [HumanMessage(content="convert")] + messages + ([final] if final else [])


@pytest.mark.parametrize("messages", [
    calculator(),
    calculator(convert_args={"amount": 100.0, "from_currency": "USD", "to_currency": "CNY"}),
    calculator(expression="720 * 1.08", product="777.6000000000001"),
    calculator(expression="1.08 * 720.0"),
    calculator(expression="(720) * (1 + 0.08)"),
])
def test_calculator_accepts_chained_tool_results(messages):
    run_cell("01-quickstart.ipynb", "calculator-validation", {"calc_result": {"messages": messages}})


@pytest.mark.parametrize("messages", [
    [HumanMessage(content="convert"), AIMessage(content="777.6")],
    calculator(convert_status="error"),
    calculator(convert_args={"amount": 200, "from_currency": "USD"}),
    calculator(convert_args={"amount": 100, "from_currency": "USD", "to_currency": "EUR"}),
    calculator(converted=700.0),
    calculator(calc_status="error"),
    calculator(final=None),
    calculator(expression="777.6", order="calculate-first"),
    calculator(expression="100 * 7.2 * 1.08", order="calculate-first"),
    calculator(expression="100 * 7.2 * 1.08", order="parallel"),
    calculator(expression="777.6"),
    calculator(expression="700 * 1.08", product="756.0"),
])
def test_calculator_rejects_unfulfilled_or_unchained_run(messages):
    with pytest.raises(AssertionError):
        run_cell("01-quickstart.ipynb", "calculator-validation", {"calc_result": {"messages": messages}})


NOTES = "# notes"
PLAN = [{"content": "search", "status": "completed"}]


def research(*, results=({"url": "https://example.com"},), search_status="success", todos=PLAN,
             files=None, final=AIMessage(content="report"), delegate=False, file_path="/notes.md"):
    messages = [HumanMessage(content="research"),
                call("write_todos", {"todos": PLAN}, "t1"), reply("Updated todo list", "write_todos", "t1")]
    if delegate:
        messages += [call("task", {"description": "search"}, "k1"), reply("summary", "task", "k1")]
    else:
        messages += [call("internet_search", {"query": "LangGraph"}, "s1"),
                     reply(json.dumps({"results": list(results)}), "internet_search", "s1", search_status)]
    messages += [call("write_file", {"file_path": file_path, "content": NOTES}, "f1"),
                 reply("Updated file /notes.md", "write_file", "f1")]
    if final is not None:
        messages.append(final)
    state = {"messages": messages, "files": {"/notes.md": {"content": NOTES}} if files is None else files}
    if todos is not None:
        state["todos"] = todos
    return state


SEARCHED = [{"query": "LangGraph", "results": 3}]


def check(state, search_log=SEARCHED):
    run_cell("02-research-assistant.ipynb", "research-validation",
             {"result": state, "search_log": list(search_log)})


@pytest.mark.parametrize("state", [
    research(),
    research(delegate=True),
    research(file_path="notes.md"),
    research(file_path="/./notes.md"),
])
def test_research_accepts_search_or_delegation_with_consistent_state(state):
    check(state)


def test_research_treats_planning_and_files_as_optional():
    state = research()
    state["messages"] = [m for m in state["messages"]
                         if not (isinstance(m, ToolMessage) and m.name in {"write_todos", "write_file"})]
    state.pop("todos")
    state["files"] = {}
    check(state)


def test_research_normalizes_edited_paths_before_skipping_content_check():
    state = research(file_path="notes.md", files={"/notes.md": {"content": "# notes, edited"}})
    state["messages"][-1:-1] = [call("edit_file", {"file_path": "notes.md", "old_string": "notes",
                                                   "new_string": "notes, edited"}, "e1"),
                                reply("Successfully replaced", "edit_file", "e1")]
    check(state)


@pytest.mark.parametrize("search_log", [
    [],
    [{"query": "LangGraph", "results": 0}],
])
def test_research_rejects_delegation_without_an_actual_search(search_log):
    with pytest.raises(AssertionError, match="internet_search"):
        check(research(delegate=True), search_log)


@pytest.mark.parametrize(("state", "search_log"), [
    # The search tool ran but returned nothing, or failed before logging.
    (research(results=()), [{"query": "LangGraph", "results": 0}]),
    (research(search_status="error"), []),
    (research(final=None), SEARCHED),
    (research(final=AIMessage(content="", tool_calls=[{"id": "x", "name": "ls", "args": {}}])), SEARCHED),
    (research(todos=[{"content": "search", "status": "pending"}]), SEARCHED),
    (research(files={}), SEARCHED),
    (research(files={"/notes.md": {"content": "changed"}}), SEARCHED),
    (research(file_path="notes.md", files={"/other.md": {"content": NOTES}}), SEARCHED),
])
def test_research_rejects_missing_search_report_or_inconsistent_state(state, search_log):
    with pytest.raises(AssertionError):
        check(state, search_log)
