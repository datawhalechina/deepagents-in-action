> 本次执行模式：**offline**。源码指纹：`e6eda366327c`。

# 最小工具实验：谁执行了 echo？

学习目标：区分模型发出的工具调用、框架执行的 Python 函数与工具返回。模板只需基础 Python；复制后替换为本章的问题和正文入口。

**预期现象**：模型产生一次 echo 调用，工具返回 `echo: hello course`，最终回复在工具返回之后。默认脚本模型控制调用选择，实际框架和工具仍执行；它不证明真实模型的决策能力。

## 1. 环境与模式

先按 [统一安装说明](../README.md) 准备 Python 3.12 环境。默认 offline 不需要 API Key；真实模型需显式选择 live。


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


## 2. 定义工具与脚本响应

`@tool` 把带类型和说明的 Python 函数注册为模型可选择的工具。AIMessage 的 tool_calls 只是调用请求；框架执行函数后才生成 ToolMessage。

这里使用 LangChain 官方 `FakeMessagesListChatModel` 的响应列表：第一条请求工具，第二条结束对话。课程的 `ScriptedChatModel` 只补上 Agent 所需的工具绑定；预设的最终回复不代表工具成功，仍须检查真实 ToolMessage。


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

## 3. 运行实际 Agent 循环

`create_agent` 连接模型和工具；`invoke` 接收消息，循环执行到模型不再请求工具。下面的状态由实际框架产生。


```python
from langchain.agents import create_agent

agent = create_agent(model=model, tools=[echo])
result = agent.invoke({"messages": [("user", f"调用 echo，原样返回 {TEXT}")]})
for message in result["messages"]:
    print(message.type, getattr(message, "name", None) or "", str(message.content)[:120])
```

    human  调用 echo，原样返回 hello course
    ai  
    tool echo echo: hello course
    ai  工具调用流程结束；请检查实际 ToolMessage。


## 4. 检查学习目标

我们检查确切参数、关联调用 ID、成功状态和结果，而不是只检查消息数量。


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

把 TEXT 改为另一段文本，从第一格重跑，预测工具结果会如何改变。若删除响应列表第一条中的 text 参数，框架会产生错误工具结果，成功断言应失败。

本实验不启动外部进程；重启内核即可清理内存状态。制作章节时按 [贡献指南](../CONTRIBUTING.md) 添加与该章有关的失败分支、清理说明和下一步。
