> 本次执行模式：**offline**。源码指纹：`f64e82d71d66`。

# 第 1 章 Notebook：Agent Harness 与最小运行结构

对应课程章节：[第 1 章：从 Agent Framework 到 Agent Harness — Deep Agents 的诞生逻辑](../../content/ch01-agent-harness.md)

本 Notebook 用一个最小示例，把第 1 章讲的「Agent 三层架构」跑起来：先分别用 LangChain 的 `create_agent()` 和 Deep Agents 的 `create_deep_agent()` 创建最小 Agent，注册同一个工具，观察两者默认装配能力的差异，并查看一次完整 `invoke` 返回的中间状态。

## 学习目标

跑完本 Notebook 后，你应该能够：

1. 说明 LangGraph（Runtime）、LangChain（Framework）、Deep Agents（Harness）三层各自负责什么；
2. 用 `create_agent()` 创建一个最小 LangChain Agent，并注册一个本地工具；
3. 用 `create_deep_agent()` 创建一个最小 Deep Agent，对比它与前者默认工具集的差异；
4. 阅读一次 `invoke` 返回的 `messages` 列表，识别用户消息、模型消息和工具消息；
5. 通过 `MODEL_NAME` 和 API Key 环境变量配置模型，而不把密钥写进代码。

对应课程小节：

- 「Agent 开发的三个层次」：底层 Runtime / 中间层 Framework / 上层 Harness；
- 「Deep Agents 的核心设计理念」：Harness 预置的虚拟文件系统等工具；
- 「三层关系一览」：三层不是替代关系，而是自底向上层层构建。

## 运行环境与依赖

使用课程锁定的 Python 3.12 环境，安装与内核选择见 [Notebook 索引](../README.md)。从第一格独立执行，无需先运行其他章节。

```bash
uv sync --project notebooks --locked
uv run --project notebooks --locked python -m course_notebooks.run ch01-agent-harness
```

核心依赖：deepagents 0.7.15、langchain 1.4.2、langgraph 1.2.11、langchain-openai 1.6.2；完整依赖由 uv.lock 锁定。下方输出记录本次实际环境。

## 预期现象与运行模式

两种 Agent 都应实际执行 echo，返回 `echo: hello deepagents`；Deep Agent 额外暴露文件工具等 Harness 能力。

默认 offline 使用脚本模型指定工具调用，真实框架仍执行工具并产生消息。随附输出来自这个模式；它验证框架机制，不证明真实模型会正确选择工具。

需要真实模型时，按 [统一配置说明](../README.md) 准备 Key，再运行上述命令并添加 `--mode live`。live 需要网络，可能产生调用费用；缺配置或调用失败不会退回脚本模型。

## 0. 准备：确认依赖版本

打印本次模式、Python 和核心依赖，便于把运行结果与环境对应。


```python
from course_notebooks.nbtools import show_runtime

show_runtime()
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


## 1. 初始化模型：控制调用选择，保留真实执行

使用 LangChain 官方 `FakeMessagesListChatModel` 预设两条响应：先请求 echo，再结束对话。课程的 `ScriptedChatModel` 继承它，只补上工具绑定和供复杂章节使用的可选回调；本章不需要回调。是否成功由真实工具结果和后续断言判断，不能从预设的最终回复推断。

响应列表按顺序循环，两种 Agent 各完整运行一次。单独重跑或中途失败后，应从模型初始化格重新开始。切换 live 后，两种 Agent 仍使用同一个真实模型和同一个工具。

`AIMessage` 表示模型发出的消息，`tool_calls` 保存工具名、参数和调用 ID。`ToolMessage` 是框架执行 Python 工具后的返回；模型只发出请求，并不亲自执行 Python。


```python
from langchain_core.messages import AIMessage, ToolMessage
from course_notebooks.model_config import create_model
from course_notebooks.testing import ScriptedChatModel

ECHO_TEXT = "hello deepagents"

offline_responses = [
    AIMessage(content="", tool_calls=[{
        "name": "echo", "args": {"text": ECHO_TEXT}, "id": "ch01-echo",
    }]),
    AIMessage(content="工具调用流程结束；实际返回值见 ToolMessage。"),
]
```


```python
model = create_model(ScriptedChatModel(responses=offline_responses))
print("模型接口：", type(model).__name__)
```

    模型接口： ScriptedChatModel


## 2. 定义一个最简单的工具

工具是 Agent 能调用的外部能力。这里定义一个 `echo` 工具，输入什么就原样返回什么，便于观察「模型决定调用工具 → 工具执行 → 模型总结结果」这条链路。

`@tool` 将函数签名中的 `text: str` 和说明转成工具接口。框架检查参数后调用函数；函数返回的字符串随后进入 ToolMessage。


```python
from langchain_core.tools import tool


@tool
def echo(text: str) -> str:
    """原样返回传入的文本，用于演示 Agent 的工具调用。"""
    return f"echo: {text}"
```

## 3. 中间层：用 LangChain 的 `create_agent()` 创建最小 Agent

`create_agent()` 来自 LangChain 框架层。它只装配你显式传入的模型和工具——这是理解「框架层提供什么」的基线。


```python
from langchain.agents import create_agent

langchain_agent = create_agent(
    model=model,
    tools=[echo],
    system_prompt="你是一个简洁的助手。需要工具时优先调用工具，再用一句话总结结果。",
)

print("图节点:", list(langchain_agent.get_graph().nodes))
```

    图节点: ['__start__', 'model', 'tools', '__end__']


### 3.1 跑一次完整 invoke，观察中间状态

`invoke` 返回一个字典，`result["messages"]` 里按顺序记录了整条轨迹：`HumanMessage`（用户输入）→ `AIMessage`（可能带 `tool_calls`）→ `ToolMessage`（工具返回值）→ `AIMessage`（最终回答）。

```text
用户消息 → 模型产生 tool_calls → 框架运行 echo(text)
        ← 模型读取 ToolMessage ← 工具返回字符串
模型最终回复（不再请求工具）
```

LangGraph 负责这些节点之间的执行与状态传递；invoke 返回的是实际运行后的状态。


```python
question = f"请调用 echo 工具，把文本 '{ECHO_TEXT}' 原样返回，然后告诉我工具返回了什么。"
lc_result = langchain_agent.invoke({"messages": [{"role": "user", "content": question}]})

for message in lc_result["messages"]:
    message.pretty_print()
```

    ================================[1m Human Message [0m=================================
    
    请调用 echo 工具，把文本 'hello deepagents' 原样返回，然后告诉我工具返回了什么。
    ==================================[1m Ai Message [0m==================================
    Tool Calls:
      echo (ch01-echo)
     Call ID: ch01-echo
      Args:
        text: hello deepagents
    =================================[1m Tool Message [0m=================================
    Name: echo
    
    echo: hello deepagents
    ==================================[1m Ai Message [0m==================================
    
    工具调用流程结束；实际返回值见 ToolMessage。


### 3.2 检查可验证的行为

本实验明确要求成功调用 echo。仅有 ToolMessage 不够，因为参数错误也可能以 ToolMessage 返回。下面核对工具名、参数、调用 ID、成功状态和确切结果；模型最终回答的措辞可以不同。


```python
from langchain_core.messages import AIMessage, ToolMessage


def assert_echo(messages, expected_text):
    calls = [call for message in messages if isinstance(message, AIMessage)
             for call in message.tool_calls]
    expected_ids = {call["id"] for call in calls
                    if call["name"] == "echo" and call["args"] == {"text": expected_text}}
    assert expected_ids, "没有发出参数正确的 echo 调用。"
    successful = [message for message in messages if isinstance(message, ToolMessage)
                  and message.name == "echo" and message.tool_call_id in expected_ids
                  and message.status == "success"
                  and message.content == f"echo: {expected_text}"]
    assert successful, "echo 没有成功返回预期内容；检查工具错误与调用关联。"
    assert isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls, "缺少最终回复。"
    print("已验证 echo 的参数、调用关联、成功状态与返回值：", successful[-1].content)


lc_messages = lc_result["messages"]
assert_echo(lc_messages, ECHO_TEXT)
```

    已验证 echo 的参数、调用关联、成功状态与返回值： echo: hello deepagents


## 4. 上层：用 `create_deep_agent()` 创建最小 Deep Agent

`create_deep_agent()` 来自 Deep Agents（Harness 层）。传入完全相同的模型和工具，但它会额外预置一套经过验证的工具——这正是第 1 章所说的「开箱即用的 Agent 套件」。


```python
from deepagents import create_deep_agent

deep_agent = create_deep_agent(
    model=model,
    tools=[echo],
    system_prompt="你是一个简洁的助手。需要工具时优先调用工具，再用一句话总结结果。",
)

print("图节点:", list(deep_agent.get_graph().nodes))
```

    图节点: ['__start__', 'model', 'tools', 'PatchToolCallsMiddleware.before_agent', '__end__']


### 4.1 对比两层默认装配的工具

读取编译后图中 `tools` 节点绑定的工具名，是观察「框架层 vs Harness 层」差异的确定手段——不依赖模型输出。


```python
def list_tools(agent):
    """读取图中 tools 节点绑定的工具名，用于对比不同层默认装配的工具。"""
    node = agent.nodes["tools"]
    tools_by_name = getattr(node, "tools_by_name", None)
    if tools_by_name is None:
        bound = getattr(node, "bound", None)
        tools_by_name = getattr(bound, "tools_by_name", {})
    return sorted(tools_by_name)


lc_tools = list_tools(langchain_agent)
deep_tools = list_tools(deep_agent)

print("create_agent 暴露的工具       :", lc_tools)
print("create_deep_agent 暴露的工具  :", deep_tools)
print("Harness 额外提供的工具        :", [t for t in deep_tools if t not in lc_tools])

assert "write_file" in deep_tools, "Deep Agent 应默认提供虚拟文件系统工具"
print("✓ create_deep_agent 默认装配了虚拟文件系统工具（如 write_file / read_file / grep）")
```

    create_agent 暴露的工具       : ['echo']
    create_deep_agent 暴露的工具  : ['delete', 'echo', 'edit_file', 'execute', 'glob', 'grep', 'ls', 'read_file', 'task', 'write_file']
    Harness 额外提供的工具        : ['delete', 'edit_file', 'execute', 'glob', 'grep', 'ls', 'read_file', 'task', 'write_file']
    ✓ create_deep_agent 默认装配了虚拟文件系统工具（如 write_file / read_file / grep）


### 4.2 用 Deep Agent 跑同样的任务


```python
deep_result = deep_agent.invoke({"messages": [{"role": "user", "content": question}]})
for message in deep_result["messages"]:
    message.pretty_print()

assert_echo(deep_result["messages"], ECHO_TEXT)
```

    ================================[1m Human Message [0m=================================
    
    请调用 echo 工具，把文本 'hello deepagents' 原样返回，然后告诉我工具返回了什么。
    ==================================[1m Ai Message [0m==================================
    Tool Calls:
      echo (ch01-echo)
     Call ID: ch01-echo
      Args:
        text: hello deepagents
    =================================[1m Tool Message [0m=================================
    Name: echo
    
    echo: hello deepagents
    ==================================[1m Ai Message [0m==================================
    
    工具调用流程结束；实际返回值见 ToolMessage。
    已验证 echo 的参数、调用关联、成功状态与返回值： echo: hello deepagents


## 5. 三层架构在示例中的位置

| 层次 | 代表 | 本 Notebook 中的体现 |
|---|---|---|
| Runtime（底层） | LangGraph | `create_agent()` 和 `create_deep_agent()` 返回的是可运行的图；`get_graph().nodes` 里的 `model`、`tools` 节点就是 LangGraph 的执行引擎 |
| Framework（中间层） | LangChain | `from langchain.agents import create_agent`，以及统一的模型/工具接口（`ChatOpenAI`、`@tool`） |
| Harness（上层） | Deep Agents | `from deepagents import create_deep_agent`，在框架之上额外预置虚拟文件系统等工具 |

可以看到：传入相同的模型和工具时，`create_agent()` 只暴露你给的工具；`create_deep_agent()` 还会自动补齐 `write_file`、`read_file`、`grep`、`task` 等工具。这说明三层是**层层构建**而不是互相替代——Harness 复用了下面两层的运行时和框架能力。

## 5.1 回看证据与小练习

1. 两种 Agent 均应出现用户消息、带工具调用的 AIMessage、成功 ToolMessage、最终 AIMessage。
2. 两次工具实际返回相同的 `echo: hello deepagents`；默认工具集合不同。
3. 未调用、错误参数、错误返回或错误调用关联都不能通过成功验证。

**改一个变量**：修改 ECHO_TEXT，从第一格重跑，观察两种 Agent 的结果如何一起变化。随后在 offline_responses 第一条中把 args 改为 `{}`，预期工具返回参数错误，成功断言失败。恢复正确参数再执行；无需为此调用真实模型。

## 6. 常见报错、成本与清理

- offline 不需要 API Key；live 缺 Key 会在创建模型时失败，按统一 README 配置。
- 真实模型出现 401、网络错误或超时，检查凭证、端点和网络；模型不调用 echo 时实验应失败，不能把直接回答当成调用成功。
- 本示例的 Agent 状态在内存中；重启内核后从头运行即可清理。
- 不提交 `.env`、Key 或未经检查的输出；本次模式以开头和执行报告为准。

下一步阅读 [第 2 章：快速上手](../../content/ch02-quickstart.md)。
