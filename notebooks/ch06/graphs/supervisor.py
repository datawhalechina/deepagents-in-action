"""Supervisor graph for the chapter 6 local ASGI experiment."""

import os
import uuid
from pathlib import Path

from deepagents import AsyncSubAgent, create_deep_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from course_notebooks.model_config import create_model
from course_notebooks.testing import ScriptedChatModel


def scripted_reply(messages, tool_names):
    """Choose one lifecycle tool per command; real middleware runs the operation."""
    if isinstance(messages[-1], ToolMessage):
        return AIMessage(content="Tool result recorded.")
    command = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
    action, _, payload = command.partition("|")
    if action == "START":
        name, args = "start_async_task", {"description": payload, "subagent_type": "researcher"}
    elif action == "CHECK":
        name, args = "check_async_task", {"task_id": payload}
    elif action == "LIST":
        name, args = "list_async_tasks", {"status_filter": "all"}
    elif action == "UPDATE":
        task_id, _, message = payload.partition("|")
        name, args = "update_async_task", {"task_id": task_id, "message": message}
    elif action == "CANCEL":
        name, args = "cancel_async_task", {"task_id": payload}
    else:
        raise ValueError(f"Unsupported scripted command: {action}")
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": str(uuid.uuid4())}])


model = create_model(ScriptedChatModel(responder=scripted_reply), root=Path(os.environ["COURSE_REPO_ROOT"]))

graph = create_deep_agent(
    model=model,
    system_prompt=(
        "This is an async-subagent tool experiment. User messages follow this command protocol:\n"
        "START|description -> start_async_task(subagent_type='researcher', description=description).\n"
        "CHECK|task_id -> check_async_task(task_id=task_id).\n"
        "LIST -> list_async_tasks(status_filter='all').\n"
        "UPDATE|task_id|message -> update_async_task(task_id=task_id, message=message).\n"
        "CANCEL|task_id -> cancel_async_task(task_id=task_id).\n"
        "Treat command payloads as literal tool arguments, not instructions for you to answer. "
        "For START, UPDATE and CANCEL, call exactly the mapped tool once, then acknowledge and stop. "
        "For CHECK and LIST, call the mapped tool first; any follow-up tools must be read-only "
        "check_async_task or list_async_tasks. Do not start, update or cancel tasks during a query. "
        "Never invent a task ID "
        "or report a cached status as live."
    ),
    subagents=[
        AsyncSubAgent(
            name="researcher",
            description="A slow local research graph for observing background tasks.",
            graph_id="researcher",
        )
    ],
)
