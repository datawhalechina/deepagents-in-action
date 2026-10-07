> 本次执行模式：**offline**。源码指纹：`2b88165f2dc1`。

# 第 8 章 Notebook：跨线程记忆与文件隔离

对应课程正文：[第 8 章：长期记忆](../../content/ch08-long-term-memory.md)。

用户在一段对话中说“以后代码注释用中文”。新对话能否得到这个偏好？如果上一段对话还写了临时草稿，新对话会不会同时拿到草稿？本实验把**共享的偏好**与**线程内的草稿**放在同一个 Agent 中，直接检查文件工具、存储记录和实际模型请求。

**预期结果**：同一用户的新线程能读到更新后的偏好，读不到旧线程草稿；回到旧线程仍能读草稿；另一用户只读到自己的偏好。观察不到任一工具结果，就不能只凭 Agent 最后说“完成”判定成功。

建议先理解 [第 1 章的消息与工具循环](../ch01/01-agent-harness.ipynb)；本实验从第一格独立运行，不需要其他 Notebook 的内核状态。

## 1. 环境、范围与三个容器

按 [统一安装说明](../README.md) 使用 Python 3.12 锁定环境。从仓库根目录运行：

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch08-long-term-memory
```

默认 **offline**：脚本模型按下面公开的规则请求文件工具；工具、Backend、Store、Checkpointer 和模型请求记录都真实执行。它验证数据边界，不证明真实模型会自主选择这些工具。按 README 配置支持工具调用的模型后，可显式加 `--mode live`；会产生网络请求与可能的费用。本实验不需要数据库或 Agent Server。

| 容器 | 保存什么 | 本实验中的作用 |
|---|---|---|
| Agent State + `StateBackend` | 当前线程的消息和虚拟文件 | 保存草稿；换线程不能直接读取 |
| `InMemorySaver` / Checkpointer | 以 `thread_id` 为键保存 State 快照 | 回到旧线程时恢复草稿 |
| `InMemoryStore` + `StoreBackend` | 以 namespace、key 保存共享文件 | 同一用户的新线程读到偏好 |

它们都只在这个 Python 进程的内存中。**跨线程可见不等于重启后还在**；生产环境需要持久化的 Store 与 Checkpointer。`/memories/preferences.json`、`/workspace/draft.txt` 是 Agent 虚拟路径，不是电脑磁盘路径。

`show_runtime()` 展示当前模式与依赖版本；`show_text()` 把工具输出折行。

### 硅流真实模型（live）

**待验证**（2026-10-06 核对）：当前版本尚无整本 live 通过记录。真实模型复测曾在保存场景反复提交同一组错误的 `edit_file` 参数；本节据此补上了文本参数的具体写法，以及重复错误的上限。暂不列出已验证型号，补验后再填写完整型号、日期、验证版本和记录链接。

配置：在未提交的根目录 `.env` 中填写 `SILICONFLOW_API_KEY` 和完整 `MODEL_NAME`；公共入口不提供隐含模型默认值。模型必须支持工具调用。API 地址、固定参数与报告字段见 [README 模型记录说明](../README.md#live-records)。随附输出仍为 offline。

范围与服务：模型选择文件工具并填写参数；Backend、Store、Checkpointer、工具参数校验与证据核对真实执行。数据都在内存里，无额外服务。


```python
from dataclasses import dataclass
import json
import re

from course_notebooks.model_config import create_model
from course_notebooks.nbtools import show_runtime, show_text
from course_notebooks.testing import ScriptedChatModel
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.backends.utils import create_file_data
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

show_runtime()
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.22
    langchain==1.4.3
    langchain-core==1.6.6
    langgraph==1.2.13
    langchain-openai==1.6.7


## 2. 先准备两个用户的记忆文件

`StoreBackend` 的 `namespace` 用用户 ID 隔离数据。这里用两个固定教学用户 `alice` 和 `bob`。Alice 先预置空 JSON 对象 `{}`；Bob 用同 schema 的另一对象：`comment_language="en"`、`variable_language="zh"`。Alice 保存后应为 `comment_language="zh"`、`variable_language="en"`。先预置文件，因为 `memory=[...]` 负责**读取已有文件**，不会为新用户自动创建文件。`create_file_data` 将文本转成 StoreBackend 期望的文件数据格式。

`CompositeBackend` 根据路径选择后端：`/memories/` 走 Store，其余路径走 State。路由会去掉 `/memories/` 前缀，所以 Agent 看见的 `/memories/preferences.json` 在 Store 中对应 key `/preferences.json`。此处的用户 ID 来自我们传入的运行上下文；实际服务应由经过身份验证的入口提供，不能直接信任任意客户端填的 ID。


```python
MEMORY_PATH = "/memories/preferences.json"
DRAFT_PATH = "/workspace/draft.txt"
STORE_KEY = "/preferences.json"
EXPECTED_PREFERENCES = {"comment_language": "zh", "variable_language": "en"}
BOB_PREFERENCES = {"comment_language": "en", "variable_language": "zh"}
PREFERENCE_JSON = json.dumps(EXPECTED_PREFERENCES, ensure_ascii=False)
DRAFT_TEXT = "仅本线程可见：草稿 42"

@dataclass(frozen=True)
class UserContext:
    user_id: str

store = InMemoryStore()
store.put(("alice", "memories"), STORE_KEY,
          create_file_data("{}"))
store.put(("bob", "memories"), STORE_KEY,
          create_file_data(json.dumps(BOB_PREFERENCES)))

backend = CompositeBackend(
    default=StateBackend(),
    routes={"/memories/": StoreBackend(
        namespace=lambda runtime: (runtime.context.user_id, "memories"),
    )},
)
print("已初始化两个用户的偏好文件；虚拟路由：/memories/ → Store，其余 → State")
```

    已初始化两个用户的偏好文件；虚拟路由：/memories/ → Store，其余 → State


## 3. 指定工具调用，并记录真正进入模型的请求

`AIMessage` 中的 `tool_calls` 只是模型提出的调用请求；框架随后执行工具并产生 `ToolMessage`。默认脚本模型按当前用户消息和本轮已返回的工具结果决定下一步，不直接改 Store 或 State：

| 场景 | 请求的工具 |
|---|---|
| 保存 | `read_file` 偏好 → `edit_file` 偏好 → `write_file` 草稿 |
| 新线程 | `read_file` 偏好 → `read_file` 草稿 |
| 旧线程 | `read_file` 草稿 |
| 其他用户 | `read_file` 偏好 |

`edit_file` 的 `old_string`、`new_string` 是**字符串**参数：`old_string` 用 `read_file` 返回的原文件正文，`new_string` 用 `json.dumps(对象, ensure_ascii=False)` 得到的文本。传 JSON 对象会被工具的真实参数校验拒绝，工具层不会替模型把对象转成字符串。

同一个工具以完全相同的参数反复失败达到上限时，`StopRepeatedToolErrors` 会在下一次模型请求前结束本次执行，`run_scene` 先展示这些实际请求和工具返回，再明确失败。

最后一句“已完成”由脚本预设，不能当证据。`tool_names` 是 Agent 当次提供的工具名；本例先核对所需工具确实注册。真实模型模式下 `create_model` 会选用 README 中配置的模型，这张固定调用表不再决定其行为。


```python
def scripted_reply(messages, tool_names):
    latest = max(i for i, message in enumerate(messages)
                 if isinstance(message, HumanMessage))
    scene = messages[latest].text.split("：", 1)[0]
    returned = [message for message in messages[latest + 1:]
                if isinstance(message, ToolMessage)]
    plans = {
        "保存": [("read_file", {"file_path": MEMORY_PATH}),
               ("edit_file", {"file_path": MEMORY_PATH,
                              "old_string": "{}", "new_string": PREFERENCE_JSON}),
               ("write_file", {"file_path": DRAFT_PATH, "content": DRAFT_TEXT})],
        "新线程": [("read_file", {"file_path": MEMORY_PATH}),
                   ("read_file", {"file_path": DRAFT_PATH})],
        "旧线程": [("read_file", {"file_path": DRAFT_PATH})],
        "其他用户": [("read_file", {"file_path": MEMORY_PATH})],
    }
    steps = plans[scene]
    if len(returned) == len(steps):
        return AIMessage(content="已完成实验；请检查工具结果。")
    name, args = steps[len(returned)]
    assert name in tool_names, f"Agent 没有注册工具 {name}"
    return AIMessage(content="", tool_calls=[{
        "name": name, "args": args, "id": f"ch08-{scene}-{len(returned)}",
    }])

model = create_model(ScriptedChatModel(responder=scripted_reply))
```

`memory=[MEMORY_PATH]` 会让框架在模型请求中加入**已有文件**的内容。为了验证“模型真的收到更新后的偏好”，下面使用 LangChain 的回调记录 `on_chat_model_start` 收到的实际 messages 对象。回调只观察，不替模型生成答案；验收只解析首次实际 `SystemMessage` 的 `<agent_memory>` 内、`MEMORY_PATH` 标题下的 JSON 正文，不在用户指令或整个 prompt 中搜语言关键词。输出只展示解析后的对象，避免打印整个系统提示词。


```python
class ModelRequestRecorder(BaseCallbackHandler):
    def __init__(self):
        self.requests = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.requests.append(list(messages[0]))


class StopRepeatedToolErrors(AgentMiddleware):
    """同一个工具以完全相同参数反复失败到上限时，显式结束本次执行。

    结果仍然保留：调用方先展示实际请求与工具返回，再判定失败。
    真实模型一直提交同一组错误参数时，不会重试到限流或超时。
    """

    def __init__(self, stop_after=2):
        super().__init__()
        self.stop_after = stop_after
        self.stopped = []

    def before_agent(self, state, runtime):
        # 每次 invoke 都是一次新的执行，重新统计。
        self.stopped = []
        return None

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):
        messages = state["messages"]
        latest = max(i for i, message in enumerate(messages)
                     if isinstance(message, HumanMessage))
        calls, counts = {}, {}
        # 保留 checkpoint 历史，只统计本次用户请求之后的错误。
        for message in messages[latest + 1:]:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    calls[call["id"]] = call
            elif isinstance(message, ToolMessage) and message.status == "error":
                call = calls.get(message.tool_call_id)
                if call is not None:
                    signature = (call["name"], json.dumps(
                        call["args"], sort_keys=True, ensure_ascii=False))
                    counts[signature] = counts.get(signature, 0) + 1
        self.stopped = [signature for signature, count in counts.items()
                        if count >= self.stop_after]
        return {"jump_to": "end"} if self.stopped else None


tool_error_guard = StopRepeatedToolErrors()

agent = create_deep_agent(
    model=model,
    backend=backend,
    store=store,
    checkpointer=InMemorySaver(),
    context_schema=UserContext,
    memory=[MEMORY_PATH],
    middleware=[tool_error_guard],
    system_prompt=(
        f"用户要求记住偏好时，先读取 {MEMORY_PATH}，再用 edit_file 更新原文件。"
        "偏好文件只保存用户指定的两字段 JSON 对象，不加日期或其他字段；"
        "edit_file 的 old_string 用 read_file 返回的原文件正文，"
        "new_string 用 json.dumps(偏好对象, ensure_ascii=False) 得到的字符串；"
        "两个参数都必须是字符串，工具不会把 JSON 对象自动转成字符串。"
        f"然后继续用 write_file 将本轮临时草稿写到 {DRAFT_PATH}。"
        "用户要求查看文件时，用 read_file 回答。工具出错时不要声称读到了内容。"
    ),
)
print("Agent 已组装；尚未执行任何场景。")
```

    Agent 已组装；尚未执行任何场景。


## 4. 运行场景并整理证据

`invoke` 启动一次 Agent 执行。`messages` 是输入消息；`configurable.thread_id` 选择要恢复的对话线程；`context` 提供 namespace 所需的用户 ID。返回的 `messages` 包含模型请求和工具结果。

旧线程的历史也会出现在返回值里，所以辅助函数只截取**本次最新用户消息之后**的记录。它逐条打印工具名、参数、状态和折行后的结果，同时按 `tool_call_id` 将工具结果与请求对应。回调记录的第一条请求用于检查这次执行起步时注入了哪份记忆。

锁定版本的 `read_file` 以 `@@ lines 1-N of N @@` 标明完整范围，后面才是文件正文；辅助函数核对范围和正文行数，拒绝不完整分页。Store 正文、工具正文和系统 memory 正文统一用 `json.loads` 解析，要求整个对象严格相等：换序和空白可接受，缺字段、错值、额外日期都失败。

同一个工具以完全相同参数连续失败达到上限时，`StopRepeatedToolErrors` 会在下一次模型请求前结束本次执行：`jump_to="end"` 让结果仍完整保留，`run_scene` 先打印这些实际请求与工具返回，再明确失败。这样模型重复提交同一组错误参数时不会一直重试到限流或超时。错误只统计最新用户消息之后的本次执行；同一线程追加修正后的请求时重新统计，历史消息仍保留在 checkpoint 中。


```python
def scene_evidence(messages):
    """只验收最新用户消息后的调用；返回必须在对应调用之后且 ID、工具名唯一匹配。"""
    latest = max(i for i, message in enumerate(messages)
                 if isinstance(message, HumanMessage))
    calls, returns, pending, seen = [], [], {}, set()
    for message in messages[latest + 1:]:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                assert call["id"] not in seen, "工具调用 ID 重复"
                seen.add(call["id"])
                pending[call["id"]] = call
                calls.append(call)
        elif isinstance(message, ToolMessage):
            call = pending.pop(message.tool_call_id, None)
            assert call is not None, "工具返回没有唯一的先前调用"
            assert message.name == call["name"], "工具返回名称与调用不一致"
            returns.append(message)
    assert not pending, "工具调用缺少返回"
    return calls, returns


def run_scene(scene, thread_id, user_id, instruction):
    recorder = ModelRequestRecorder()
    result = agent.invoke(
        {"messages": [("user", f"{scene}：{instruction}")]},
        config={"configurable": {"thread_id": thread_id}, "callbacks": [recorder]},
        context=UserContext(user_id=user_id),
    )
    calls, returns = scene_evidence(result["messages"])
    assert recorder.requests, "没有记录到模型请求"
    run = {"result": result, "calls": calls, "returns": returns,
           "first_request": recorder.requests[0]}
    print(f"\n【{scene}】用户={user_id}，线程={thread_id}")
    print("  本轮工具调用数：", len(calls))
    for call, reply in ((call, next(item for item in returns
                                   if item.tool_call_id == call["id"]))
                        for call in calls):
        print(f"  {call['id']}: {call['name']}({call['args'].get('file_path')}) → "
              f"{reply.status}")
        show_text("  工具返回：", reply.text, width=78)
    if tool_error_guard.stopped:
        # 相同参数反复失败：已显式结束，先展示实际请求与工具返回再判定失败。
        for name, arguments in tool_error_guard.stopped:
            for call in calls:
                signature = (call["name"], json.dumps(
                    call["args"], sort_keys=True, ensure_ascii=False))
                if signature != (name, arguments):
                    continue
                reply = next(item for item in returns
                             if item.tool_call_id == call["id"])
                show_text(f"重复失败的 {name} 请求 {call['id']}：",
                          json.dumps(call["args"], ensure_ascii=False, indent=2))
                show_text("  对应工具返回：", reply.text, width=78)
        raise AssertionError(
            "同一个工具以相同参数反复失败，本次执行已按上限结束；"
            "上面是实际请求与工具返回。"
        )
    return run


def tool_reply(run, name, path):
    """调用关联已经由 scene_evidence 核对；按工具名和路径选本轮结果。"""
    for call in run["calls"]:
        if call["name"] == name and call["args"].get("file_path") == path:
            return next(message for message in run["returns"]
                        if message.tool_call_id == call["id"])
    return None


def parse_preferences(content, expected):
    """对象严格相等：允许换序、空白，不允许缺字段、错误值或额外字段。"""
    value = json.loads(content)
    assert isinstance(value, dict) and value == expected, "偏好 JSON 对象不符合预期"
    return value


def read_file_content(reply):
    """取完整文件正文，不能把范围头一起交给 json.loads 或接受部分分页。"""
    assert reply is not None and reply.status == "success", "文件读取未成功"
    lines = reply.text.splitlines()
    header = re.fullmatch(r"@@ lines (\d+)-(\d+) of (\d+) @@", lines[0]) if lines else None
    assert header is not None, "缺少完整文件范围头"
    start, end, total = map(int, header.groups())
    assert start == 1 and end == total and total > 0, "拒绝不完整分页"
    body = lines[1:]
    assert len(body) == total, "文件正文行数不完整"
    return "\n".join(body)


def memory_content(first_request):
    """只取实际 SystemMessage 的 agent_memory 中指定路径下的文件正文。"""
    system = "\n".join(message.text for message in first_request
                       if isinstance(message, SystemMessage))
    blocks = re.findall(r"^<agent_memory>\n(.*?)\n\n</agent_memory>",
                        system, flags=re.MULTILINE | re.DOTALL)
    assert len(blocks) == 1, "没有唯一的实际 memory 注入块"
    path, separator, content = blocks[0].partition("\n\n")
    assert separator and path == MEMORY_PATH, "memory 未加载指定偏好文件"
    return content


def validate_preferences(run, user_id, expected):
    """Store、真实 read_file 和首次系统 memory 各自独立验收同一完整对象。"""
    record = store.get((user_id, "memories"), STORE_KEY)
    assert record is not None, "用户 namespace 中没有偏好记录"
    stored = parse_preferences(record.value["content"], expected)
    read = parse_preferences(read_file_content(tool_reply(run, "read_file", MEMORY_PATH)), expected)
    injected = parse_preferences(memory_content(run["first_request"]), expected)
    return {"store": stored, "read_file": read, "agent_memory": injected}


def validate_saved(run):
    """先读再编辑、草稿写入成功及最终产物是验收目标，不限制额外工具调用。"""
    read = tool_reply(run, "read_file", MEMORY_PATH)
    assert read is not None and read.status == "success", "read_file 未成功"
    # 参数错误被拒绝后可以重试；这里取真正成功的那次 edit_file，仍要求先读再编辑。
    edits = [reply for call in run["calls"]
             if call["name"] == "edit_file" and call["args"].get("file_path") == MEMORY_PATH
             for reply in run["returns"] if reply.tool_call_id == call["id"]]
    edit = next((reply for reply in edits if reply.status == "success"), None)
    assert edit is not None, "edit_file 未成功"
    draft = tool_reply(run, "write_file", DRAFT_PATH)
    assert draft is not None and draft.status == "success", "write_file 未成功"
    call_ids = [call["id"] for call in run["calls"]]
    assert call_ids.index(read.tool_call_id) < call_ids.index(edit.tool_call_id), "必须先读再编辑"
    parse_preferences(read_file_content(read), {})
    parse_preferences(memory_content(run["first_request"]), {})
    record = store.get(("alice", "memories"), STORE_KEY)
    assert record is not None, "Alice 的 namespace 中没有保存偏好"
    parse_preferences(record.value["content"], EXPECTED_PREFERENCES)
    assert run["result"]["files"][DRAFT_PATH]["content"] == DRAFT_TEXT
    assert MEMORY_PATH not in run["result"]["files"], "偏好不应写入 State"
    assert store.get(("alice", "memories"), DRAFT_PATH) is None, "草稿不应写入 Store"

```

### 4.1 第一段对话：更新偏好并写草稿

`edit_file` 更新 Store 中已有偏好；`write_file` 写入 State 中的草稿。验收检查偏好先读再编辑、所需工具成功，再核对 Alice 的 Store JSON 和 State 草稿；额外工具调用完整保留，不因此判错。`edit_file` 的两个正文参数是字符串：`old_string` 用读取到的原文，`new_string` 用 `json.dumps(偏好对象, ensure_ascii=False)`；传 JSON 对象会被工具参数校验拒绝。即使工具报告成功，写错 namespace 或内容也不能通过。此时用户 `alice` 的记忆提示词仍是本轮开始时加载的旧对象 `{}`；写入后的值要在**新线程**检查。


```python
saved = run_scene(
    "保存", "alice-original", "alice",
    f"请把 {MEMORY_PATH} 更新为 JSON 对象 {PREFERENCE_JSON}，"
    '字段 comment_language 必须为 "zh"，variable_language 必须为 "en"；'
    "只保留这两个字段，不添加日期或其他字段。"
    "先用 read_file 读取原文件，再用 edit_file 替换整个文件："
    'old_string 用 read_file 返回的原文件正文（初始是字符串 "{}"），'
    f"new_string 用字符串 {PREFERENCE_JSON!r}；"
    "这两个参数都必须是字符串，不要传 JSON 对象。"
    f"然后继续用 write_file 写临时草稿 {DRAFT_PATH}，内容是“{DRAFT_TEXT}”。",
)
validate_saved(saved)
alice_record = store.get(("alice", "memories"), STORE_KEY)
show_text("Store 中 Alice 的偏好 JSON：", alice_record.value["content"])
print("旧线程的 State 文件：", list(saved["result"].get("files", {})))

```

    
    【保存】用户=alice，线程=alice-original
      本轮工具调用数： 3
      ch08-保存-0: read_file(/memories/preferences.json) → success
    
      工具返回：
    @@ lines 1-1 of 1 @@
    {}
      ch08-保存-1: edit_file(/memories/preferences.json) → success
    
      工具返回：
    Successfully replaced 1 instance(s) of the string in
      '/memories/preferences.json'
      ch08-保存-2: write_file(/workspace/draft.txt) → success
    
      工具返回：
    Updated file /workspace/draft.txt
    
    Store 中 Alice 的偏好 JSON：
    {"comment_language": "zh", "variable_language": "en"}
    旧线程的 State 文件： ['/workspace/draft.txt']


看上面的工具返回与 Store：偏好和草稿经不同后端写入。`Store.get` 是 Python 直接核对存储内容；它本身不能证明新线程的模型已经看到了偏好，所以下一步还要检查模型请求。

### 4.2 同一用户的新线程：偏好可读，草稿不可读

给 `alice` 换一个 `thread_id`，但复用同一个 Store。预期偏好读取成功，草稿读取报“文件不存在”。这个错误是**预期边界**，不是 Notebook 执行失败。


```python
fresh = run_scene(
    "新线程", "alice-fresh", "alice",
    f"请分别读取 {MEMORY_PATH} 和 {DRAFT_PATH}，报告实际工具结果。",
)
draft_miss = tool_reply(fresh, "read_file", DRAFT_PATH)
assert draft_miss is not None and draft_miss.status == "error"
assert DRAFT_PATH not in fresh["result"].get("files", {})
alice_evidence = validate_preferences(fresh, "alice", EXPECTED_PREFERENCES)
print("首次模型请求中的偏好对象：", alice_evidence["agent_memory"])
print("新线程读不到旧草稿。")

```

    
    【新线程】用户=alice，线程=alice-fresh
      本轮工具调用数： 2
      ch08-新线程-0: read_file(/memories/preferences.json) → success
    
      工具返回：
    @@ lines 1-1 of 1 @@
    {"comment_language": "zh", "variable_language": "en"}
      ch08-新线程-1: read_file(/workspace/draft.txt) → error
    
      工具返回：
    Error: File '/workspace/draft.txt' not found
    首次模型请求中的偏好对象： {'comment_language': 'zh', 'variable_language': 'en'}
    新线程读不到旧草稿。


`read_file` 的成功返回说明 Agent 能通过虚拟文件工具读取 Store；首次模型请求的系统 memory 正文也严格等于 Alice 的 JSON 对象，说明 `memory=` 确实将已有文件注入。草稿读取失败只说明**新线程隔离**，不代表旧线程的数据被删除。

### 4.3 回到旧线程：草稿仍在

复用 `alice-original` 的 `thread_id`，由 Checkpointer 恢复旧 State。查看工具结果，并直接读取该线程的 checkpoint 里的 `files` 字段。这个字段是 Agent State 的一部分，不是 Store 记录。


```python
resumed = run_scene(
    "旧线程", "alice-original", "alice",
    f"回到原对话，请读取先前的临时草稿 {DRAFT_PATH}。",
)
draft_read = tool_reply(resumed, "read_file", DRAFT_PATH)
assert draft_read is not None and draft_read.status == "success"
assert read_file_content(draft_read) == DRAFT_TEXT
old_state = agent.get_state({"configurable": {"thread_id": "alice-original"}})
assert old_state.values["files"][DRAFT_PATH]["content"] == DRAFT_TEXT
parse_preferences(memory_content(resumed["first_request"]), {})
print("旧线程 checkpoint 中仍有：", list(old_state.values["files"]))
```

    
    【旧线程】用户=alice，线程=alice-original
      本轮工具调用数： 1
      ch08-旧线程-0: read_file(/workspace/draft.txt) → success
    
      工具返回：
    @@ lines 1-1 of 1 @@
    仅本线程可见：草稿 42
    旧线程 checkpoint 中仍有： ['/workspace/draft.txt']


注意时机：这个旧线程恢复了先前已经加载的记忆提示词。即使 Store 文件现在已更新，旧线程的首次模型请求仍可能保留本轮之前注入的旧文本。因此本实验用**新线程**检查“更新后重新注入”，不把旧线程提示词当作实时同步证据。

### 4.4 另一个用户：namespace 隔离

同一个 Agent 与同一个 Store，改用 `bob` 的运行上下文。预期 Store、真实 `read_file` 正文、首次系统 memory 正文都严格等于 Bob 的对象 `{"comment_language": "en", "variable_language": "zh"}`；任一处串入 Alice 的对象都会失败。


```python
other_user = run_scene(
    "其他用户", "bob-first", "bob",
    f"请读取你自己的偏好文件 {MEMORY_PATH}。",
)
bob_evidence = validate_preferences(other_user, "bob", BOB_PREFERENCES)
assert BOB_PREFERENCES != EXPECTED_PREFERENCES
print("首次模型请求中的偏好对象：", bob_evidence["agent_memory"])
print("Bob 的工具结果、Store 文件和首次模型请求均严格匹配 Bob 的对象。")

```

    
    【其他用户】用户=bob，线程=bob-first
      本轮工具调用数： 1
      ch08-其他用户-0: read_file(/memories/preferences.json) → success
    
      工具返回：
    @@ lines 1-1 of 1 @@
    {"comment_language": "en", "variable_language": "zh"}
    首次模型请求中的偏好对象： {'comment_language': 'en', 'variable_language': 'zh'}
    Bob 的工具结果、Store 文件和首次模型请求均严格匹配 Bob 的对象。


## 5. 回顾、边界与练习

本次从实际证据得到四个结论：

1. `edit_file` 更新了 `alice` 的 Store 文件；同用户新线程的 `read_file` 成功，首次模型请求含更新后的偏好。
2. 新线程读取旧草稿得到工具错误；旧线程读取成功，checkpoint 的 State 中仍有草稿。
3. `bob` 的工具结果、Store 文件和首次模型请求使用另一 namespace。
4. 这些记录都在内存里；**跨线程共享**是本实验的结论，不是进程重启后的持久化保证。也没有测试访问控制：实际用户身份应由服务入口认证。

保存场景的 `edit_file` 参数必须是字符串；同一组错误参数重复到上限时，`StopRepeatedToolErrors` 会显式结束并展示实际请求与返回，不会重试到限流或超时。

**改一个变量再观察**：把 4.2 中 `run_scene` 的线程 ID 从 `"alice-fresh"` 改成 `"alice-original"`，保持用户仍为 `alice`。先预测草稿读取的状态：它应从预期错误变成成功，后面的 `assert draft_miss.status == "error"` 会停止。看打印出来的 `read_file` 结果核对原因。然后恢复线程 ID、重启内核并从第一格全部运行，四个场景应重新通过。

还可把脚本保存对象加一个 `date` 字段，预测 Store 严格比较应失败；或故意将 namespace 固定为 Alice，预测 Bob 的工具即使 success，JSON 验收也会失败。检查 `/memories/preferences.json`（Store key 为 `/preferences.json`）的对象，恢复修改后重启内核全部运行。

如果 `memory=` 提示词断言失败，先检查是否预置了对应 Store 文件、路由 key 是否去掉 `/memories/` 前缀，以及是否用了新的线程。下一步可回到 [第 8 章正文](../../content/ch08-long-term-memory.md)了解持久化 Store、更多作用域和记忆整理。重启当前内核即可清理本实验的内存数据。
