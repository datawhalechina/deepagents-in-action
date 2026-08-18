# 第 14 章：Streaming — 实时观察主 Agent、子 Agent 与工具调用

> 研究助手已经跑了两分钟。后台日志显示它调用了搜索工具，也确实启动了 `researcher`；浏览器里的用户却只看到一个转圈图标。等到最终答案出现时，用户不知道它是在工作，还是已经卡住了。

模型仍然可能给出一份好答案。真正让用户不安的是，应用把两分钟的运行过程压扁成了一个最终值。本章沿着这个故障改造“黑盒研究助手”：先看见委派，再看见子 Agent 的消息和工具调用，随后修复事件顺序，最后处理旧代码里的底层协议。

示例以 Deep Agents v0.6 引入的 Typed Projection API 为主线。新应用优先使用 `agent.stream_events(..., version="v3")`；`agent.stream(..., version="v2")` 放在后半章，专门解释 LangGraph 的协议格式、namespace 和 custom updates。两者解决的问题不同，代码也不要混在同一个循环里。

## 1. 一次“看起来卡住”的研究请求

先看这个应用的原始调用。它没有错，甚至很适合脚本：

```python
result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
print(result["messages"][-1].content)
```

对应到页面，运行期间只有这样一条状态：

```text title="改造前的页面"
用户：研究近期的 Agent Streaming 模式
系统：正在生成……
```

问题出在产品体验。`invoke()` 只有在整个运行结束后才返回，所以页面无法回答这些最基本的问题：

- coordinator 有没有真的把任务交给 `researcher`？
- 子 Agent 是正在搜索，还是已经失败？
- 工具参数还在生成，还是工具已经返回错误？
- 最终答案出现前，究竟发生了哪些中间步骤？

我们先不急着设计漂亮的进度条。第一步只做一件事：把当前运行中“谁在工作”显示出来。

## 2. 先让案例稳定复现

如果完全依赖模型自由发挥，模型有时会直接回答问题，不调用 `task`，Streaming 页面也就没有稳定的子 Agent 可以展示。为了排查显示链路，我们先把研究请求固定委派给 `researcher`。

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

request = {
    "messages": [
        {"role": "user", "content": "Research recent Agent streaming patterns"}
    ]
}
```

运行到这里，我们已经有了一个可观察的树：顶层是 coordinator，下面是一次 `researcher` 委派，研究过程中还可能出现工具调用。模板中的搜索工具和模型必须支持 Tool Calling，否则后面只能看到 Agent 状态，看不到工具事件。

## 3. 第一个修复：先显示“研究助手已启动”

### 3.1 不要先从 graph node 猜产品状态

最底层的 LangGraph 会产生很多节点名称，例如 `model_request`、`tools`。它们对调试有用，却不适合作为产品界面。用户关心的是“研究助手”，不是某个内部节点。

Deep Agents 为委派提供了更直接的视图：`stream.subagents`。它的每一个 handle 对应一次 `task` 委派，并带有用户真正需要的名称、路径和生命周期状态。

```python
stream = agent.stream_events(request, version="v3")

for subagent in stream.subagents:
    print(f"[{subagent.name}] {subagent.status}")
    print("path:", subagent.path)

    try:
        print("output:", subagent.output)
    except Exception as exc:
        print(f"failed: {exc}")
```

现在页面至少可以在卡片上写出：`researcher · started`。如果运行成功，`output` 是子 Agent 的最终状态；如果它失败或被中断，读取最终输出时可能抛出异常，这个异常应成为卡片上的错误，而不是被吞掉。

### 3.2 Projection 是按需打开的

刚才我们只关心“启动、结束、失败”，所以没有订阅子 Agent 的全部消息。v3 的 projection 是惰性的：访问 `subagent.messages` 或 `subagent.tool_calls` 时，才打开对应的细流。

这对生产页面很实用。只展示状态和耗时时，不需要消费每一条消息和工具增量；需要详细过程的界面，再打开相应 projection。没有必要为每个内部事件都建立一份 UI 状态。

## 4. 第二个修复：让用户知道它在查什么

状态卡片解决了“是不是卡住”的问题，但用户很快会追问：“它到底在做什么？”现在把 coordinator 和 researcher 的消息都接出来。

```python
stream = agent.stream_events(request, version="v3")

for message in stream.messages:
    print("[coordinator]", message.text)

for subagent in stream.subagents:
    for message in subagent.messages:
        print(f"[{subagent.name}]", message.text)
```

这段代码能帮助我们确认上下文隔离是否真的发生：coordinator 负责下达任务和汇总，researcher 在自己的上下文中完成研究。主 Agent 不需要接收每一次搜索结果，只需要接收子 Agent 最后的摘要。

但这段代码还不能直接放进实时页面。它先把 coordinator 的 iterator 消费完，再去消费 `subagents`。如果 researcher 在后台已经输出了很多内容，页面看到的顺序就会被重新排列：主 Agent 的话全部出现在前面，子 Agent 的话全部出现在后面。

第一次接入后，页面可能会变成这样：

```text title="能够看到内容，但顺序失真"
[coordinator] 正在委派研究任务
[coordinator] 这是最终总结……
[researcher] 正在比较不同的 Streaming 接口
[researcher] 已找到相关资料……
```

researcher 明明先完成研究，却被排在最终总结之后。第 6 节会修复这个顺序问题；在那之前，还要把卡片里缺失的工具活动补上。

## 5. 第三个修复：工具调用也要能被看见

研究卡片里只有文字仍然不够。用户看到“正在研究”，却不知道它是在等网络、调用搜索，还是工具已经报错。工具调用也按 Agent 层级提供 projection：

```python
stream = agent.stream_events(request, version="v3")

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

这里有三个容易混淆的时刻：参数或工具输出还在增量到达；调用已经完成；调用完成但带有错误。页面可以把它们映射成“运行中”“已完成”和“失败”，不要把错误调用渲染成一行空白结果。

到这一步，用户看到的不再是一张只会闪烁的卡片：

```text title="补上工具状态后"
researcher · running
  search · running   query="Deep Agents event streaming"
  search · completed 5 results
  正在整理 v3 projection 与 v2 protocol 的差异……
```

如果研究 Agent 还会委派下一层 Agent，投影可以继续向下递归：

```python
stream = agent.stream_events(request, version="v3")

for subagent in stream.subagents:
    print(f"subagent {subagent.name}: {subagent.status}")

    for tool_call in subagent.tool_calls:
        print(f"{tool_call.tool_name}({tool_call.input})")
        for delta in tool_call.output_deltas:
            print(delta, end="", flush=True)

    for nested in subagent.subagents:
        print(f"nested subagent {nested.name}: {nested.status}")
```

递归时要用 `path` 作为 UI 的唯一键。同名 `researcher` 可能来自不同委派分支，单独用 `name` 会把两张卡片的状态写到一起。

## 6. 顺序乱了：两种方式修复实时消费

### 6.1 异步服务：并发消费

回到刚才的页面 bug。coordinator 和 researcher 的事件会交错到达，实时 UI 不能把两个 iterator 排队处理。异步服务应同时消费它们：

```python
import asyncio


async def stream_live():
    stream = await agent.astream_events(request, version="v3")

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

`asyncio.gather` 解决的是阻塞问题：一个投影等待网络时，另一个仍然可以把事件送到页面。它不承诺所有投影之间都有一个可以直接比较的全局顺序；如果要审计“哪个 token 先到”，还需要更底层的事件。

### 6.2 同步程序：使用 `interleave`

如果当前是同步命令行程序，不必为了展示进度重写成异步。v3 提供了 `interleave`：

```python
stream = agent.stream_events(request, version="v3")

for name, item in stream.interleave("messages", "subagents"):
    if name == "messages":
        print("[coordinator]", item.text)
    else:
        for message in item.messages:
            print(f"[{item.name}]", message.text)
```

它适合快速做一个同步展示。如果要递归合并工具调用和嵌套子 Agent，仍然建议在应用层写一个事件 adapter，而不是让每个组件都理解 iterator 的细节。

## 7. 页面开始工作后，才需要精确顺序

大多数产品只需要“主对话”“researcher 卡片”和“工具行”三个区域。它们有了自己的来源和路径，页面就能正确更新。只有在调试丢事件、重放运行或做审计时，才值得保留所有层级的精确到达顺序。

这时可以读取 v3 的 raw protocol events：

```python
stream = agent.stream_events(request, version="v3")

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

raw event 的字段属于协议层。建议集中写一个 adapter，负责校验版本、读取 `namespace`、分配序号，再转换成应用自己的事件格式；页面只消费转换后的对象。这样协议升级时只改 adapter 和测试，不必逐个修改组件。

## 8. 旧代码为什么还在处理 `type/ns/data`

团队接手一个已有 LangGraph 服务时，常会看到这样的循环：

```python
for chunk in agent.stream(
    request,
    stream_mode=["updates", "messages", "custom"],
    subgraphs=True,
    version="v2",
):
    print(chunk["type"])
    print(chunk["ns"])
    print(chunk["data"])
```

这段循环直接消费底层图执行协议，不使用 v3 的 typed projections。v2 的每个 `StreamPart` 都有 `type`、`ns`、`data`：

```text
()                              -> main agent
("tools:abc123",)              -> task 工具启动的子 Agent
("tools:abc123", "model:xyz")  -> 子 Agent 内部模型节点
```

`stream_mode` 决定 `data` 的形状：`updates` 适合看节点状态变化，`messages` 适合 token 和工具消息，`custom` 适合应用自定义进度。`subgraphs=True` 才会让子图事件出现在同一条流里：

```python
for chunk in agent.stream(
    request,
    stream_mode="updates",
    subgraphs=True,
    version="v2",
):
    if chunk["type"] != "updates":
        continue

    source = "subagent" if chunk["ns"] else "main"
    print(f"[{source}]", chunk["data"])
```

这套格式适合两类场景：已有应用迁移时不想一次重写事件路由；调试时必须知道某条更新来自哪一个图节点。新页面仍建议用 v3 的 `subagents`，因为它直接表达“委派给哪个产品角色”，不用让 UI 猜 namespace。

## 9. 需要自定义进度时，先定义自己的事件

研究工具可能还想报告“已找到 3 个来源”“正在合并摘要”。这类信息不是内部 node 状态，应该由工具显式发出：

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

在 v2 中，这些信号从 `custom` 分支的 `chunk["data"]` 读取；如果应用已经采用 v3，就在 adapter 里把它们转为统一的 `progress` 事件。不要让前端组件一半读取 v3 对象、一半判断 v2 的字符串字段。

## 10. 从“能看到”到“能交付”

到这里，页面终于能把一次研究请求说清楚：

```text
coordinator message  -> 主对话
subagent started     -> researcher 卡片进入 running
subagent message     -> 写入 researcher 卡片
tool call            -> 卡片里的工具行，显示参数和结果
subagent completed   -> 卡片收起，保留摘要和状态
final output         -> 主对话里的最终答案
error/interrupted    -> 对应层级的错误或中断提示
```

建议把所有投影先转换成一个小而稳定的内部事件：

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

页面不需要知道 `model_request` 这种内部节点名，但必须保留 `path`。它是跨层级路由的依据；`name` 只是用户看到的标签。

### 四个生产问题

页面上线前还要补四个运行边界：

1. Streaming 不等于并行。是否并行取决于编排方式，不能从“事件交错”反推执行模型。
2. 客户端断开后怎么办？长任务需要明确选择超时、取消，还是转入后台继续执行。
3. 慢客户端怎么办？服务端要限制队列大小，或丢弃能够重建的增量，不能无限积压。
4. 刷新页面后还能不能看见刚才的过程？如果需要重放，就把标准化事件写入 Trace、数据库或对象存储；内存 iterator 不是持久化日志。

工具错误、子 Agent 失败和中断状态都要原样保留。只有把失败也做成事件，用户才知道“研究没有完成”和“页面没有刷新”是两回事。

## 11. 一次最小实验：把研究模板从黑盒改成可观察

在 AgentSeek 的 `deepagents/research` 模板中完成下面这条改造链：

1. 升级本地 AgentSeek，并用 `agentseek create deepagents/research --checkout main` 拉取最新模板。
2. 先运行模板自带的研究流程，确认 `researcher` 能被调用。先不要改页面，记录一次 `invoke()` 的最终结果。
3. 将后端调用改成 `stream_events(..., version="v3")`，先只显示 `researcher` 的 `started/completed/failed`。
4. 给主对话和 `researcher` 卡片分别接入 `.messages`，确认两边的上下文边界。
5. 在子 Agent 卡片中加入 `.tool_calls`，展示工具名、参数增量、完成状态和错误。
6. 用 `asyncio.gather` 或 `stream.interleave` 修复主对话和研究卡片的交错顺序。
7. 最后增加一个仅供开发者使用的协议调试开关，用 v2 的 `type/ns/data` 查看同一运行的底层事件。

验收不看某一段固定文本，因为模型输出会变化。只检查四件事：请求确实委派给了 `researcher`，子 Agent 有独立状态，工具调用没有被吞掉，最终答案仍由 coordinator 汇总。

## 本章小结

这次改造从一个具体故障开始：最终答案能返回，但用户看不见中间过程。解决它的顺序也很重要：

- 用 `stream.subagents` 先显示产品层的委派状态；
- 按需打开 `.messages`、`.tool_calls`、`.subagents` 和 `.output`；
- 用异步并发消费或 `interleave` 保留实时更新；
- 只有需要审计时，才读取 raw events 和 namespace；
- 新应用默认使用 v3，v2 留给底层调试、custom updates 和迁移；
- Streaming 不负责持久化、取消、超时和背压，生产边界要由应用补齐。

## 官方参考

- [Deep Agents Event Streaming](https://docs.langchain.com/oss/python/deepagents/event-streaming)
- [Deep Agents Streaming](https://docs.langchain.com/oss/python/deepagents/streaming)
- [LangChain Event Streaming](https://docs.langchain.com/oss/python/langchain/event-streaming)
- [LangGraph Event Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
