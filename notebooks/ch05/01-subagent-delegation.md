> 本次执行模式：**offline**。源码指纹：`e0323c4dda46`。

# 第 5 章 Notebook：子 Agent 委派与上下文隔离

对应课程章节：[第 5 章：子 Agent 与上下文隔离](../../content/ch05-subagents.md)。

本实验只使用本地固定的研究资料，不调用搜索服务。主 Agent 把比较任务交给声明式 `researcher`，子 Agent 读取资料、写入研究记录并回传结论。我们分别检查**主 Agent 的消息**和**共享的文件状态**，看清两个边界。

## 学习目标

运行结束后，你应该能够：

1. 用字典声明 `researcher`，并让主 Agent 通过 `task` 委派；
2. 从 `AIMessage.tool_calls` 与 `ToolMessage` 检查委派和结果回传；
3. 证明子 Agent 的内部工具记录不自动进入主 Agent 的 `messages`；
4. 证明默认 `StateBackend` 的文件状态会回到主 Agent，且主 Agent 可以主动读取它。

本章只讨论进程内的同步子 Agent；第 6 章另讲异步子 Agent。

## 运行环境与模式

使用 [统一安装入口](../README.md) 的 Python 3.12 锁定环境。本章从第一格独立执行，无需先运行第 1 章。

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch05-subagents
```

默认 offline 使用公开的脚本规则选择工具，task、lookup_case、write_file、read_file 与 StateBackend 均真实执行。随附输出来自这个模式，验证消息与文件边界，不证明真实模型会遵从委派指令。

要观察真实模型选择工具，按 README 配置模型并在命令后添加 `--mode live`；需要网络且可能产生费用。除模型 API 外，本章不需要搜索、数据库或沙箱。

## 0. 检查环境并准备模型

先展示本次模式与版本。脚本响应只规定工具调用的顺序，不预造工具返回或最终 Agent 状态。模型切换通过公共配置完成。


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

## 1. 定义可复现的本地资料工具

以下数字是**教学用的固定案例**，不代表真实产品测量。`lookup_case` 的入参和返回值会记录在 Python 列表中，供我们观察子 Agent 的内部工具调用；这份列表不会自动成为主 Agent 的消息。


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

## 2. 声明 researcher 并创建主 Agent

`researcher` 有自己的描述、指令和 `lookup_case` 工具。主 Agent 不注册 `lookup_case`，只负责委派和接收结果。Deep Agents 仍会为双方装配文件工具；这里不引入 Skills、Todo 或异步任务，以便只观察本章的核心行为。

`task` 的实际参数名是 `description` 和 `subagent_type`。它由主 Agent 在运行时调用，不需要我们在 Python 中手动调用。


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

预期主 Agent 先调用 `task`，随后收到子 Agent 的简短结论。模型的自然语言措辞可能变化；我们只依赖工具调用和状态来验证。


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

主 Agent 的 `AIMessage.tool_calls` 记录它选择了谁、交代了什么任务；名称为 `task` 的 `ToolMessage` 是子 Agent 的回传。这里还打印本地工具日志中的输入和返回值，作为子 Agent 确实读取资料的证据。


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

子 Agent 的 `lookup_case` 和 `write_file` 调用已经发生，但它们的内部 `ToolMessage` 不会自动并入主 Agent 的 `messages`。主 Agent 看到的是自己的 `task` 调用及其结果。这里检查的是**消息轨迹**，并不意味着子 Agent 的文件无法共享。


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

默认 `StateBackend` 把文件存在本次 Agent 的状态中。子 Agent 写入文件后，文件更新会出现在主 Agent 的返回状态。文件内容是否正确可以直接检查，无须猜测模型的最终回答。此时主 Agent **尚未主动读取**文件内容。下一格把报告的 Markdown 原文放在代码块里，避免报告标题被当作 Notebook 章节标题。


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

第二次调用把上一轮的 `messages` 和 `files` 显式传回图中，再请求 `read_file`。这不需要数据库或磁盘文件；它演示的是**同一研究流程中的状态交接**。读文件之后，该次 `read_file` 的返回才会进入主 Agent 的消息上下文。

上一格已展示完整报告。这里核对 `read_file` 读回的是同一份内容，只显示返回头和行数，避免重复打印整篇报告。


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


## 预期现象、练习与清理

- **委派与回传**：第一轮出现 task(researcher)，lookup_trace 留下实际资料工具的输入和返回。
- **消息隔离**：主 Agent 收到 task 结果，没有子 Agent 内部的 lookup_case、write_file 记录，也没有提前 read_file。
- **文件共享**：第一轮状态含报告，第二轮主 Agent 主动 read_file 才把完整报告内容读入消息。隔离消息不代表隔离 StateBackend 文件。
- **失败边界**：没有委派、缺少报告证据、提前读文件或读回不一致都会失败；真实模型不遵从指令时也应报告失败。
- **小练习**：在脚本报告中移除 `95` 后从头执行，预测哪一条断言失败；恢复后再跑。也可观察实际第一轮 messages 与 files 的不同作用。
- **清理**：本例文件在内存状态中，不写本机磁盘。重启内核后从头执行；不要提交模型凭证。

完整验证：

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch05-subagents
```

继续阅读 [第 6 章：异步子 Agent](../../content/ch06-async-subagents.md)，观察工作被交给后台服务后生命周期如何变化。
