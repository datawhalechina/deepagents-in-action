# 第 14 章：Streaming — 实时观察主 Agent、子 Agent 与工具调用

> `invoke()` 只告诉你运行到了哪里；Streaming 让你看到它是怎样走到这里的。本章用一个强制委派研究任务的 Deep Agent，分别观察 coordinator、researcher、工具调用和最终输出，并把产品级的 Event Streaming v3 与底层 LangGraph v2 协议放在各自清晰的位置。

本章的代码以 Deep Agents v0.6 引入的 Typed Projection API 为主线。对于新应用，优先从 `agent.stream_events(..., version="v3")` 开始；它为消息、工具调用、子 Agent 和最终状态提供独立投影。`agent.stream(..., version="v2")` 仍然有价值，但它更接近底层图执行协议，适合调试 namespace、custom updates 或迁移已有 LangGraph 代码。

## 1. 为什么最终结果不够

最小的 Agent 调用通常是：

```python
result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
print(result["messages"][-1].content)
```

它适合一次性脚本，却隐藏了几个对真实应用很重要的问题：

- coordinator 是否真的委派了任务，还是自己回答了；
- 哪个子 Agent 正在运行，何时完成，是否失败或被中断；
- 工具调用正在等待、增量参数是否还没结束、工具结果是否报错；
- 主 Agent 与子 Agent 的文本为什么交错，页面应该把它放到哪张卡片；
- 最终答案之前是否已经发生了多轮工具调用或上下文压缩。

Streaming 是运行时的观察面。它把“等待一个最终值”改成“消费一组随运行产生的事件”，但它本身不等于并行执行，也不会自动提供持久化、重放、取消或背压。那些能力仍需要应用和运行时单独设计。

## 2. 先固定一个可观察的案例

本章后面的片段都围绕同一个 coordinator。系统提示词要求它把研究请求交给 `researcher`，这样我们可以稳定地看到子 Agent 生命周期，而不是依赖模型偶然选择 `task` 工具。

```python
import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI


model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "zai-org/GLM-5.2"),
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
)

agent = create_deep_agent(
    model=model,
    system_prompt=(
        "You are a coordinator. Delegate every research request to the "
        "researcher subagent. Do not research the topic yourself. "
        "After the subagent returns, summarize its result in two sentences."
    ),
    subagents=[
        {
            "name": "researcher",
            "description": "Researches a topic and returns a concise summary.",
            "system_prompt": (
                "Research the topic, use available tools when useful, "
                "and return a concise evidence-aware summary."
            ),
        }
    ],
)

input = {
    "messages": [
        {"role": "user", "content": "Research recent Agent streaming patterns"}
    ]
}
```

如果模板或模型供应商使用不同的环境变量，只需替换模型初始化；后续 Streaming 代码不依赖具体供应商。为了让案例具有可观察的工具事件，模板中的搜索工具和模型都必须支持工具调用。

## 3. Streaming 的层级模型

把一次运行拆成四层，可以先决定页面如何呈现，再决定消费哪个投影：

| 层级 | 看到的对象 | 适合呈现 |
| --- | --- | --- |
| Coordinator | 顶层 Agent 的消息、工具调用和最终状态 | 主对话、总体进度 |
| Subagent | 一次 `task` 委派对应的子 Agent handle | 子任务卡片、状态和摘要 |
| Tool call | 某一层 Agent 发起的工具、参数增量和结果 | 工具状态、参数预览、错误 |
| Output | 一层 Agent 的最终状态或完成信号 | 收起详情、更新最终答案 |

v3 的 `stream.subagents` 是面向产品的委派视图：它暴露配置中的子 Agent 名称、路径和生命周期，隐藏了内部 graph node。`stream.subgraphs` 则是底层图执行结构，namespace 里可能出现 `tools:<id>` 和更深的节点路径。用户界面优先使用 `subagents`；只有需要调试协议或兼容旧代码时，才直接处理 namespace。

Projection 是惰性的。创建 `stream` 后，访问某个子 Agent 的 `.messages` 或 `.tool_calls` 才会订阅对应的流；只需要生命周期时，读取 `.status` 和 `.output` 就够了。这使得简单的 UI 不必为每一个内部事件付出成本。

## 4. 推荐主线：Event Streaming v3

### 4.1 先观察子 Agent 生命周期

`stream_events()` 返回一个带有 Typed Projection 的流对象。下面的循环只打开子 Agent 视图，并在它结束时读取最终输出：

```python
stream = agent.stream_events(input, version="v3")

for subagent in stream.subagents:
    print(subagent.name, subagent.path, subagent.status)

    try:
        output = subagent.output
        print(f"[{subagent.name}] completed")
        print(output)
    except Exception as exc:
        print(f"[{subagent.name}] failed: {exc}")
```

`name` 来自 coordinator 调用 `task` 时选择的 `subagent_type`，在本例中是 `researcher`。`path` 是该委派在 Agent 树中的 namespace 路径；`status` 可以是 `started`、`completed`、`failed` 或 `interrupted` 等生命周期状态。不要把一次 `status` 打印当成最终验收门：生产系统仍应记录错误、超时和取消原因。

### 4.2 观察 coordinator 和 researcher 的消息

顶层的 `stream.messages` 只属于 coordinator；每个子 Agent handle 的 `subagent.messages` 才属于该子 Agent：

```python
stream = agent.stream_events(input, version="v3")

for message in stream.messages:
    print("[coordinator]", message.text)

for subagent in stream.subagents:
    for message in subagent.messages:
        print(f"[{subagent.name}]", message.text)
```

这段代码适合离线检查，但不适合实时页面：先完整消费 coordinator，再消费 subagents，会把已经发生的交错事件按层级重新排列。下一节会处理并发消费。

### 4.3 观察工具调用和增量输出

工具调用也按 Agent 层级隔离。顶层工具走 `stream.tool_calls`，researcher 的工具走 `subagent.tool_calls`：

```python
stream = agent.stream_events(input, version="v3")

for call in stream.tool_calls:
    print("[coordinator tool]", call.tool_name, call.input)
    print("completed:", call.completed, "error:", call.error)

for subagent in stream.subagents:
    for call in subagent.tool_calls:
        print(f"[{subagent.name} tool]", call.tool_name, call.input)

        for delta in call.output_deltas:
            print(delta, end="", flush=True)

        if call.completed and call.error is None:
            print("\nresult:", call.output)
        elif call.error is not None:
            print("\nerror:", call.error)
```

这里需要区分三种状态：参数或输出仍在增量到达、调用已经完成、调用已经完成但带有错误。UI 可以把前两种分别映射成“运行中”和“已完成”，错误则保留在对应的工具卡片，不要静默当成空结果。

### 4.4 递归观察嵌套子 Agent

子 Agent 也拥有 `.messages`、`.tool_calls`、`.subagents` 和 `.output` 等投影。因此可以递归进入更深的委派：

```python
stream = agent.stream_events(input, version="v3")

for subagent in stream.subagents:
    print(f"subagent {subagent.name}: {subagent.status}")

    for tool_call in subagent.tool_calls:
        print(f"{tool_call.tool_name}({tool_call.input})")
        for delta in tool_call.output_deltas:
            print(delta, end="", flush=True)

    for nested in subagent.subagents:
        print(f"nested subagent {nested.name}: {nested.status}")
```

递归消费时给每个节点保存稳定的 `path`，不要只使用 `name` 作为唯一键。两个同名子 Agent 可能来自不同的委派分支，页面状态应该按路径区分。

## 5. 让实时 UI 保留交错顺序

### 5.1 异步：并发消费各个投影

coordinator 和 subagent 的输出可能交错到达。异步应用用 `astream_events` 和 `asyncio.gather` 同时消费：

```python
import asyncio


async def stream_live():
    stream = await agent.astream_events(input, version="v3")

    async def consume_coordinator():
        async for message in stream.messages:
            print("[coordinator]", await message.text)

    async def consume_subagents():
        async for subagent in stream.subagents:
            async for message in subagent.messages:
                print(f"[{subagent.name}]", await message.text)

    await asyncio.gather(consume_coordinator(), consume_subagents())


asyncio.run(stream_live())
```

真实前端通常不会直接 `print`，而是把事件转换为带有 `source`, `path`, `kind`, `status` 和 `delta` 的内部消息，再通过 WebSocket 或 SSE 推送。并发消费解决的是“不要阻塞某一层”，并不自动给事件加上跨投影的全局顺序。

### 5.2 同步：使用 `interleave`

同步服务或命令行程序可以使用 `stream.interleave(...)` 在一个循环中合并投影：

```python
stream = agent.stream_events(input, version="v3")

for name, item in stream.interleave("messages", "subagents"):
    if name == "messages":
        print("[coordinator]", item.text)
    else:
        for message in item.messages:
            print(f"[{item.name}]", message.text)
```

`interleave` 适合快速构建同步展示；如果页面要求“每一个 token 的精确到达顺序”，应继续读取 raw protocol events，并用 `namespace` 路由。不要假设先创建的 projection 就先产出，也不要依次消费多个无限期运行的 projection。

## 6. 需要精确顺序时读取 raw events

v3 的投影 API 为产品语义做了分组。如果必须保留 coordinator 和所有嵌套子 Agent 的精确事件顺序，可以遍历原始协议事件：

```python
stream = agent.stream_events(input, version="v3")

for event in stream:
    if event.get("method") != "messages":
        continue

    params = event["params"]
    payload = params["data"][0]
    if not isinstance(payload, dict):
        continue
    if payload.get("event") != "content-block-delta":
        continue

    block = payload.get("delta") or {}
    if block.get("type") != "text-delta":
        continue

    namespace = params["namespace"]
    source = "subagent" if namespace else "coordinator"
    print(f"[{source}] {block['text']}", end="", flush=True)
```

raw event 的字段是协议层数据，不应在业务代码里到处散落字符串判断。建议集中写一个 adapter：它负责校验事件版本、提取 `namespace`、转换为应用内部事件；页面和业务逻辑只消费内部事件。协议升级时只改 adapter 和测试。

## 7. v3 与传统 v2：两种视角，不要混写

### 7.1 v3：面向应用的 typed projections

v3 的核心是“按语义订阅”：

```python
stream = agent.stream_events(input, version="v3")

for message in stream.messages:
    ...

for subagent in stream.subagents:
    for call in subagent.tool_calls:
        ...
```

你不需要在一个 `chunk` 字典里判断类型，也不需要自己从内部节点名称推断哪个对象是产品意义上的子 Agent。新应用的默认选择应是 v3，再按界面需要打开 `.messages`、`.tool_calls`、`.values`、`.subagents` 或 `.output`。

### 7.2 v2：统一的 `StreamPart` 协议

已有 LangGraph 代码、协议调试和 custom updates 仍可能直接使用 v2：

```python
for chunk in agent.stream(
    input,
    stream_mode=["updates", "messages", "custom"],
    subgraphs=True,
    version="v2",
):
    print(chunk["type"])  # updates / messages / custom
    print(chunk["ns"])    # () 或子图 namespace
    print(chunk["data"])   # 当前 mode 的 payload
```

每个 chunk 都有 `type`、`ns`、`data` 三个关键字段。`ns=()` 通常表示主 Agent；非空 namespace 表示子图或更深的节点。例如：

```text
()                              -> main agent
("tools:abc123",)              -> task 工具启动的子 Agent
("tools:abc123", "model:xyz")  -> 子 Agent 内部模型节点
```

不要把 v2 的 `chunk["data"]` 当成 v3 的 `message.text`，也不要把 v3 的 `subagent.name` 误当成 v2 namespace。两者的抽象层级不同：v3 关注委派和投影，v2 关注图执行路径。

### 7.3 `stream_mode`、`subgraphs=True` 与 custom updates

`stream_mode` 决定 v2 事件的 payload 类型：`updates` 适合节点状态变化，`messages` 适合 token 和工具消息，`custom` 适合应用自定义进度。`subgraphs=True` 才会把子图事件带到同一条流中：

```python
for chunk in agent.stream(
    input,
    stream_mode="updates",
    subgraphs=True,
    version="v2",
):
    if chunk["type"] != "updates":
        continue

    source = "subagent" if chunk["ns"] else "main"
    print(f"[{source}]", chunk["data"])
```

自定义进度信号属于应用协议，不要让 UI 依赖某个内部 graph node 的名字。若工具需要发出业务进度，可以在工具内部调用 `get_stream_writer()`：

```python
from langchain.tools import tool
from langgraph.config import get_stream_writer


@tool
def analyze_data(topic: str) -> str:
    """Analyze a topic and report structured progress."""
    writer = get_stream_writer()
    writer({"status": "starting", "topic": topic, "progress": 0})
    # 执行实际分析
    writer({"status": "complete", "topic": topic, "progress": 100})
    return f"Analysis complete: {topic}"
```

随后在 v2 的 `custom` 分支中消费 `chunk["data"]`。如果应用已经采用 v3，应把这类自定义信号通过一个集中 adapter 映射成内部 `progress` 事件，而不是在组件中混合两种协议。

## 8. 从事件到页面：一个简单的映射

一个足够清晰的前端事件模型可以是：

```text
coordinator message  -> 主对话消息流
subagent started     -> 新建 researcher 卡片，状态 running
subagent message     -> 写入对应 path 的子 Agent 卡片
tool call            -> 卡片内的工具行，显示参数增量和结果
subagent completed   -> researcher 卡片折叠，保留摘要和耗时
final output         -> 主对话的最终答案区域
error/interrupted    -> 对应层级显示可恢复的错误状态
```

实际实现时至少保留以下字段：

```python
{
    "run_id": "...",
    "source": "coordinator" | "subagent",
    "path": ("tools:...",),
    "kind": "message" | "tool_call" | "progress" | "output",
    "status": "running" | "completed" | "failed" | "interrupted",
    "delta": "...",
}
```

`path` 是跨层级路由的稳定依据，`name` 只是用户可读标签。页面应允许用户展开子 Agent 和工具详情，但默认把主对话与最终输出放在最显眼的位置，避免把内部 graph 节点变成用户必须理解的概念。

## 9. 常见误区与生产边界

### 误区一：把 Streaming 当成并行执行

Streaming 只报告运行中的事件。一个串行 Agent 也可以有流式输出；多个子 Agent 是否并行，取决于编排方式和运行时。要观察并发，结合子 Agent 的开始时间、结束时间和运行路径，而不是只看页面上消息出现的先后。

### 误区二：依次阻塞消费多个 projection

先把 `stream.messages` 消费完，再打开 `stream.subagents`，会让实时 UI 失去交错顺序；同步使用 `interleave`，异步使用 `gather`。长任务还应设置超时，并在客户端断开时决定是否取消后端运行。

### 误区三：把 graph node 当成产品概念

`model_request`、`tools` 等节点对调试很有用，却不一定适合直接展示。用户需要的是“研究助手正在查资料”，而不是某个内部节点名称。v3 的 `subagents` 正是为了提供更稳定的产品语义。

### 误区四：把到达顺序当成业务顺序

网络、模型服务和子 Agent 调度都会影响事件到达时间。需要可审计的顺序时保存 raw event 的序号、时间戳和 namespace；不要用最终消息文本反推发生过什么。

### 误区五：忘记错误、取消和背压

页面不能只处理文本 delta。工具错误、子 Agent 失败、运行中断、客户端离线和慢消费者都必须有明确策略：记录、重试、取消、降级或提示用户。Streaming 层不替你决定这些策略。

### 误区六：把流式日志当成持久化记录

如果需要刷新页面后继续查看，应该把标准化后的事件写入 Trace、数据库或对象存储，并使用 `run_id` 做关联。内存中的 iterator 消费完就结束，不能当作重放机制。

## 10. 一次最小实验

在 AgentSeek 的 `deepagents/research` 模板中完成下面的改造：

1. 升级模板和本地 AgentSeek 后，先运行模板自带研究流程，确认 `researcher` 可以被调用。
2. 在后端把一次 `invoke()` 改为 `stream_events(..., version="v3")`。
3. 给主对话增加 coordinator 消息流，给侧栏增加 `researcher` 子 Agent 卡片。
4. 在卡片中显示工具调用的 `tool_name`、参数增量、完成状态和错误。
5. 用 `asyncio.gather` 或 `stream.interleave` 保留两个投影的实时更新。
6. 最后增加一个“协议调试”开关，用 v2 的 `type/ns/data` 查看同一运行的底层事件。

实验验收不看某一段固定输出，而看四个事实是否能被观察到：确实发生了委派、子 Agent 有独立状态、工具调用没有被吞掉、最终答案仍由 coordinator 汇总。模型输出会变化，这是 Streaming 应用必须面对的正常情况。

## 本章小结

- `invoke()` 适合拿最终状态，Streaming 适合观察运行过程。
- 新应用优先使用 `stream_events(..., version="v3")` 的 typed projections。
- `stream.subagents` 是面向产品的 Deep Agents 委派视图；`subgraphs` 和 namespace 是底层图协议。
- 访问 `.messages`、`.tool_calls` 等 projection 才会订阅对应流；只看生命周期时不必打开全部细节。
- coordinator 与 subagent 要并发消费；精确全局顺序则读取 raw events 并检查 namespace。
- v2 的 `stream_mode`、`subgraphs=True` 和 `custom` 适合协议调试与迁移，不要和 v3 返回值混写。
- Streaming 不自动解决持久化、重放、取消、超时和背压，生产应用需要补上这些边界。

## 官方参考

- [Deep Agents Event Streaming](https://docs.langchain.com/oss/python/deepagents/event-streaming)
- [Deep Agents Streaming](https://docs.langchain.com/oss/python/deepagents/streaming)
- [LangChain Event Streaming](https://docs.langchain.com/oss/python/langchain/event-streaming)
- [LangGraph Event Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
