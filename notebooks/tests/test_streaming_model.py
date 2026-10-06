"""Exercise the course model with real SDK parsing and offline SSE transport."""
import asyncio
import json

import httpx
import pytest
from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from openai import AsyncOpenAI, OpenAI

from course_notebooks.model_config import create_model


def completion_stream(request, continuation_name):
    """Mirror providers that send a name only in the first tool-call delta."""
    payload = json.loads(request.content)
    assert payload["stream"] is True
    if any(message["role"] == "tool" for message in payload["messages"]):
        deltas = [{"role": "assistant", "content": "done"}]
        finish = "stop"
    else:
        deltas = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"index": 0, "id": "echo-1", "type": "function",
                 "function": {"name": "echo", "arguments": '{"text":'}},
                {"index": 1, "id": "length-1", "type": "function",
                 "function": {"name": "length", "arguments": '{"text":'}},
            ]},
            {"tool_calls": [
                {"index": 1, "function": {"name": continuation_name, "arguments": '"abc"}'}},
                {"index": 0, "function": {"name": continuation_name, "arguments": '"hello"}'}},
            ]},
        ]
        finish = "tool_calls"
    events = [
        {"id": "chatcmpl-test", "object": "chat.completion.chunk", "created": 0,
         "model": "test-model", "choices": [
             {"index": 0, "delta": delta, "finish_reason": None},
         ]}
        for delta in deltas
    ]
    events.append({"id": "chatcmpl-test", "object": "chat.completion.chunk", "created": 0,
                   "model": "test-model", "choices": [
                       {"index": 0, "delta": {}, "finish_reason": finish},
                   ]})
    content = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("continuation_name", ["", None], ids=["empty-name", "absent-name"])
def test_v3_course_model_preserves_tool_names_and_executes_tools(
    tmp_path, monkeypatch, asynchronous, continuation_name,
):
    """Empty continuation names must not replace names before tool execution."""
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    model = create_model(None, root=tmp_path, mode="live")
    seen = []

    @tool
    def echo(text: str) -> str:
        """Return the supplied text."""
        seen.append(("echo", text))
        return text

    @tool
    def length(text: str) -> str:
        """Return the length of the supplied text."""
        seen.append(("length", text))
        return str(len(text))

    transport = httpx.MockTransport(lambda request: completion_stream(request, continuation_name))
    inputs = {"messages": [("user", "Use both tools, then finish.")]}
    config = {"recursion_limit": 6}
    if asynchronous:
        async def collect():
            async with AsyncOpenAI(api_key="test-key", http_client=httpx.AsyncClient(transport=transport)) as client:
                model.async_client = client.chat.completions
                agent = create_agent(model=model, tools=[echo, length])
                async with await agent.astream_events(inputs, config, version="v3") as run:
                    return await run.output()
        result = asyncio.run(collect())
    else:
        with OpenAI(api_key="test-key", http_client=httpx.Client(transport=transport)) as client:
            model.client = client.chat.completions
            agent = create_agent(model=model, tools=[echo, length])
            with agent.stream_events(inputs, config, version="v3") as run:
                result = run.output

    assert sorted(seen) == [("echo", "hello"), ("length", "abc")]
    returns = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert sorted((m.name, m.tool_call_id, m.content, m.status) for m in returns) == [
        ("echo", "echo-1", "hello", "success"),
        ("length", "length-1", "3", "success"),
    ]
    assert result["messages"][-1].text == "done"
