> 本次执行模式：**offline**。源码指纹：`edec4739e74e`。

# 最小工具实验：谁执行了 echo？

模型可以提出“请调用这个工具”，但谁真正运行 Python 函数？这份实验用一个只返回文本的工具，把这个过程拆开观察。

你只需会写 Python 函数、列表、字典和 `for` 循环，不需要先学 LangChain。第一次使用 Notebook，先看 [入门与运行说明](../README.md)。这份最小实验也供后续章节作者复制。

**预期现象**：工具实际返回 `echo: hello course`，随后出现模型回复。默认使用无需 Key 的脚本模型；它预先安排模型消息，工具函数和框架仍真实执行。

## 1. 环境与模式

按 [统一安装说明](../README.md) 准备 Python 3.12 环境，在项目内核中从第一格依次运行。代码格左侧出现执行编号，表示该格运行过；没有打印内容的定义格也可能正常完成。

下一格的 `show_runtime()` 打印环境，`TEXT` 是我们准备交给工具的文本。`course_notebooks` 是随课程安装的辅助包：`create_model()` 选择 offline 或 live，`ScriptedChatModel` 提供离线响应。先保持默认 offline，学会观察结果后再切换真实模型。


```python
from course_notebooks.nbtools import show_runtime
from course_notebooks.model_config import create_model
from course_notebooks.testing import ScriptedChatModel
from langchain_core.messages import AIMessage, ToolMessage

show_runtime()
TEXT = "hello course"
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


### 先认清四个角色

| 名称 | 在本实验中做什么 |
|---|---|
| 模型 | 产生回复，或者提出带参数的工具调用 |
| 工具 | 普通 Python 函数；这里是 `echo(text)` |
| 框架 | 接收调用请求，运行工具，再把结果交回模型 |
| Agent | 把模型和工具连接起来、反复执行上述步骤的程序 |

```text
用户提出请求 → 模型提出 echo 调用 → 框架执行 Python 函数
                                      ↓
用户得到回复 ← 模型读取结果 ← ToolMessage 保存工具返回值
```

LangChain 提供本例使用的 Agent 构造函数。`AIMessage` 是模型消息，`ToolMessage` 是工具执行结果；两者承担不同的工作。

## 2. 定义工具与脚本响应

`@tool` 是装饰器：它把函数的名称、参数类型和说明整理成模型可用的工具接口。`text: str` 表示参数是字符串，三引号里的说明帮助模型理解工具用途。函数实际返回的是加上 `echo:` 前缀的文本，便于我们辨认。

为了先观察机制，使用 LangChain 官方 `FakeMessagesListChatModel` 的响应列表：第一条要求调用工具，第二条结束对话。课程的 `ScriptedChatModel` 为它补充 Agent 需要的工具绑定。它不会推理，也不会检查工具是否成功；成功与否要看实际返回值。


```python
from langchain_core.tools import tool

@tool
def echo(text: str) -> str:
    """原样返回文本，观察一次工具调用。"""
    return f"echo: {text}"


model = create_model(ScriptedChatModel(responses=[
    AIMessage(content="", tool_calls=[{
        "name": "echo", "args": {"text": TEXT}, "id": "template-echo",
    }]),
    AIMessage(content="工具调用流程结束；请检查实际 ToolMessage。"),
]))
```

### 看懂这一条调用请求

第一条 `AIMessage` 的 `tool_calls` 是一个列表，其中的字典描述一次调用：

| 字段 | 本例的值 | 用途 |
|---|---|---|
| `name` | `echo` | 选择哪个工具 |
| `args` | `{"text": TEXT}` | 把什么参数传给函数 |
| `id` | `template-echo` | 给调用编号，让返回消息能找到对应请求 |

`content=""` 表示这次没有普通文本回复，真正的请求在 `tool_calls` 中。创建这条消息尚未执行 `echo`；下一步启动 Agent 循环才会执行工具。

## 3. 运行实际 Agent 循环

`create_agent(model=..., tools=[echo])` 组装模型和工具。`invoke(...)` 才开始执行，直到模型不再请求工具。

输入里的 `messages` 是对话列表，`("user", 文本)` 是用户消息的简写。返回的 `result` 是字典，`result["messages"]` 保存运行后的消息记录。下一格逐条打印消息类型、工具名和内容；只打印前 120 个字符是为了方便阅读。


```python
from langchain.agents import create_agent

agent = create_agent(model=model, tools=[echo])
result = agent.invoke({"messages": [("user", f"调用 echo，原样返回 {TEXT}")]})
for message in result["messages"]:
    print(message.type, getattr(message, "name", None) or "", str(message.content)[:120])
    if isinstance(message, AIMessage):
        for call in message.tool_calls:
            print("  请求工具:", call["name"], "参数:", call["args"], "调用 ID:", call["id"])
    if isinstance(message, ToolMessage):
        print("  对应调用 ID:", message.tool_call_id, "执行状态:", message.status)
```

    human  调用 echo，原样返回 hello course
    ai  
      请求工具: echo 参数: {'text': 'hello course'} 调用 ID: template-echo
    tool echo echo: hello course
      对应调用 ID: template-echo 执行状态: success
    ai  工具调用流程结束；请检查实际 ToolMessage。


### 输出应该怎样读？

offline 模式下，应依次看到四条消息：

| 打印的类型 | 含义 | 重点观察 |
|---|---|---|
| `human` | 用户输入 | 要交给工具的文本 |
| `ai` | 模型提出调用 | 普通文本可为空；下方明细打印工具名、参数和调用 ID |
| `tool echo` | 工具真正返回了 | 内容应为 `echo: hello course` |
| `ai` | 本轮结束 | 这句是预设回复，不能单独作为成功证据 |

真实模型的措辞和调用次数可能不同；仍需检查工具执行的内容。

## 4. 检查学习目标

下面先从消息中收集调用请求（`calls`）和工具结果（`returns`），再逐项核对。列表推导式中的两个 `for` 表示“遍历每条模型消息，再遍历其中的工具调用”。`isinstance` 判断消息类型，`any(...)` 检查是否至少有一项满足条件。

`assert 条件` 是自动检查：条件不成立就报错并停止。这里需要同时满足：调用名称和参数正确；结果的 `tool_call_id` 能对应请求的 `id`；工具状态成功；返回文本准确。最后再确认出现模型回复。


```python
calls = [c for m in result["messages"] if isinstance(m, AIMessage) for c in m.tool_calls]
returns = [m for m in result["messages"] if isinstance(m, ToolMessage)]
assert any(c["name"] == "echo" and c["args"] == {"text": TEXT} for c in calls)
assert any(m.name == "echo" and m.status == "success" and m.content == f"echo: {TEXT}"
           and any(c["id"] == m.tool_call_id and c["name"] == "echo" for c in calls)
           for m in returns)
assert isinstance(result["messages"][-1], AIMessage)
print("已验证：调用请求 → Python 工具执行 → 工具结果 → 最终回复。")
```

    已验证：调用请求 → Python 工具执行 → 工具结果 → 最终回复。


## 改一个变量再观察

1. 把 `TEXT` 改为 `"hello junior"`，先预测工具输出，再从第一格重跑。应看到 `echo: hello junior`，成功断言仍通过。
2. 仅在 offline 模式，把响应列表第一条的 `args` 改成 `{}`。运行后检查工具错误和失败断言：`echo` 缺少必需的 `text` 参数，即使预设的模型回复照常出现，也不能算成功。
3. 恢复 `{"text": TEXT}`，重启内核并全部运行，确认实验重新通过。重启会清空变量，不能只运行最后一格。

**回顾**：模型负责提出请求，框架执行函数，ToolMessage 保存结果；一次可靠验证必须把三者对应起来。本实验不启动外部进程，重启内核即可清理内存状态。

接着运行 [第 1 章 Notebook](../ch01/01-agent-harness.ipynb)，比较基础 Agent 和 Deep Agent。章节作者再参考 [贡献指南](../CONTRIBUTING.md)。
