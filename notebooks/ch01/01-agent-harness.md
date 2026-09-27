> 本次执行模式：**offline**。源码指纹：`366833ffcce5`。

# 第 1 章 Notebook：Agent Harness 与最小运行结构

对应课程章节：[第 1 章：从 Agent Framework 到 Agent Harness — Deep Agents 的诞生逻辑](../../content/ch01-agent-harness.md)。

同样给一个模型和一个 `echo` 工具，普通 Agent 与 Deep Agent 有什么不同？我们用相同输入运行两者，先看真正的工具返回，再比较它们可用的工具。

你只需基础 Python，不必预先掌握 LangChain 或 LangGraph。若还没见过工具调用，建议先做 [最小工具实验](../_template/01-minimal-tool.ipynb)。本章可以单独从第一格运行。

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

### 先理解三层分别解决什么问题

Agent 是一个“调用模型 → 按需执行工具 → 把结果交回模型”的程序。下面三个库帮助我们搭建这个程序：

| 层次 | 用普通话理解 | 本例用到的能力 |
|---|---|---|
| LangGraph：运行时（Runtime） | 决定下一步执行谁，并传递运行状态 | 在模型步骤和工具步骤之间流转 |
| LangChain：框架（Framework） | 提供统一的模型、消息、工具接口，并组装 Agent | `create_agent()` 连接我们给出的模型和工具 |
| Deep Agents：运行套件（Harness） | 在框架上预装适合多步骤任务的工具、提示和处理逻辑 | `create_deep_agent()` 额外提供文件操作、任务委派等能力 |

**图**（graph）是步骤及其连接关系；**节点**（node）是其中一个步骤，例如调用模型或执行工具。**状态**（state）是步骤之间传递的数据，例如消息列表。先记住这些直观含义，下面会看到对应代码和输出。

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


## 1. 初始化模型：先控制选择，再观察执行

这里先安排两条固定模型消息：请求 `echo`，然后结束对话。这样无需 Key，就能专心观察框架怎样执行工具。`FakeMessagesListChatModel` 是 LangChain 官方提供的固定响应模型，课程的 `ScriptedChatModel` 为它补充工具绑定。

下一格只准备消息列表，再下一格调用课程辅助函数 `create_model(...)`：默认返回这个脚本模型，显式切换 live 时才按配置创建真实模型。这个辅助函数不是 Agent 构造函数，也不会在此执行工具。

响应列表会循环。两种 Agent 各完整运行一次，正好分别消费“调用、结束”这两条消息；中途失败或想重新实验时，重启内核并从头执行，避免响应位置与预期不一致。脚本最后的回复不是成功证据，后面会核对实际工具返回。

`AIMessage` 表示模型发出的消息。它可以包含普通文本，也可以通过 `tool_calls` 请求工具：

| 字段 | 本例 | 含义 |
|---|---|---|
| `name` | `echo` | 选择工具 |
| `args` | `{"text": ECHO_TEXT}` | 传给函数的参数 |
| `id` | `ch01-echo` | 本次调用的编号，用于关联返回结果 |

框架执行函数后，把返回值放进 `ToolMessage`，并用 `tool_call_id` 标记它属于哪个调用。模型发出请求，框架运行 Python；这两步不是同一件事。`content=""` 的调用消息没有普通文本，但不表示调用内容缺失。


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

工具是 Agent 能请求执行的函数。`echo` 接收字符串，再加上 `echo:` 前缀返回，方便我们辨认它确实运行过。

`@tool` 是 Python 装饰器：它把函数名、`text: str` 参数类型和三引号说明整理成工具接口。模型用这些信息提出调用；框架检查参数后运行函数，再生成 ToolMessage。这个工具不搜索、不读文件，也不请求网络。


```python
from langchain_core.tools import tool


@tool
def echo(text: str) -> str:
    """原样返回传入的文本，用于演示 Agent 的工具调用。"""
    return f"echo: {text}"
```

## 3. 中间层：用 LangChain 的 `create_agent()` 创建最小 Agent

下面传入三个关键参数：`model` 决定用哪个模型，`tools=[echo]` 指定可用工具，`system_prompt` 给模型一条持续生效的行为说明。它与随后用户提出的具体问题不同。

这个最小配置没有加入额外工具。`create_agent()` 返回可运行的图；`get_graph().nodes` 只查看图的步骤名称，还没有运行用户任务。实际执行从下一节的 `invoke()` 开始。


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

输入字典里的 `messages` 是消息列表。每条输入消息的 `role="user"` 表示用户角色，`content` 是用户说的话。`invoke` 执行图并返回状态字典，我们从 `lc_result["messages"]` 读取运行后的对话。

```text
HumanMessage：用户请求
      ↓
AIMessage：模型请求 echo(text=...)
      ↓  框架运行 Python 工具
ToolMessage：echo: hello deepagents
      ↓
AIMessage：本轮结束
```

`pretty_print()` 只负责把消息打印得便于阅读。offline 模式下应看到上述四步；第一条 AIMessage 的普通文本可以为空，要看它下面的 Tool Calls。重点找到 `ToolMessage` 中的 `echo: hello deepagents`，再看下一节如何自动验证。


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

参数错误也可能产生 ToolMessage，因此“有返回消息”还不够。下面的 `assert_echo` 是本章自定义的检查函数，两种 Agent 都会复用它。

按三步阅读即可：先找名称和参数正确的调用 ID，再找同 ID 且状态为 `success` 的工具结果，最后确认模型已结束工具调用。`assert` 不满足时会停止并显示原因；列表和集合推导式只是从消息里筛出符合条件的项目。

通过时应打印“已验证 echo 的参数、调用关联、成功状态与返回值”。模型最终回答的措辞可以不同，实际工具返回必须符合约定。


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

保持模型、`echo` 工具和行为说明相同，只把构造函数换为 Deep Agents 的 `create_deep_agent()`。它会额外预装文件操作、任务委派等工具及配套处理逻辑。

我们要观察的是“程序默认装配了什么”，不是比较两种模型谁更聪明。下一节先列出可用工具，再运行同一个 echo 任务。


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

**工具已注册**表示模型可以选择它；**工具已调用**表示本次任务真的执行了它。这一格只比较注册清单，不要求模型使用额外工具。

`list_tools` 是本章的观察辅助函数：在图的 `tools` 节点里读取工具名，再排序打印。它使用本课程锁定版本的图内部结构，第一次学习可先关注三行输出，不需要记住内部属性路径。

预期：基础 Agent 的清单只有 `echo`；Deep Agent 包含 `echo`，还包含 `write_file`、`read_file` 等。这里的文件工具默认操作 Agent 状态中的虚拟文件，不等于可以随意读取你电脑上的文件。


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

问题、文本和检查函数都不变。即使 Deep Agent 多了很多工具，本轮仍只需要 `echo`。比较两次 ToolMessage：实际返回内容应相同；变化的是可用工具集合。


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


## 5. 用本次证据回看三层架构

| 看到的现象 | 它说明什么 |
|---|---|
| 图中有模型、工具等节点，消息按执行顺序返回 | LangGraph 驱动这些步骤，并传递状态；节点名称本身不是执行引擎 |
| `create_agent()` 能连接模型和 `echo` | LangChain 提供基础 Agent 组装及统一接口 |
| `create_deep_agent()` 还暴露文件、委派等工具 | Deep Agents 在下层能力上提供预先装配的运行套件 |

这次没有测试长期记忆、规划质量或复杂任务效果，不能从一次 echo 实验推出这些结论。你已经观察到的是：相同工具都能执行，默认装配的能力不同，三层可以共同工作。

## 5.1 先预测，再动手

1. 把 `ECHO_TEXT` 改为 `"hello junior"`，重启内核并全部运行。预测：两种 Agent 都应返回 `echo: hello junior`，可用工具清单不变。
2. 仅在 offline 模式，把 `offline_responses` 第一条的 `args` 改成 `{}`。先找工具消息里的错误，再看 `assert_echo` 在哪一步停止。
3. 恢复正确参数，从头运行。核对思路：`echo(text)` 必须有 `text`；预设的最终 AIMessage 即使出现，也不能替代成功的工具结果。

再试着用自己的话回答：为什么 Deep Agent 有 `write_file`，本次对话却没有调用它？因为可用工具清单与本轮实际调用记录是两回事。

## 6. 常见报错与清理

| 现象 | 先检查什么 |
|---|---|
| `ModuleNotFoundError` | 是否完成安装，是否选择 `notebooks/.venv` 的项目内核；见 [统一安装说明](../README.md) |
| `NameError`，例如 `model` 未定义 | 是否跳过了前面的代码格；重启内核并从头运行 |
| echo 检查失败 | 对照调用参数、ToolMessage 的 `status` 和 `tool_call_id`，不要只看最后一句模型回复 |
| live 缺 Key、401 或网络超时 | 检查根目录 `.env`、模型端点与网络；offline 无需这些凭证 |

本例状态保存在内存中，重启内核即可清理；重启后变量也会消失。不要提交 `.env`、Key 或未经检查的输出。

继续学习课程可读 [第 2 章：快速上手](../../content/ch02-quickstart.md)；想继续做本批实验，可打开 [第 5 章 Notebook](../ch05/01-subagent-delegation.ipynb)。
