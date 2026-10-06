> 本次执行模式：**offline**。源码指纹：`073615e22e15`。

# 第 14 章实验：主 Agent 委派以后，怎样看见谁在做什么？

对应正文：[Streaming](../../content/ch14-streaming.md)第 3～7、9 节。

一个助手要整理 `streaming` 主题的本地教学笔记。主 Agent 把任务交给 `researcher`；子 Agent 调用 `inspect_notes` 查阅笔记，再返回摘要；主 Agent 最后汇总。如果只用 `invoke()`，中间过程不会逐项返回给调用方。

这里使用 `stream_events(version="v3")` 观察同一个流程。它返回可逐步消费的运行对象，不是直接返回最终状态。

```text
主 Agent 请求 task
    ↓
researcher 启动 → 请求 inspect_notes
    ↓
工具发出 starting/complete 进度，返回笔记内容
    ↓
researcher 摘要 → 主 Agent 汇总
```

**学习目标**：

- 用 typed projections（按消息、工具、子 Agent 分开的观察入口）分清事件归属。
- 检查工具请求、实际执行、返回值和子 Agent 终态，理解“结束”不等于“内容正确”。
- 观察自定义进度、raw 事件的 `seq` / `namespace`，验证晚订阅会漏掉过程。

默认预期：主 Agent 有一条 `task` 调用，子 Agent 有一条 `inspect_notes` 调用；工具读到 3 条笔记，进度由 `starting` 到 `complete`，子 Agent 最终为 `completed`。断言失败说明某项实验承诺未满足，不能只凭最终回复“完成”判断。

## 1. 环境与运行模式

需要基础 Python。每份 Notebook 都建立自己的变量；**内核**是执行代码、保存变量的 Python 进程。请从第一格顺序运行，安装与内核选择见 [README](../README.md)。

- Python 3.12；锁定 deepagents 0.7.22、langchain 1.4.3、langchain-core 1.6.6、langgraph 1.2.13、langchain-openai 1.6.7，以 [uv.lock](../uv.lock)为准。下一格打印实际环境。
- 默认 `offline` 使用公共 `ScriptedChatModel` 安排模型响应，不需要 Key，也不请求模型 API；图、同步委派、工具和流式观察真实执行。它不证明真实模型会正确委派或总结。
- 这个脚本模型不实现 token 分块生成，输出是完整 `AIMessage`。因此可以验证中间步骤与消息流，不能据此验证逐 token 展示或网络首字延迟。
- 显式 `live` 通过公共 `create_model` 使用 README 的模型配置，主、子 Agent 分别创建模型实例。模型需支持工具调用，可能产生费用；配置错误会报错，不回退。真实模型的文本、事件数与增量形式可以变化。
- 公共模型入口会将后续工具分块中的空工具名转换为 `None`，避免当前 langchain-core v3 兼容层覆盖首块的工具名。说明与移除条件见 [README](../README.md)；此处理不改变工具参数或实验断言。
- v3 仍是实验性接口，升级依赖后应重跑。下一格只隐藏已在此说明的重复实验性提示，其他错误正常报告。
- 不需要搜索 Key、Agent Server、数据库或 Docker。实验的笔记是内存里的固定教学数据，不代表实时搜索结果，也不读取用户文件。

从仓库根目录的终端执行：

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch14-streaming
```

显式接入真实模型时加 `--mode live`；交互式内核则在创建模型前设置 `os.environ["COURSE_MODE"] = "live"`。不要把密钥写入代码格。


```python
import json
import os
import warnings
from collections import Counter

from deepagents import create_deep_agent
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain.tools import tool
from langgraph.config import get_stream_writer
from langgraph.stream import CustomTransformer

from course_notebooks.model_config import create_model, selected_mode
from course_notebooks.nbtools import show_runtime, show_text
from course_notebooks.testing import ScriptedChatModel

show_runtime()
warnings.filterwarnings(
    "ignore", message="The v3 streaming protocol on Pregel is experimental.*"
)
```

    运行模式： offline （脚本模型）
    Python： 3.12.11 平台： Darwin arm64
    deepagents==0.7.22
    langchain==1.4.3
    langchain-core==1.6.6
    langgraph==1.2.13
    langchain-openai==1.6.7


## 2. 准备笔记与一项真实工具

`NOTES` 是本实验的教学输入。`@tool` 把 Python 函数包装成模型可请求的工具，名称、参数类型和文档字符串告诉模型怎样调用。

`get_stream_writer()` 获取当前图运行的写入入口。工具用它发出两个应用自定义对象，表示开始查阅和查阅完成。这里的 `phase`、`topic`、`count` 都是本例约定，不是框架固定字段，也不是 `subagent.status`。

`executions` 记录实际函数执行的输入和结果。它只服务于这次顺序实验，用来核对流里看到的调用有没有真的运行。


```python
TOPIC = "streaming"
NOTES = [
    "typed projections 分开观察主 Agent 和子 Agent。",
    "raw seq 用于同次运行的事件顺序，namespace 表示事件路径。",
    "custom 进度由工具显式发送，不是模型生成的文字。",
]


def make_notes_tool(executions):
    @tool
    def inspect_notes(topic: str) -> str:
        """读取 streaming 主题的固定教学笔记，返回 topic、count 和 notes。"""
        writer = get_stream_writer()
        writer({"phase": "starting", "topic": topic, "count": 0})
        if topic != TOPIC:
            raise ValueError("本工具只提供 streaming 主题的教学笔记。")
        result = {"topic": topic, "count": len(NOTES), "notes": list(NOTES)}
        executions.append({"topic": topic, "result": result})
        writer({"phase": "complete", "topic": topic, "count": len(NOTES)})
        return json.dumps(result, ensure_ascii=False)
    return inspect_notes

print("教学输入：")
for index, note in enumerate(NOTES, start=1):
    show_text(f"笔记 {index}：", note)
```

    教学输入：
    
    笔记 1：
    typed projections 分开观察主 Agent 和子 Agent。
    
    笔记 2：
    raw seq 用于同次运行的事件顺序，namespace 表示事件路径。
    
    笔记 3：
    custom 进度由工具显式发送，不是模型生成的文字。


工具需要在图运行中取得 writer，不能像普通函数那样在这里直接调用来读取笔记。下一节把工具交给子 Agent，再由框架调用。

进度为 `complete` 只说明工具走到了该业务步骤；最终仍要核对工具结果和调用状态，不能用一条进度通知替代验收。

## 3. 创建主 Agent 与 researcher

`AIMessage` 表示模型回复，其中的 `tool_calls` 是工具请求，不是工具执行结果。`ToolMessage` 才是工具执行后返回的消息，`tool_call_id` 将结果与请求关联。

offline 的主模型响应列表是“请求 task → 汇总”；子模型列表是“请求 inspect_notes → 摘要”。列表不会理解任务，只安排默认流程。每个独立实验都创建新模型，避免循环响应游标混用。

`create_deep_agent()` 返回可执行的图（Graph），图中的节点负责调用模型、执行工具等步骤，可以循环。`researcher` 是同步子 Agent：主 Agent 的 `task` 要等它返回，但调用方能在等待期间消费流事件。它不是第 6 章的后台异步子任务，不需要 Agent Server。


```python
DELEGATION = "调用 inspect_notes(topic='streaming')，然后根据返回的笔记写简短摘要。"
REQUEST = {"messages": [HumanMessage(content="请委派 researcher 整理 streaming 教学笔记。")]}


def make_agent():
    executions = []
    parent_model = create_model(ScriptedChatModel(responses=[
        AIMessage(content="正在委派研究。", tool_calls=[{
            "id": "delegate-1", "name": "task",
            "args": {"subagent_type": "researcher", "description": DELEGATION},
        }]),
        AIMessage(content="已汇总 3 条教学笔记。"),
    ]))
    child_model = create_model(ScriptedChatModel(responses=[
        AIMessage(content="正在读取笔记。", tool_calls=[{
            "id": "inspect-1", "name": "inspect_notes", "args": {"topic": TOPIC},
        }]),
        AIMessage(content="本地共有 3 条笔记，分别说明投影、raw 顺序与自定义进度。"),
    ]))
    agent = create_deep_agent(
        model=parent_model,
        system_prompt=(
            "每次都用 task 委派 researcher，要求它调用 inspect_notes(topic='streaming')。"
            "等待子 Agent 返回后简短汇总，不调用其他工具。"
        ),
        subagents=[{
            "name": "researcher", "description": "查阅固定教学笔记并返回摘要。",
            "system_prompt": "只调用一次 inspect_notes(topic='streaming')，再总结结果。",
            "model": child_model, "tools": [make_notes_tool(executions)],
        }],
    )
    return agent, executions
```

## 4. 用 v3 的投影观察一次运行

`handle` 是观察某条消息、调用或委派的对象：先发现它，再读取它的文本或终态。主要入口如下：

| 入口 | 本例作用域 | 要看什么 |
|---|---|---|
| `run.messages` | 主 Agent | 委派说明与最后汇总 |
| `run.tool_calls` | 主 Agent | `task` 的参数和终态 |
| `run.subagents` | 主 Agent 发起的委派 | `researcher` 的名字、path、状态 |
| `child.messages` / `child.tool_calls` | 该子 Agent | 查阅说明、`inspect_notes` 与摘要 |
| `child.custom` | 该子 Agent | 工具写出的 starting/complete 进度 |
| `run.output` / `child.output` | 相应的图 | 等待执行结束并读取最终状态 |

`interleave("messages", "tool_calls", "subagents")` 将这些入口的 **handle 到达** 合并。每次返回 `(kind, item)`：`kind` 是传入的投影名，决定 `item` 怎样读取。子 Agent 出现时，立即订阅它自己的投影。

`str(message.text)` 会等待当前消息结束，得到完整文本；它不是逐 token 回调。`call.completed` 在刚收到 handle 时可能为假，不能这时就把它算成工具完成。因此先保存调用 handle，等 `run.output` 返回后再检查终态。

**顺序边界**：此同步例子会消费子循环，也会等待消息文本，期间外层循环不能立即展示其他来源。`interleave` 合并 handle，不自动把所有嵌套文本增量变成一条全局时间线。异步页面应并发消费各入口；需要精确协议顺序时看下一节 raw 的 `seq`。

`with` 管理这次流的生命周期：正常结束或代码抛错退出都会调用流的 `abort()` 释放迭代器，不依赖最后一格清理。


```python
agent, executions = make_agent()
children, parent_calls, child_calls = [], [], []
parent_texts, child_texts, progress = [], [], []

with agent.stream_events(
    REQUEST, config={"recursion_limit": 16}, version="v3",
    transformers=[CustomTransformer],
) as run:
    for kind, item in run.interleave("messages", "tool_calls", "subagents"):
        if kind == "messages":
            text = str(item.text)
            parent_texts.append(text)
            show_text("主 Agent 消息：", text)
        elif kind == "tool_calls":
            parent_calls.append(item)
            print("\n主 Agent 工具请求：", item.tool_name)
            show_text("参数：", json.dumps(item.input, ensure_ascii=False, indent=2))
        else:
            children.append(item)
            print("\n子 Agent：", item.name, "状态：", item.status)
            show_text("本次委派 path：", item.path)
            for child_kind, detail in item.interleave("messages", "tool_calls", "custom"):
                if child_kind == "messages":
                    text = str(detail.text)
                    child_texts.append(text)
                    show_text("researcher 消息：", text)
                elif child_kind == "tool_calls":
                    child_calls.append(detail)
                    print("\nresearcher 工具请求：", detail.tool_name)
                    show_text("参数：", json.dumps(detail.input, ensure_ascii=False, indent=2))
                else:
                    progress.append(detail)
                    print("进度：", detail)
    final_state = run.output
    child_states = [child.output for child in children]
```

    
    主 Agent 消息：
    正在委派研究。
    
    主 Agent 工具请求： task
    
    参数：
    {
      "subagent_type": "researcher",
      "description": "调用 inspect_notes(topic='streaming')，然后根据返回的笔记写简短摘要。"
    }
    
    子 Agent： researcher 状态： started
    
    本次委派 path：
    ('tools:5c58fb76-b4bc-f452-ea4e-4305842f4c5e',)
    
    researcher 消息：
    正在读取笔记。
    
    researcher 工具请求： inspect_notes
    
    参数：
    {
      "topic": "streaming"
    }
    进度： {'phase': 'starting', 'topic': 'streaming', 'count': 0}
    进度： {'phase': 'complete', 'topic': 'streaming', 'count': 3}
    
    researcher 消息：
    本地共有 3 条笔记，分别说明投影、raw 顺序与自定义进度。
    
    主 Agent 消息：
    已汇总 3 条教学笔记。


看默认输出时，区分“工具请求”“进度通知”和“模型消息”。主 Agent 选择 `researcher`，而子 Agent 选择 `inspect_notes`。进度由 Python 工具发送，不是模型口头说“正在做”。

`path` 是 tuple，标识当前运行内这次委派的执行路径，通常形如 `("tools:<动态 ID>",)`；它不是显示名。重跑时 ID 会变，不能与另一次运行的路径逐字比较，也不能把 `researcher` 当作多次委派的唯一键。

自定义进度需要注册 `CustomTransformer`，且工具在子图中执行，所以从 `child.custom` 读取。根 `run.custom` 的作用域是根图，不会自动汇集子图进度。

### 4.1 结束后检查实际执行与结果

`completed` 是生命周期信号。成功工具还应没有 `error`，并且结果与实际执行记录一致。`inspect_notes` 的终态输出是 `ToolMessage`，需要检查 `status`、工具名、请求 ID 和业务内容。

同步 `task` 的终态输出可能是更新状态的 `Command`，不要假定所有工具输出都是字符串；本例从主 Agent 最终消息中核对 task 的返回关联。


```python
assert len(children) == 1 and children[0].name == "researcher"
assert children[0].status == "completed" and children[0].path
assert len(parent_calls) == 1 and parent_calls[0].tool_name == "task"
assert parent_calls[0].input["subagent_type"] == "researcher"
assert len(child_calls) == 1 and child_calls[0].tool_name == "inspect_notes"
call = child_calls[0]
assert call.input == {"topic": TOPIC}
assert all(c.completed and c.error is None for c in parent_calls + child_calls)
reply = call.output
assert isinstance(reply, ToolMessage)
assert reply.name == "inspect_notes" and reply.status == "success"
assert reply.tool_call_id == call.tool_call_id
assert len(executions) == 1 and executions[0]["topic"] == TOPIC
expected = executions[0]["result"]
assert expected == {"topic": TOPIC, "count": len(NOTES), "notes": NOTES}
assert json.loads(reply.text) == expected
assert progress == [
    {"phase": "starting", "topic": TOPIC, "count": 0},
    {"phase": "complete", "topic": TOPIC, "count": len(NOTES)},
]
# 从最终消息列表筛出 task 结果，核对它属于本次请求。
parent_replies = [m for m in final_state["messages"] if isinstance(m, ToolMessage)]
assert len(parent_replies) == 1
assert parent_replies[0].tool_call_id == parent_calls[0].tool_call_id
assert parent_replies[0].status == "success"
child_replies = [m for m in child_states[0]["messages"] if isinstance(m, ToolMessage)]
assert len(child_replies) == 1 and child_replies[0].tool_call_id == call.tool_call_id
assert json.loads(child_replies[0].text) == expected
assert isinstance(final_state["messages"][-1], AIMessage)
assert not final_state["messages"][-1].tool_calls
assert final_state["messages"][-1].text.strip()
if selected_mode() == "offline":
    assert parent_texts == ["正在委派研究。", "已汇总 3 条教学笔记。"]
    assert len(child_texts) == 2
    assert "本地共有 3 条笔记" in child_texts[-1]

print("实际工具结果：")
show_text("inspect_notes：", json.dumps(expected, ensure_ascii=False, indent=2))
print("子 Agent 终态：", children[0].status)
show_text("主 Agent 最终汇总：", final_state["messages"][-1].text)
```

    实际工具结果：
    
    inspect_notes：
    {
      "topic": "streaming",
      "count": 3,
      "notes": [
        "typed projections 分开观察主 Agent 和子 Agent。",
        "raw seq 用于同次运行的事件顺序，namespace 表示事件路径。",
        "custom 进度由工具显式发送，不是模型生成的文字。"
      ]
    }
    子 Agent 终态： completed
    
    主 Agent 最终汇总：
    已汇总 3 条教学笔记。


这些检查证明本次委派和工具确实执行、消息与结果关联正确。固定的结束文案不作为成功证据；`completed` 也不证明模型摘要没有遗漏，摘要质量不在这个 offline 验证范围中。

## 5. 换一次新运行，观察 raw 的顺序与路径

raw 事件是底层协议对象，主要字段是 `seq`、`method` 和 `params`。`params.namespace` 标识事件来源的执行路径，根级通常为 `[]`，子图或更深层事件有路径段。判断某事件是否属于已知子 Agent，应做 **路径前缀匹配**，不能把任何非空路径都当成某个子 Agent 的显示名。

这里重新创建 Agent 和模型，再跑一次相同任务，不是在重放上一节。我们比较本次 raw 事件与本次子 Agent 的路径，不比较两次运行的动态 ID。

**先订阅，再推进**：`iter(run.subagents)` 先取得订阅游标，之后 `list(run)` 消费 raw 事件并推动图执行，最后读取已经缓冲的子 Agent handle。只访问属性还不等于订阅；投影也不是可随时读取的持久化日志。

本例只保存一次小实验的 raw 事件，不提供生产事件缓存。外层图仍设置执行步数上限 16；它不是费用或所有嵌套调用的全局资源上限。


```python
SUBSCRIBE_EARLY = True
raw_agent, raw_executions = make_agent()
with raw_agent.stream_events(
    REQUEST, config={"recursion_limit": 16}, version="v3",
    transformers=[CustomTransformer],
) as raw_run:
    child_cursor = iter(raw_run.subagents) if SUBSCRIBE_EARLY else None
    raw_events = list(raw_run)
    raw_children = list(child_cursor) if child_cursor is not None else list(raw_run.subagents)
    raw_final_state = raw_run.output

assert len(raw_children) == 1, "晚订阅可能漏掉委派；必须先订阅再推进运行。"
raw_path = raw_children[0].path
assert raw_children[0].status == "completed"
assert len(raw_executions) == 1
print("raw 事件数：", len(raw_events))
print("各 method 数量：")
for method, count in Counter(e["method"] for e in raw_events).items():
    print(f"  {method}: {count}")
show_text("本次 raw 子 Agent path：", raw_path)
```

    raw 事件数： 20
    各 method 数量：
      values: 8
      messages: 4
      tools: 4
      lifecycle: 2
      custom: 2
    
    本次 raw 子 Agent path：
    ('tools:37254e35-0e31-0c30-1888-f2d94454c8f8',)


### 5.1 校验 seq、取证路径与完整消息

`seq` 在同次 raw 运行内递增；即使只展示部分事件也应保留原序号，不能要求过滤后的序号连续。`timestamp` 可展示时间，但不代替序号排序。代码中的 `zip(sequences, sequences[1:])` 把相邻序号配成一对，逐对检查后一个是否更大。

下一格只打印工具与进度事件摘要，避免把整份状态、元数据和动态 ID 铺满输出。`belongs_to()` 用前缀匹配判断归属，根路径不会匹配到非空子 Agent 路径。

脚本模型的 raw `messages` 事件是 `(AIMessage, metadata)`，而非逐 token 的 `content-block-delta`。因此不写一个只接受文本增量的过滤器，再把“过滤结果为空”当成没有模型输出。live 的 raw 结构可能不同，本实验不解析供应商 token 协议。


```python
def belongs_to(namespace, path):
    return tuple(namespace[:len(path)]) == tuple(path)


sequences = [event["seq"] for event in raw_events]
assert sequences and all(type(seq) is int for seq in sequences)
assert all(left < right for left, right in zip(sequences, sequences[1:]))
assert all(isinstance(e["params"]["namespace"], list) for e in raw_events)
raw_progress = [
    e for e in raw_events if e["method"] == "custom"
    and belongs_to(e["params"]["namespace"], raw_path)
]
assert [e["params"]["data"] for e in raw_progress] == progress
assert not belongs_to([], raw_path)
assert belongs_to(list(raw_path) + ["model_request:example"], raw_path)
child_tool_events = [
    e for e in raw_events if e["method"] == "tools"
    and belongs_to(e["params"]["namespace"], raw_path)
]
started = [e for e in child_tool_events if e["params"]["data"]["event"] == "tool-started"]
finished = [e for e in child_tool_events if e["params"]["data"]["event"] == "tool-finished"]
assert len(started) == len(finished) == 1
start_data, finish_data = started[0]["params"]["data"], finished[0]["params"]["data"]
assert start_data["tool_name"] == "inspect_notes" and start_data["input"] == {"topic": TOPIC}
assert finish_data["tool_call_id"] == start_data["tool_call_id"]
assert isinstance(finish_data["output"], ToolMessage)
assert finish_data["output"].status == "success"
assert json.loads(finish_data["output"].text) == raw_executions[0]["result"]
assert started[0]["seq"] < raw_progress[0]["seq"] < raw_progress[1]["seq"] < finished[0]["seq"]

for event in raw_events:
    if event["method"] not in {"tools", "custom"}:
        continue
    params = event["params"]
    owner = "researcher" if belongs_to(params["namespace"], raw_path) else "主 Agent"
    data = params["data"]
    label = data.get("event", data.get("phase"))
    print(f"#{event['seq']:02d} [{owner}] {event['method']} / {label}")

if selected_mode() == "offline":
    message_events = [e for e in raw_events if e["method"] == "messages"]
    assert len(message_events) == 4
    assert all(isinstance(e["params"]["data"][0], AIMessage) for e in message_events)
    print("完整 AIMessage 事件数：", len(message_events), "（不是 token 数）")
```

    #04 [主 Agent] tools / tool-started
    #09 [researcher] tools / tool-started
    #10 [researcher] custom / starting
    #11 [researcher] custom / complete
    #12 [researcher] tools / tool-finished
    #16 [主 Agent] tools / tool-finished
    完整 AIMessage 事件数： 4 （不是 token 数）


默认输出应保留这样的顺序：子 Agent 工具 `tool-started` → 两条 custom 进度 → `tool-finished`。打印中的“主 Agent / researcher”是本例根据已知路径计算的标签，不是 raw 协议自带的 `source` 字段。

两次实验的 `progress` 都来自相同工具和固定数据，故内容一致；它们不是同一批事件。本次路径只用于本次 raw 事件路由。

## 6. 一个反例：先读 output，再订阅会怎样？

再创建独立实验，直接读 `late_run.output`。这个属性会推动图到结束，不只是读一个当前值。随后才订阅 `late_run.subagents`，将看不到已经过去的委派 handle。

这不是没有委派：实际工具执行记录和最终主 Agent 的 task 返回仍然存在。它说明“事情发生过”与“这个消费者及时订阅到了”是两件事。


```python
late_agent, late_executions = make_agent()
with late_agent.stream_events(REQUEST, config={"recursion_limit": 16}, version="v3") as late_run:
    late_output = late_run.output
    late_children = list(late_run.subagents)
assert len(late_executions) == 1
late_tool_results = [m for m in late_output["messages"] if isinstance(m, ToolMessage)]
assert len(late_tool_results) == 1 and late_tool_results[0].status == "success"
assert late_children == []
print("实际子 Agent 工具执行次数：", len(late_executions))
print("晚订阅收到的子 Agent handle 数：", len(late_children))
```

    实际子 Agent 工具执行次数： 1
    晚订阅收到的子 Agent handle 数： 0


## 7. 练习：只改订阅时机

1. 保持 offline，在第 **5** 节把 `SUBSCRIBE_EARLY = True` 改成 `False`。
2. 先预测：raw 事件和工具还会发生吗？晚订阅能得到 researcher handle 吗？
3. 重启内核并运行全部，第 5 节应在“晚订阅可能漏掉委派”的断言失败。
4. 失败时 raw 运行已经完整消费，工具已执行；不是任务还在后台等待。改变的是消费者的订阅时机。
5. 恢复 `True`，重启并运行全部，核对一条委派、raw 路径匹配和进度顺序重新通过。

不要同时修改模型、工具或事件过滤条件。若需要多个消费者读取同一投影，应在消费前使用框架的 `tee` 等分流机制；重复订阅不是日志重放，本实验不展开多消费者处理。

## 8. 边界、排错与清理

| 现象 | 检查位置 |
|---|---|
| 只有最终回复，没有 researcher | 模型是否实际请求 task；是否在执行前订阅 subagents |
| child.custom 不存在 | 是否注册 CustomTransformer；工具是否在当前子图发出事件 |
| 工具请求出现，但结果不合格 | 等运行结束后检查 completed、error、ToolMessage.status 和内容 |
| raw 文本过滤器没有输出 | 当前是完整消息还是 content-block 增量；不能只接受一种形式 |
| live 没按指定工具流程执行 | 查看实际模型请求与返回；断言会失败，不自动改成 offline |
| 流代码与旧例子的 type/ns/data 不同 | 本例使用 v3；v2 StreamPart 是另一层接口，不要混用循环 |

**验证范围**：同步 v3 投影、一次子 Agent 委派、工具与结果关联、custom 进度、raw 顺序和路径、晚订阅反例。没有验证逐 token 传输、异步并发消费、工具异常/子 Agent 失败的独立触发、v2 迁移、SSE 页面、网络断开、生产背压或持久化重放。Streaming 本身不等于并行，也不承担业务质量验收。

**清理**：每次流都在 `with` 中创建和消费，作用域退出会结束迭代器；不创建文件、服务器或持久后台任务。列表仅保存在当前内核，重启后清空。本例不使用 Checkpointer，三场实验之间也不共享会话状态。

下一步：回到[正文的 Streaming 应用模板](../../content/ch14-streaming.md)，为真实界面并发消费各投影；需要业务验收时另接入 [Rubric](../../content/ch13-grading-rubrics.md)。
