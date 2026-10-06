"""Local compatibility for OpenAI-compatible Chat Completions streams."""
from copy import deepcopy

from langchain_openai import ChatOpenAI


class StreamingChatOpenAI(ChatOpenAI):
    """Keep empty continuation names from erasing a v3 tool call's name.

    langchain-core 1.6.6's v3 compat bridge replaces a tool name whenever
    the next delta is not None. Some compatible providers send "" instead
    of None after the first chunk. Normalize that placeholder before both
    the sync and async ChatOpenAI paths construct messages or emit callbacks.

    This private conversion hook is covered by SDK/graph integration tests.
    Remove the adapter when an upstream upgrade passes those tests without it.
    """

    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        chunk = deepcopy(chunk)
        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices", [])
        for choice in choices:
            for call in (choice.get("delta") or {}).get("tool_calls") or []:
                function = call.get("function") or {}
                if function.get("name") == "":
                    function["name"] = None
        return super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info,
        )
