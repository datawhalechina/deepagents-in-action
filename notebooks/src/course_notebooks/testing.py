"""A thin tool-calling adapter around LangChain's official fake chat model."""
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field


class ScriptedChatModel(FakeMessagesListChatModel):
    """Use official response-list replay, or a message-aware chapter callback.

    Response lists cycle in order; use a fresh instance for independent experiments.
    Callbacks receive the current messages and this binding's tool names, which
    supports shared supervisor/researcher models and runtime-generated task IDs.
    In both cases the actual Agent framework executes the requested tools.
    """

    responses: list[BaseMessage] = Field(default_factory=list)
    responder: Callable[[list[BaseMessage], tuple[str, ...]], AIMessage] | None = Field(
        default=None, exclude=True
    )

    def bind_tools(self, tools: Sequence[Any], *, tool_choice=None, **kwargs):
        names = tuple(convert_to_openai_tool(tool)["function"]["name"] for tool in tools)
        # Keep the response cursor on the original model; each Agent step rebinds.
        return self.bind(tool_names=names)

    def _generate(self, messages, stop=None, run_manager=None, *, tool_names=(), **kwargs):
        if self.responder is None:
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        response = self.responder(messages, tool_names)
        if not isinstance(response, AIMessage):
            raise TypeError("脚本模型必须返回 AIMessage；Agent 状态由实际框架产生。")
        return ChatResult(generations=[ChatGeneration(message=response)])
