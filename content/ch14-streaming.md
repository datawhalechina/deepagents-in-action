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

![同一个研究请求在 invoke 与 Streaming 中的体验对比：invoke 只显示运行中和最终答案，Streaming 则逐步展开 coordinator、researcher、搜索工具和消息状态](../public/imgs/44-comparison-invoke-vs-streaming.png)

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

### 3.2 拆解 `subagent` handle

这个 handle 既有身份字段，也有可以继续消费的 projection：

| 字段或 projection | 含义 | 读取时机 | 页面怎么用 |
| --- | --- | --- | --- |
| `name` | coordinator 调用 `task` 时选择的 `subagent_type` | handle 出现时 | 显示 `researcher` 等角色名称；不作为唯一键 |
| `path` | 这次委派在 Agent 树中的 namespace 路径 | handle 出现时 | 作为卡片路由键，区分多个同名子 Agent |
| `status` | `started`、`completed`、`failed`、`interrupted` 等生命周期状态 | 收到 handle 及其后续状态时 | 更新状态徽标；终态仍要结合 `output` 或异常判断 |
| `messages` | 该子 Agent 发出的消息 projection | 需要文本过程时 | 写入当前 `path` 对应的消息列表 |
| `tool_calls` | 该子 Agent 发起的工具调用 projection | 需要工具细节时 | 在当前卡片下建立工具行 |
| `values` | 该子 Agent 的状态值 projection | 需要状态快照时 | 调试或状态面板使用，不等同于文本消息 |
| `subagents` | 该子 Agent 继续发起的嵌套委派 | 存在多级委派时 | 递归建立子卡片 |
| `output` | 该委派的最终状态或完成信号 | 需要等待终态时 | 完成后保存最终结果；失败时捕获异常 |

`name` 的来源值得单独记住：它不是内部 graph node 名，也不是一次运行的唯一 ID。它来自 coordinator 为 `task` 选择的 `subagent_type`。同一个 `researcher` 可以被调用多次，所以 UI 应按 `path` 存储状态，用 `name` 显示标签。

`status` 是生命周期，不是质量结论：

| 状态 | 表示什么 | 应用动作 |
| --- | --- | --- |
| `started` | 委派已经被发现并开始运行 | 创建或更新卡片为 running |
| `completed` | 子 Agent 已结束且可读取最终输出 | 读取 `output`，保存结果并结束计时 |
| `failed` | 子 Agent 以错误结束 | 保存异常，卡片进入 failed |
| `interrupted` | 运行在中断点暂停 | 保留现有状态，等待恢复或取消 |

`completed` 也不代表研究内容一定正确，只代表这次委派正常结束。业务验收仍要由测试、Rubric 或人工审核完成。

### 3.3 Projection 是按需打开的

刚才我们只关心“启动、结束、失败”，所以没有订阅子 Agent 的全部消息。v3 的 projection 是惰性的：访问 `subagent.messages` 或 `subagent.tool_calls` 时，才打开对应的细流。

这对生产页面很实用。只展示状态和耗时时，不需要消费每一条消息和工具增量；需要详细过程的界面，再打开相应 projection。没有必要为每个内部事件都建立一份 UI 状态。

父级 `stream` 也提供相同方向的 projection：

| 父级 projection | 范围 |
| --- | --- |
| `stream.messages` | coordinator 的消息 |
| `stream.tool_calls` | coordinator 发起的工具调用 |
| `stream.values` | 顶层运行的状态值 |
| `stream.subagents` | coordinator 发起的委派 |
| `stream.output` | 顶层运行的最终输出 |

![v3 Typed Projection 的层级与作用域：顶层 stream 提供 messages、tool_calls、values、subagents 和 output；subagent handle 保存 name、path、status，并按需打开自己的同类 projections](../public/imgs/45-framework-typed-projections.png)

这里最容易犯的错是范围混淆。`stream.messages` 不会替你合并所有子 Agent 的消息；`subagent.messages` 也不会包含 coordinator 的最终总结。它们是两条独立 projection。

`values` 需要再多解释一句：它不是另一种消息流，也没有 Deep Agents 统一规定的业务字段。它发出的是当前 Agent state 的快照，字段取决于应用和中间件。例如启用了 Todo 或自定义状态时，快照可能包含消息列表、todos 或其他运行状态。把它用于调试和状态面板比较合适；主对话文本仍从 `messages` 读取，工具结果仍从 `tool_calls` 读取。

```python
stream = agent.stream_events(request, version="v3")

for value in stream.values:
    print("state snapshot:", value)
```

不要把每个 `value` 当成一个可直接追加的增量。它更像“这一时刻的状态快照”，前端若要保存，应按 `run_id` 和时间序号覆盖或采样，而不是无限拼接。

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

### 4.1 `message` 应该读什么

Typed Projection 已经把底层 content-block 事件整理成 message handle。本章示例只需要一个字段：

| 字段 | 同步代码 | 异步代码 | 含义 |
| --- | --- | --- | --- |
| `text` | `message.text` | `await message.text` | 当前消息可显示的文本内容 |

同步和异步写法的差别不是语法装饰。异步 handle 的文本可能仍在到达，读取时需要 `await`。如果要保留逐个 `text-delta` 的精确顺序，不应从 `message.text` 反推，而要使用第 7 节的 raw events。

消息对象解决的是“显示什么”；消息属于谁由你消费的 projection 决定。建议在进入内部事件模型时补上来源字段：

```python
{
    "source": "coordinator",
    "path": (),
    "kind": "message",
    "text": message.text,
}
```

子 Agent 消息则把 `source` 改为 `subagent`，并保存 `subagent.path`。不要只把文本字符串推给前端，否则两个来源交错时无法还原卡片归属。

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

### 5.1 拆解 `tool_call`

一个 tool-call handle 同时承载调用身份、进行中的增量和终态：

| 字段或 projection | 含义 | 使用规则 |
| --- | --- | --- |
| `tool_name` | 模型选择的工具名 | 用于显示和分类；不要把未知工具名直接当成可信操作 |
| `input` | 工具输入 | 参数可能包含敏感数据，写日志和推送前先做脱敏 |
| `output_deltas` | 工具执行过程中产生的增量输出 | 按到达顺序追加，不要把单个 delta 当成完整结果 |
| `completed` | 调用是否进入完成状态 | `True` 只表示调用结束，仍要检查 `error` |
| `output` | 成功调用的最终输出 | 在 `completed` 且 `error is None` 后读取 |
| `error` | 调用错误 | 非空时进入失败分支，不要继续把 `output` 当成功结果 |

因此，工具状态不能只写成 `if call.completed: success`。可靠判断至少分成下面三支：

```python
if not call.completed:
    status = "running"
elif call.error is not None:
    status = "failed"
else:
    status = "completed"
```

`output_deltas` 适合终端或实时日志区，`output` 适合完成后的结果摘要。两者同时保存时要避免重复：不要先把所有 delta 拼成全文，又把相同的最终 `output` 再追加一次。

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

`interleave` 每次返回 `(name, item)`。`name` 是你传入的 projection 名，决定 `item` 的类型：

| `name` | `item` | 下一步 |
| --- | --- | --- |
| `messages` | coordinator 的 message handle | 读取 `item.text` |
| `subagents` | 一次委派的 subagent handle | 读取 `item.name/path/status`，再按需消费子 projection |

它只合并你显式传入的 projection。上例没有传 `tool_calls`，所以 coordinator 的工具调用不会凭空出现在循环中；子 Agent 工具也仍需从 `item.tool_calls` 读取。

它适合快速做一个同步展示。如果要递归合并工具调用和嵌套子 Agent，仍然建议在应用层写一个事件 adapter，而不是让每个组件都理解 iterator 的细节。

![coordinator 与 researcher 的事件会交错到达：串行消费把两个来源分组后造成顺序失真，并发消费使用 asyncio.gather 或 interleave 将事件按到达过程送入页面事件流](../public/imgs/46-sequence-concurrent-streaming.png)

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

### 7.1 raw event 的字段

上面的过滤器只取了文本增量，实际 adapter 至少应该理解这些字段：

| 路径 | 含义 | 处理建议 |
| --- | --- | --- |
| `event["method"]` | 协议事件的方法，例如 `messages` | 先按方法分派，再读取对应 payload |
| `event["params"]` | 事件参数包 | 当作协议对象校验，不要假定所有方法字段相同 |
| `params["namespace"]` | 产生事件的图层级路径 | 空值表示 coordinator；非空值用于子图路由 |
| `params["data"]` | 当前方法的数据数组 | 先检查长度和类型，再取 `data[0]` |
| `data[0]["event"]` | content-block 事件类型 | `content-block-delta` 才表示增量块 |
| `data[0]["delta"]` | 增量块内容 | 再检查 `delta["type"]`，例如 `text-delta` |
| `delta["text"]` | 本次文本增量 | 追加到对应 `namespace` 的缓冲区 |

`namespace` 不是子 Agent 的显示名。v3 的 `subagent.name` 来自 `subagent_type`，raw event 的 namespace 是执行路径，可能包含 `tools:<id>` 和内部节点。前端 adapter 可以同时保存两者：`display_name` 用于界面，`path` 用于路由和审计。

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

| 字段 | 形状 | 解读 |
| --- | --- | --- |
| `type` | 字符串 | 当前 chunk 属于 `updates`、`messages` 或 `custom` 哪一种模式 |
| `ns` | tuple/list-like namespace | 空值通常是主 Agent；非空值表示子图或内部节点路径 |
| `data` | 随 `type` 变化 | `updates` 常是节点状态字典，`messages` 常是消息与 metadata，`custom` 是工具写入的自定义 payload |

![v3 与 v2 Streaming 的观察层级对比：v3 Typed Projection 面向产品角色提供 message、subagent 和 tool_call 字段；v2 StreamPart 面向图执行提供 type、ns、data；两者通过应用事件 Adapter 转换为统一页面事件](../public/imgs/47-comparison-v3-v2-streaming.png)

```text
()                              -> main agent
("tools:abc123",)              -> task 工具启动的子 Agent
("tools:abc123", "model:xyz")  -> 子 Agent 内部模型节点
```

`stream_mode` 决定 `data` 的形状：`updates` 适合看节点状态变化，`messages` 适合 token 和工具消息，`custom` 适合应用自定义进度。`subgraphs=True` 才会让子图事件出现在同一条流里：

| `type` | `chunk["data"]` 常见形状 | 需要继续解读的字段 |
| --- | --- | --- |
| `updates` | `{node_name: state_update}` | `node_name` 是图节点名；`state_update` 的 schema 由节点决定 |
| `messages` | `(token, metadata)` | `token.content` 是文本；工具调用还要看 `token.tool_call_chunks`，来源要结合 `chunk["ns"]` |
| `custom` | 工具通过 writer 写入的任意对象 | 只按应用自定义 schema 解析，框架不会替你验证 |

例如 v2 的 `messages` 分支，不能只打印整个 tuple：

```python
from langchain.messages import AIMessageChunk, ToolMessage


for chunk in agent.stream(
    request,
    stream_mode="messages",
    subgraphs=True,
    version="v2",
):
    if chunk["type"] != "messages":
        continue

    token, metadata = chunk["data"]
    source = "subagent" if chunk["ns"] else "main"

    if isinstance(token, AIMessageChunk) and token.tool_call_chunks:
        for tool_chunk in token.tool_call_chunks:
            print(source, "tool:", tool_chunk.get("name"), tool_chunk.get("args"))
    elif isinstance(token, ToolMessage):
        print(source, "tool result:", token.name, token.content)
    elif token.content:
        print(source, token.content, end="", flush=True)
```

这里的 `metadata` 也不要丢掉。它通常携带模型调用、节点或运行标签，调试时可以帮助定位来源；但产品 UI 仍应优先使用 namespace 和 adapter 生成的稳定 `path`，不要把某个 metadata 私有键当成长期 API。

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

不要把 `data` 当成固定 schema。先判断 `chunk["type"]`，再按对应模式解析。尤其是 `messages` 的 payload 不能直接当成 v3 的 `message.text`；v3 已经替你做了投影，v2 仍要求应用处理模式和来源。

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

本例的 custom payload 是应用自己定义的，不是框架固定字段：

| 字段 | 本例含义 | 约束建议 |
| --- | --- | --- |
| `status` | 当前业务阶段 | 使用有限枚举，例如 `starting/analyzing/complete` |
| `topic` | 本次分析对象 | 只在必要事件中发送，避免每个增量重复大字段 |
| `progress` | 进度百分比 | 约定 `0-100`，且只表示业务估算，不冒充真实完成比例 |

既然 schema 由应用掌握，就应该为它加版本和验证。生产事件可增加 `schema_version`，消费者遇到未知版本时记录并降级，而不是猜测字段含义。

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

这些内部字段也要有明确来源：

| 内部字段 | 来自哪里 | 用途 |
| --- | --- | --- |
| `run_id` | 应用或运行时为本次请求分配 | 关联持久化事件、Trace 和重放 |
| `source` | 当前消费的是父级还是 subagent projection | 决定写入主对话还是子卡片 |
| `path` | `subagent.path` 或 raw `namespace` | 唯一路由到执行分支 |
| `kind` | adapter 根据 projection 或 method 归一化 | 让前端按消息、工具、进度、输出分派 |
| `status` | subagent 或 tool-call 生命周期映射 | 控制 running/completed/failed/interrupted 状态 |
| `delta` | message、tool output 或 custom payload | 承载增量内容；其 schema 随 `kind` 校验 |

`run_id` 不在本章展示的 subagent 字段表中自动出现，所以示例把它标为“应用或运行时分配”，不能把省略号替换成 `subagent.name`。`path` 才负责区分执行分支，两者职责不同。

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
