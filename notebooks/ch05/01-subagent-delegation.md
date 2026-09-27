> 本次执行模式：**offline**。源码指纹：`a14c406605a2`。

# 第 5 章 Notebook：子 Agent 委派与上下文隔离

对应课程章节：[第 5 章：子 Agent 与上下文隔离](../../content/ch05-subagents.md)。

把研究任务交给另一个 Agent 后，主 Agent 会看到它的全部工作过程吗？如果子 Agent 写了文件，主 Agent 又怎样拿到文件？本实验分别观察**消息记录**和**文件状态**，回答这两个问题。

例子使用本地固定的 A/B 方案资料：主 Agent 负责委派，名为 `researcher` 的子 Agent 查资料、写报告，再返回简短结论。不调用搜索服务。建议先读 [第 1 章的消息与工具循环](../ch01/01-agent-harness.ipynb)；运行时无需保留其他 Notebook 的变量。

## 学习目标

运行结束后，你应该能够：

1. 用字典声明 `researcher`，并让主 Agent 通过 `task` 委派；
2. 从 `AIMessage.tool_calls` 与 `ToolMessage` 检查委派和结果回传；
3. 证明子 Agent 的内部工具记录不自动进入主 Agent 的 `messages`；
4. 证明默认 `StateBackend` 的文件状态会回到主 Agent，且主 Agent 可以主动读取它。

本章只讨论进程内的同步子 Agent；第 6 章另讲异步子 Agent。

### 先把“上下文”和“状态”分开

| 名称 | 本例中的含义 |
|---|---|
| 主 Agent | 接收用户问题，决定把研究工作交给谁 |
| 子 Agent | 接收一项具体任务，在自己的消息记录里使用工具，再返回结果 |
| `messages` / 消息上下文 | 模型在本轮对话中使用的消息记录；包含用户输入、模型消息和工具结果 |
| state / 状态 | 程序传递的数据包；除 `messages` 外，还可以包含 `files` |
| `StateBackend` | 本例默认的文件存储方式：把文件内容放在 Agent 状态里，不写电脑磁盘 |

**同步委派**表示主 Agent 的这次 `task` 调用要等子 Agent 返回，才能继续处理结果。下面的流程发生在同一 Python 进程内：

```text
主 Agent：task(description=任务说明, subagent_type="researcher")
              ↓
researcher：lookup_case 查资料 → write_file 写报告 → 返回简短结论
              ↓
主 Agent：收到 task 的工具结果；返回状态中还包含文件更新
              ↓  下一轮明确要求读文件
主 Agent：read_file → 报告正文进入本轮工具消息
```

消息隔离不等于文件隔离，也不等于安全沙箱；我们只验证本例这两种数据怎样传递。

## 运行环境与模式

使用 [统一安装入口](../README.md) 的 Python 3.12 锁定环境。本章从第一格独立执行，无需先运行第 1 章。

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch05-subagents
```

默认 offline 使用公开的脚本规则选择工具，task、lookup_case、write_file、read_file 与 StateBackend 均真实执行。随附输出来自这个模式，验证消息与文件边界，不证明真实模型会遵从委派指令。

要观察真实模型选择工具，按 README 配置模型并在命令后添加 `--mode live`；需要网络且可能产生费用。除模型 API 外，本章不需要搜索、数据库或沙箱。

## 0. 确认环境并导入辅助函数

`show_runtime()` 打印运行模式与版本，`show_text()` 让长输出分行。它们来自课程辅助包。`HumanMessage` 是用户输入，`AIMessage` 是模型回复或工具请求，`ToolMessage` 是工具返回。

先准备本地资料和工具，再准备脚本模型，最后组装 Agent。此时还没有执行研究任务。


```python
from course_notebooks.nbtools import show_runtime, show_text
from course_notebooks.model_config import create_model
from course_notebooks.testing import ScriptedChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

show_runtime()
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


## 1. 定义可复现的本地资料工具

问题是：A、B 两种方案，哪个同时满足响应速度、数据新鲜度和错误率的约束？以下数字是**固定教学案例**，不代表真实产品测量。

`p95` 是第 95 百分位延迟：可以粗略理解为约 95% 的请求不超过这个耗时，不是平均耗时。A 的 420 ms 超过 150 ms 上限；B 的 95 ms、5 分钟更新间隔和 0.6% 错误率均满足本例约束。因此我们预期报告保留证据并选择 B。

`@tool` 把 Python 函数及其参数、说明注册为工具。`lookup_trace` 是我们用来观察实际调用的 Python 列表；向它追加记录，并不会自动给主模型追加消息。`REPORT_PATH` 是虚拟文件的名称，不能拿这个路径去电脑磁盘上找文件。


```python
from langchain_core.tools import tool

CASE_ID = "cache-plan"
REPORT_PATH = "/research/cache-choice.md"
CASE_MATERIAL = """[A] 实时汇总：同一组 1000 次请求中，p95 延迟 420 ms，错误率 0.4%。
[B] 每 5 分钟更新一次缓存：同一组请求中，p95 延迟 95 ms，错误率 0.6%。
[约束] p95 必须低于 150 ms；允许结果最多延迟 5 分钟；错误率必须低于 1%。"""
lookup_trace = []

@tool
def lookup_case(case_id: str) -> str:
    """读取本地固定的缓存方案研究材料。case_id 应为 cache-plan。"""
    result = CASE_MATERIAL if case_id == CASE_ID else f"未知案例：{case_id}"
    lookup_trace.append({"case_id": case_id, "result": result})
    return result
```

### 1.1 准备无需 Key 的模型响应

`responder` 是一个回调函数：框架每次向脚本模型请求回复时，调用 `scripted_reply(messages, tool_names)`。`messages` 是当前 Agent 的消息记录，`tool_names` 是它当前可用的工具名。

下面按两个输入选择下一条响应，没有直接伪造 Agent 的最终状态：

| 当前角色/情况 | 脚本提出的请求 |
|---|---|
| 工具清单含 `lookup_case`，说明当前是 researcher | 先查资料，再 `write_file`，最后返回摘要 |
| 主 Agent 收到第一轮研究问题 | 调用 `task` 委派给 researcher |
| 主 Agent 收到第二轮明确读文件的要求 | 调用 `read_file` |
| 主 Agent 已收到 ToolMessage | 结束本轮 |

第一次可以按这张表理解并运行函数，不必逐行背下分支。报告文字也是预设的，所以这个模式不能证明模型具备比较方案的能力；它检验的是实际工具执行、委派和数据传递。修改教学资料时，也要检查脚本报告和后面的断言是否仍匹配。


```python
def scripted_reply(messages, tool_names):
    calls = [call["name"] for message in messages if isinstance(message, AIMessage)
             for call in message.tool_calls]
    if "lookup_case" in tool_names:  # 只有 researcher 注册了资料工具
        if "lookup_case" not in calls:
            name, args = "lookup_case", {"case_id": CASE_ID}
        elif "write_file" not in calls:
            # 固定教学报告；下面的 write_file 仍由实际工具执行。
            name, args = "write_file", {"file_path": REPORT_PATH, "content":
                "[A] p95 420 ms，错误率 0.4%。\n[B] p95 95 ms，错误率 0.6%。\n"
                "[约束] p95 <150 ms；最多延迟5分钟；错误率 <1%。\n结论：方案 B 满足约束。"}
        else:
            return AIMessage(content=f"方案 B 满足约束，报告位于 {REPORT_PATH}。")
    elif isinstance(messages[-1], ToolMessage):
        return AIMessage(content=f"已收到工具结果：{messages[-1].name}。")
    else:
        request = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
        if "read_file" in request:
            name, args = "read_file", {"file_path": REPORT_PATH}
        else:
            name, args = "task", {"subagent_type": "researcher", "description":
                "研究 cache-plan，读取固定资料，比较约束并将短报告写入 /research/cache-choice.md。"}
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"ch05-{name}"}])


model = create_model(ScriptedChatModel(responder=scripted_reply))
```

## 2. 声明 researcher 并创建主 Agent

“声明子 Agent”就是用一个字典告诉框架它的名字、用途和可用工具：

| 字段 | 谁使用它 |
|---|---|
| `name` | 主 Agent 用 `subagent_type` 选择这个子 Agent |
| `description` | 告诉主 Agent 哪类工作适合交给它 |
| `system_prompt` | 指导子 Agent 自己怎样完成工作 |
| `tools` | 给子 Agent 的自定义工具，这里是 `lookup_case` |

主 Agent 的 `tools=[]` 表示没有额外传入自定义工具，**不表示完全没有工具**：Deep Agents 仍会装配 `task`、文件操作等内置工具。本实验聚焦委派和文件传递，不使用其他默认能力来推进任务。

主 Agent 在运行时通过 `task(description=..., subagent_type="researcher")` 委派；我们不在 Python 中手动调用这个工具。第一轮提示它暂不读文件，是为了先观察“文件已存在，但正文还没通过 read_file 返回”的状态。


```python
from deepagents import create_deep_agent

researcher = {
    "name": "researcher",
    "description": "研究本地 cache-plan 案例，比较 A、B 两种方案，并把证据写入文件。",
    "system_prompt": f"""你是研究员。处理 cache-plan 时：
1. 调用 lookup_case(case_id="{CASE_ID}") 获取资料；
2. 根据资料比较 A、B 与约束，使用 write_file 把短报告写入 {REPORT_PATH}；
3. 报告中保留 [A]、[B]、[约束] 三个资料标签，并给出结论；
4. 最终只返回一两句结论及文件路径，不复制整段原始资料。""",
    "tools": [lookup_case],
}

agent = create_deep_agent(
    model=model,
    tools=[],
    system_prompt=(
        "你是协调者。遇到 cache-plan 研究任务，必须调用 task，"
        "并指定 subagent_type=researcher。研究资料由 researcher 的 lookup_case 工具提供，"
        "报告写入虚拟文件；不要要求搜索磁盘。收到结果后简短转述，"
        "本轮不要调用 lookup_case 或 read_file。后续用户明确要求读文件时再调用 read_file。"
    ),
    subagents=[researcher],
)
```

## 3. 委派一次研究任务

`invoke` 接收输入状态并运行 Agent；`messages` 中的 `role="user"` 和 `content` 分别表示说话角色和问题文本。返回的 `first_result` 包含本轮消息以及更新后的文件状态。

预期主 Agent 调用 `task`，等待 researcher 查资料、写报告，再收到简短回传。下一格只打印消息数，后面两节会打开消息内容检查。消息数本身不证明委派成功。


```python
first_result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "请把 cache-plan 案例交给 researcher：比较 A、B 哪个满足约束，保存有证据的短报告，然后告诉我结论。",
    }]
})
print("本轮主 Agent 消息数:", len(first_result["messages"]))
```

    本轮主 Agent 消息数: 4


### 3.1 检查 `task` 的输入与返回

`AIMessage.tool_calls` 记录主 Agent 选择了谁、交代了什么任务；名称为 `task` 的 ToolMessage 保存子 Agent 的回传。代码里的列表推导式负责从全部消息中筛出这两类记录。

预期输出按顺序给出：委派对象 `researcher`、任务说明、简短结论及文件路径、`lookup_case` 实际读到的 A/B 资料。最后一项来自 Python 观察列表 `lookup_trace`，不是从主 Agent 消息里复制出来的。


```python
from langchain_core.messages import AIMessage, ToolMessage

task_calls = [
    call
    for message in first_result["messages"]
    if isinstance(message, AIMessage)
    for call in message.tool_calls
    if call["name"] == "task"
]
task_results = [
    message
    for message in first_result["messages"]
    if isinstance(message, ToolMessage) and message.name == "task"
]
assert any(call["args"].get("subagent_type") == "researcher" for call in task_calls), (
    "主 Agent 没有委派给 researcher；请检查 MODEL_NAME 是否支持工具调用，以及主 Agent 提示词。"
)
assert task_results and str(task_results[-1].content).strip(), "task 没有返回可观察的结果。"
assert any(item["case_id"] == CASE_ID for item in lookup_trace), (
    "researcher 没有读取固定资料；请检查它是否调用 lookup_case。"
)

print("委派对象:", task_calls[0]["args"]["subagent_type"])
show_text("task 任务说明", task_calls[0]["args"]["description"])
show_text("task 返回", task_results[-1].content)
for item in lookup_trace:
    show_text(f"lookup_case({item['case_id']}) 返回", item["result"])
```

    委派对象: researcher
    
    task 任务说明
    研究 cache-plan，读取固定资料，比较约束并将短报告写入 /research/cache-choice.md。
    
    task 返回
    方案 B 满足约束，报告位于 /research/cache-choice.md。
    
    lookup_case(cache-plan) 返回
    [A] 实时汇总：同一组 1000 次请求中，p95 延迟 420 ms，错误率 0.4%。
    [B] 每 5 分钟更新一次缓存：同一组请求中，p95 延迟 95 ms，错误率 0.6%。
    [约束] p95 必须低于 150 ms；允许结果最多延迟 5 分钟；错误率必须低于 1%。


### 3.2 检查消息上下文边界

researcher 内部已经调用 `lookup_case` 和 `write_file`。主 Agent 的消息里应出现自己的 `task` 结果，不自动展开子 Agent 的逐步工具记录。

下一格应打印主 Agent 收到的工具结果名（offline 为 `['task']`），并确认第一轮没有 `read_file`。这些 `assert` 用来固定观察时机：如果主 Agent 提前读了文件，就不能再用这一轮演示“主动读取之前”的边界。

这里讨论模型消息怎样传递；Python 程序仍可能从返回状态中直接访问文件。下一节观察的正是这个区别。


```python
parent_tools = [message.name for message in first_result["messages"]
                if isinstance(message, ToolMessage)]
parent_calls = [call["name"] for message in first_result["messages"]
                if isinstance(message, AIMessage) for call in message.tool_calls]
print("主 Agent 收到的工具结果名:", parent_tools)
assert "task" in parent_tools
assert "lookup_case" not in parent_tools
assert "write_file" not in parent_tools
assert "read_file" not in parent_calls and "read_file" not in parent_tools, (
    "主 Agent 第一轮提前读了文件，无法观察读取前的消息与文件边界。"
)
print("已验证：子 Agent 工具记录未并入主消息，主 Agent 第一轮尚未主动读文件。")
```

    主 Agent 收到的工具结果名: ['task']
    已验证：子 Agent 工具记录未并入主消息，主 Agent 第一轮尚未主动读文件。


## 4. 检查共享的文件状态

默认 `StateBackend` 把文件保存在 Agent 状态中。researcher 写完报告后，我们可以用普通 Python 读取 `first_result["files"][REPORT_PATH]`。

| 谁在读取 | 现在看到了什么 |
|---|---|
| Notebook 中的 Python 代码 | 可以查看整个返回状态，包括报告文件内容 |
| 主 Agent 的模型消息 | 已有 task 的简短回传；尚未出现 read_file 返回的报告正文 |

**在 Notebook 里展示文件，不会自动把正文发送给模型。** 这也解释了为什么“消息上下文隔离”和“文件状态共享”可以同时成立。

下一格应找到虚拟文件 `/research/cache-choice.md`，报告包含 `[A]`、`[B]`、`[约束]` 和关键数值。Markdown 原文放在代码块里显示，避免报告自己的标题混入 Notebook 章节。


```python
report = first_result.get("files", {}).get(REPORT_PATH)
assert report is not None, f"researcher 未在共享状态中写入 {REPORT_PATH}。"
report_text = report["content"]
assert all(label in report_text for label in ("[A]", "[B]", "[约束]", "420", "95")), (
    "报告缺少固定资料标签或关键延迟数据；请检查 researcher 的 write_file 调用。"
)
from IPython.display import Markdown, display

print("共享文件:", REPORT_PATH)
display(Markdown("````markdown\n" + report_text.rstrip() + "\n````"))
```

    共享文件: /research/cache-choice.md



````markdown
[A] p95 420 ms，错误率 0.4%。
[B] p95 95 ms，错误率 0.6%。
[约束] p95 <150 ms；最多延迟5分钟；错误率 <1%。
结论：方案 B 满足约束。
````


### 4.1 让主 Agent 主动读取文件

本例没有配置跨调用的持久化保存。第二次 `invoke` 显式传回 `messages` 和 `files`，不能假设同一个 Agent 对象会自动记住上一轮数据。

`*first_result["messages"]` 是 Python 列表展开：把旧消息逐条放进新列表，再追加用户的读文件要求。传入 `files` 则把同一份虚拟文件交给新一轮。`new_messages` 通过切片只取新产生的消息。

这次 `read_file` 返回后，报告正文才作为工具消息进入主 Agent 的上下文。预期输出包括文件返回头、报告行数和“已读回共享状态中的完整报告”；代码会确认读回文本包含上一格的完整报告，避免重复打印整篇正文。


```python
second_result = agent.invoke({
    "messages": [
        *first_result["messages"],
        {"role": "user", "content": f"请使用 read_file 读取 {REPORT_PATH}，再简短告诉我报告的结论。"},
    ],
    "files": first_result["files"],
})
new_messages = second_result["messages"][len(first_result["messages"]):]
read_results = [
    message
    for message in new_messages
    if isinstance(message, ToolMessage) and message.name == "read_file"
]
assert read_results, "主 Agent 未调用 read_file；请换用能可靠调用工具的 MODEL_NAME 后重跑。"
read_text = str(read_results[-1].content)
assert report_text.strip() in read_text, "read_file 读回的内容与共享状态中的报告不一致。"
print("read_file 返回头:", read_text.splitlines()[0])
print("已读回共享状态中的完整报告：", len(report_text.splitlines()), "行")
print("已验证：消息上下文隔离，文件状态共享；主 Agent 主动读取后才看到文件内容。")
```

    read_file 返回头: @@ lines 1-4 of 4 @@
    已读回共享状态中的完整报告： 4 行
    已验证：消息上下文隔离，文件状态共享；主 Agent 主动读取后才看到文件内容。


## 回顾、练习与清理

本次证据有三部分：主 Agent 通过 task 得到简短回传；子 Agent 内部工具记录没有自动进入主消息；文件更新回到主状态，第二轮主动 read_file 才把正文带入主消息。

### 练习：聊天里的文件路径能代替文件内容吗？

1. 保持 offline，在第二次 `agent.invoke` 中暂时去掉 `"files": first_result["files"]`，其余输入不变。先预测：已有的 task 摘要还在，但新一轮是否还能读到报告？
2. 只重跑第二次调用那一格。它应在完整内容断言处停止；另开一格运行 `print(read_text)`，查看实际的文件读取错误。`read_text` 在断言之前已经赋值，所以失败后仍可查看。核对思路：聊天记录包含文件路径，不等于这次状态里有该文件。
3. 恢复 `files`，重启内核并全部运行，确认内容检查重新通过。

另一个小练习：在脚本报告中移除 `95`，从头运行，观察“报告缺少关键延迟数据”的断言。它检查证据完整性，不是在评价文笔。

| 失败位置 | 先检查什么 |
|---|---|
| 没有 task / 没有 lookup_trace | 是否按顺序创建模型、工具和 Agent；live 时模型是否遵从委派要求 |
| `report is None` | 子 Agent 是否执行 write_file，写入路径是否正确 |
| 第一轮出现 read_file | 提前读文件破坏了本次观察时机，应排查调用记录 |
| 第二轮读回内容不一致 | 是否传回 files，是否读了同一路径 |

文件和观察列表都在本例内存状态中，重启内核即可清理，不会在电脑磁盘留下这份虚拟报告。可用下面的终端命令重新独立执行；完成后继续 [第 6 章 Notebook](../ch06/01-async-subagent-lifecycle.ipynb)。

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch05-subagents
```
