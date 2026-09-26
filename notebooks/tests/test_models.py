import pytest
from deepagents import create_deep_agent
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from course_notebooks.model_config import create_model, selected_mode
from course_notebooks.testing import ScriptedChatModel


@pytest.fixture(autouse=True)
def clean_config(monkeypatch):
    import os
    for key in list(os.environ):
        if key.startswith(("MODEL_", "SILICONFLOW_", "COURSE_")):
            monkeypatch.delenv(key)


def test_default_offline_ignores_credentials_and_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_KEY", "do-not-use")
    (tmp_path / ".env").write_text("COURSE_MODE=live\nMODEL_API_KEY=do-not-use\n")
    scripted = ScriptedChatModel(responder=lambda messages, tools: AIMessage(content="offline"))
    assert create_model(scripted, root=tmp_path) is scripted
    assert selected_mode() == "offline"


def test_live_requires_credentials_without_fallback(tmp_path):
    with pytest.raises(ValueError, match="SILICONFLOW_API_KEY"):
        create_model(None, root=tmp_path, mode="live")


def test_generic_provider_configuration_cannot_mix_with_siliconflow(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "example-generic-key")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "example-siliconflow-key")
    with pytest.raises(ValueError, match="MODEL_BASE_URL"):
        create_model(None, root=tmp_path, mode="live")


def test_complete_generic_provider_and_unknown_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "example-generic-key")
    monkeypatch.setenv("MODEL_BASE_URL", "http://127.0.0.1:9999/v1")
    monkeypatch.setenv("MODEL_NAME", "example-model")
    model = create_model(None, root=tmp_path, mode="live")
    assert model.model_name == "example-model"
    assert str(model.openai_api_base) == "http://127.0.0.1:9999/v1"
    with pytest.raises(ValueError, match="offline.*live"):
        selected_mode("automatic")


def test_scripted_model_runs_real_tool_and_receives_tool_result():
    seen = []

    @tool
    def echo(text: str) -> str:
        """Return the supplied text."""
        seen.append(text)
        return f"echo: {text}"

    def reply(messages, tools):
        assert "echo" in tools
        if isinstance(messages[-1], ToolMessage):
            assert messages[-1].content == "echo: hello"
            return AIMessage(content="done")
        return AIMessage(content="", tool_calls=[{
            "id": "echo-1", "name": "echo", "args": {"text": "hello"},
        }])

    agent = create_agent(model=ScriptedChatModel(responder=reply), tools=[echo])
    result = agent.invoke({"messages": [("user", "echo hello")]})
    assert seen == ["hello"]
    assert result["messages"][-1].content == "done"


@pytest.mark.parametrize("factory", [create_agent, create_deep_agent])
def test_response_list_advances_across_tool_rebinding(factory):
    """Copying the response index on bind repeats calls instead of advancing."""
    seen = []

    @tool
    def echo(text: str) -> str:
        """Return the supplied text."""
        seen.append(text)
        return f"echo: {text}"

    model = ScriptedChatModel(responses=[
        AIMessage(content="", tool_calls=[{
            "id": "first", "name": "echo", "args": {"text": "first"},
        }]),
        AIMessage(content="", tool_calls=[{
            "id": "second", "name": "echo", "args": {"text": "second"},
        }]),
        AIMessage(content="done"),
    ])
    agent = factory(model=model, tools=[echo])
    for _ in range(2):
        result = agent.invoke({"messages": [("user", "echo twice")]}, {"recursion_limit": 10})
        returns = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert [(m.tool_call_id, m.content, m.status) for m in returns] == [
            ("first", "echo: first", "success"),
            ("second", "echo: second", "success"),
        ]
        assert result["messages"][-1].content == "done"
    assert seen == ["first", "second", "first", "second"]


def test_response_list_preserves_tool_calls_in_async_stream():
    import asyncio

    seen = []

    @tool
    def echo(text: str) -> str:
        """Return the supplied text."""
        seen.append(text)
        return f"echo: {text}"

    model = ScriptedChatModel(responses=[
        AIMessage(content="", tool_calls=[{
            "id": "stream-echo", "name": "echo", "args": {"text": "streamed"},
        }]),
        AIMessage(content="done"),
    ])
    agent = create_agent(model=model, tools=[echo])

    async def collect():
        return [message async for message, _ in agent.astream(
            {"messages": [("user", "echo streamed")]},
            {"recursion_limit": 10}, stream_mode="messages",
        )]

    messages = asyncio.run(collect())
    assert seen == ["streamed"]
    assert any(isinstance(m, ToolMessage) and m.content == "echo: streamed"
               and m.tool_call_id == "stream-echo" and m.status == "success" for m in messages)
    assert any(isinstance(m, AIMessage) and m.tool_calls for m in messages)


def test_callback_tool_bindings_are_isolated_between_agents():
    @tool
    def supervisor_tool() -> str:
        """A supervisor-only tool."""
        return "supervisor"

    @tool
    def researcher_tool() -> str:
        """A researcher-only tool."""
        return "researcher"

    model = ScriptedChatModel(responder=lambda messages, tools: AIMessage(content=",".join(tools)))
    supervisor = model.bind_tools([supervisor_tool])
    researcher = model.bind_tools([researcher_tool])
    assert supervisor.invoke("next").content == "supervisor_tool"
    assert researcher.invoke("next").content == "researcher_tool"
    assert supervisor.invoke("next").content == "supervisor_tool"
