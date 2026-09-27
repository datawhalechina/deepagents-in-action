> 本次执行模式：**offline**。源码指纹：`c4587349f0fd`。

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

它们都只在这个 Python 进程的内存中。**跨线程可见不等于重启后还在**；生产环境需要持久化的 Store 与 Checkpointer。`/memories/preferences.md`、`/workspace/draft.txt` 是 Agent 虚拟路径，不是电脑磁盘路径。

`show_runtime()` 展示当前模式与依赖版本；`show_text()` 把工具输出折行。


```python
from dataclasses import dataclass

from course_notebooks.model_config import create_model
from course_notebooks.nbtools import show_runtime, show_text
from course_notebooks.testing import ScriptedChatModel
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.backends.utils import create_file_data
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

show_runtime()
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


## 2. 先准备两个用户的记忆文件

`StoreBackend` 的 `namespace` 用用户 ID 隔离数据。这里用两个固定教学用户 `alice` 和 `bob`。先预置文件，因为 `memory=[...]` 负责**读取已有文件**，不会为新用户自动创建文件。`create_file_data` 将文本转成 StoreBackend 期望的文件数据格式。

`CompositeBackend` 根据路径选择后端：`/memories/` 走 Store，其余路径走 State。路由会去掉 `/memories/` 前缀，所以 Agent 看见的 `/memories/preferences.md` 在 Store 中对应 key `/preferences.md`。此处的用户 ID 来自我们传入的运行上下文；实际服务应由经过身份验证的入口提供，不能直接信任任意客户端填的 ID。


```python
MEMORY_PATH = "/memories/preferences.md"
DRAFT_PATH = "/workspace/draft.txt"
STORE_KEY = "/preferences.md"
PREFERENCE = "代码注释用中文，变量名用英文。"
DRAFT_TEXT = "仅本线程可见：草稿 42"

@dataclass(frozen=True)
class UserContext:
    user_id: str

store = InMemoryStore()
store.put(("alice", "memories"), STORE_KEY,
          create_file_data("# 用户偏好\n暂无记录。\n"))
store.put(("bob", "memories"), STORE_KEY,
          create_file_data("# 用户偏好\n回答尽量详细。\n"))

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
                              "old_string": "暂无记录。", "new_string": PREFERENCE}),
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

`memory=[MEMORY_PATH]` 会让框架在模型请求中加入**已有文件**的内容。为了验证“模型真的收到更新后的偏好”，下面使用 LangChain 的回调记录 `on_chat_model_start` 收到的实际请求文本。回调只观察，不替模型生成答案；输出只展示与实验有关的短片段，避免打印整个系统提示词。


```python
class ModelRequestRecorder(BaseCallbackHandler):
    def __init__(self):
        self.requests = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.requests.append("\n".join(message.text for message in messages[0]))

agent = create_deep_agent(
    model=model,
    backend=backend,
    store=store,
    checkpointer=InMemorySaver(),
    context_schema=UserContext,
    memory=[MEMORY_PATH],
    system_prompt=(
        f"用户要求记住偏好时，先读取 {MEMORY_PATH}，再用 edit_file 更新原文件；"
        f"将本轮临时草稿写到 {DRAFT_PATH}。"
        "用户要求查看文件时，用 read_file 回答。工具出错时不要声称读到了内容。"
    ),
)
print("Agent 已组装；尚未执行任何场景。")
```

    Agent 已组装；尚未执行任何场景。


## 4. 运行场景并整理证据

`invoke` 启动一次 Agent 执行。`messages` 是输入消息；`configurable.thread_id` 选择要恢复的对话线程；`context` 提供 namespace 所需的用户 ID。返回的 `messages` 包含模型请求和工具结果。

旧线程的历史也会出现在返回值里，所以辅助函数只截取**本次最新用户消息之后**的记录。它逐条打印工具名、参数、状态和折行后的结果，同时按 `tool_call_id` 将工具结果与请求对应。回调记录的第一条请求用于检查这次执行起步时注入了哪份记忆。


```python
def run_scene(scene, thread_id, user_id, instruction):
    recorder = ModelRequestRecorder()
    result = agent.invoke(
        {"messages": [("user", f"{scene}：{instruction}")]},
        config={"configurable": {"thread_id": thread_id}, "callbacks": [recorder]},
        context=UserContext(user_id=user_id),
    )
    messages = result["messages"]
    latest = max(i for i, message in enumerate(messages)
                 if isinstance(message, HumanMessage))
    current = messages[latest + 1:]
    calls = [call for message in current if isinstance(message, AIMessage)
             for call in message.tool_calls]
    returns = [message for message in current if isinstance(message, ToolMessage)]
    assert recorder.requests, "没有记录到模型请求"
    print(f"\n【{scene}】用户={user_id}，线程={thread_id}")
    print("  本轮工具调用数：", len(calls))
    for call in calls:
        reply = next((item for item in returns
                      if item.tool_call_id == call["id"]), None)
        print(f"  {call['name']}({call['args'].get('file_path')}) → "
              f"{reply.status if reply else '无返回'}")
        if reply:
            show_text("  工具返回：", reply.text, width=78)
    return {"result": result, "calls": calls, "returns": returns,
            "first_request": recorder.requests[0]}


def tool_reply(run, name, path):
    """按调用 ID 找到本轮指定文件工具的实际返回。"""
    for call in run["calls"]:
        if call["name"] == name and call["args"].get("file_path") == path:
            return next((message for message in run["returns"]
                         if message.tool_call_id == call["id"]), None)
    return None
```

### 4.1 第一段对话：更新偏好并写草稿

`edit_file` 更新 Store 中已有偏好；`write_file` 写入 State 中的草稿。只有两条真实工具结果成功，后面才有意义。此时用户 `alice` 的记忆提示词仍是本轮开始时加载的旧文本；写入后的值要在**新线程**检查。


```python
saved = run_scene(
    "保存", "alice-original", "alice",
    f"请记住我的偏好：{PREFERENCE} 先读原文件，再更新偏好；"
    f"另外写一份临时草稿，内容是“{DRAFT_TEXT}”。",
)
for name, path in (("read_file", MEMORY_PATH),
                   ("edit_file", MEMORY_PATH),
                   ("write_file", DRAFT_PATH)):
    reply = tool_reply(saved, name, path)
    assert reply is not None and reply.status == "success", f"{name}({path}) 未成功"

alice_record = store.get(("alice", "memories"), STORE_KEY)
assert alice_record is not None and PREFERENCE in alice_record.value["content"]
show_text("Store 中 Alice 的偏好：", alice_record.value["content"])
print("旧线程的 State 文件：", list(saved["result"].get("files", {})))
```

    
    【保存】用户=alice，线程=alice-original
      本轮工具调用数： 3
      read_file(/memories/preferences.md) → success
    
      工具返回：
    @@ lines 1-2 of 2 @@
    # 用户偏好
    暂无记录。
      edit_file(/memories/preferences.md) → success
    
      工具返回：
    Successfully replaced 1 instance(s) of the string in
      '/memories/preferences.md'
      write_file(/workspace/draft.txt) → success
    
      工具返回：
    Updated file /workspace/draft.txt
    
    Store 中 Alice 的偏好：
    # 用户偏好
    代码注释用中文，变量名用英文。
    旧线程的 State 文件： ['/workspace/draft.txt']


看上面的工具返回与 Store：偏好和草稿经不同后端写入。`Store.get` 是 Python 直接核对存储内容；它本身不能证明新线程的模型已经看到了偏好，所以下一步还要检查模型请求。

### 4.2 同一用户的新线程：偏好可读，草稿不可读

给 `alice` 换一个 `thread_id`，但复用同一个 Store。预期偏好读取成功，草稿读取报“文件不存在”。这个错误是**预期边界**，不是 Notebook 执行失败。


```python
fresh = run_scene(
    "新线程", "alice-fresh", "alice",
    f"请分别读取 {MEMORY_PATH} 和 {DRAFT_PATH}，报告实际工具结果。",
)
preference_read = tool_reply(fresh, "read_file", MEMORY_PATH)
draft_miss = tool_reply(fresh, "read_file", DRAFT_PATH)
assert preference_read is not None and preference_read.status == "success"
assert PREFERENCE in preference_read.text
assert draft_miss is not None and draft_miss.status == "error"
assert DRAFT_PATH not in fresh["result"].get("files", {})
assert PREFERENCE in fresh["first_request"], "新线程的模型请求未包含更新后的记忆"
print("首次模型请求中的偏好：",
      next(line.strip() for line in fresh["first_request"].splitlines()
           if PREFERENCE in line))
print("新线程读不到旧草稿。")
```

    
    【新线程】用户=alice，线程=alice-fresh
      本轮工具调用数： 2
      read_file(/memories/preferences.md) → success
    
      工具返回：
    @@ lines 1-2 of 2 @@
    # 用户偏好
    代码注释用中文，变量名用英文。
      read_file(/workspace/draft.txt) → error
    
      工具返回：
    Error: File '/workspace/draft.txt' not found
    首次模型请求中的偏好： 代码注释用中文，变量名用英文。
    新线程读不到旧草稿。


`read_file` 的成功返回说明 Agent 能通过虚拟文件工具读取 Store；首次模型请求中也已有更新后的文本，说明 `memory=` 确实将已有文件注入。草稿读取失败只说明**新线程隔离**，不代表旧线程的数据被删除。

### 4.3 回到旧线程：草稿仍在

复用 `alice-original` 的 `thread_id`，由 Checkpointer 恢复旧 State。查看工具结果，并直接读取该线程的 checkpoint 里的 `files` 字段。这个字段是 Agent State 的一部分，不是 Store 记录。


```python
resumed = run_scene(
    "旧线程", "alice-original", "alice",
    f"回到原对话，请读取先前的临时草稿 {DRAFT_PATH}。",
)
draft_read = tool_reply(resumed, "read_file", DRAFT_PATH)
assert draft_read is not None and draft_read.status == "success"
assert DRAFT_TEXT in draft_read.text
old_state = agent.get_state({"configurable": {"thread_id": "alice-original"}})
assert DRAFT_PATH in old_state.values.get("files", {})
print("旧线程 checkpoint 中仍有：", list(old_state.values["files"]))
```

    
    【旧线程】用户=alice，线程=alice-original
      本轮工具调用数： 1
      read_file(/workspace/draft.txt) → success
    
      工具返回：
    @@ lines 1-1 of 1 @@
    仅本线程可见：草稿 42
    旧线程 checkpoint 中仍有： ['/workspace/draft.txt']


注意时机：这个旧线程恢复了先前已经加载的记忆提示词。即使 Store 文件现在已更新，旧线程的首次模型请求仍可能保留本轮之前注入的旧文本。因此本实验用**新线程**检查“更新后重新注入”，不把旧线程提示词当作实时同步证据。

### 4.4 另一个用户：namespace 隔离

同一个 Agent 与同一个 Store，改用 `bob` 的运行上下文。预期读取 Bob 的“回答尽量详细”，且模型首次请求不包含 Alice 刚保存的偏好。


```python
other_user = run_scene(
    "其他用户", "bob-first", "bob",
    f"请读取你自己的偏好文件 {MEMORY_PATH}。",
)
bob_read = tool_reply(other_user, "read_file", MEMORY_PATH)
assert bob_read is not None and bob_read.status == "success"
assert "回答尽量详细" in bob_read.text and PREFERENCE not in bob_read.text
assert "回答尽量详细" in other_user["first_request"]
assert PREFERENCE not in other_user["first_request"]
bob_record = store.get(("bob", "memories"), STORE_KEY)
assert bob_record is not None and "回答尽量详细" in bob_record.value["content"]
print("首次模型请求中的偏好：",
      next(line.strip() for line in other_user["first_request"].splitlines()
           if "回答尽量详细" in line))
print("Bob 的工具结果、Store 文件和首次模型请求均使用 Bob 的 namespace。")
```

    
    【其他用户】用户=bob，线程=bob-first
      本轮工具调用数： 1
      read_file(/memories/preferences.md) → success
    
      工具返回：
    @@ lines 1-2 of 2 @@
    # 用户偏好
    回答尽量详细。
    首次模型请求中的偏好： 回答尽量详细。
    Bob 的工具结果、Store 文件和首次模型请求均使用 Bob 的 namespace。


## 5. 回顾、边界与练习

本次从实际证据得到四个结论：

1. `edit_file` 更新了 `alice` 的 Store 文件；同用户新线程的 `read_file` 成功，首次模型请求含更新后的偏好。
2. 新线程读取旧草稿得到工具错误；旧线程读取成功，checkpoint 的 State 中仍有草稿。
3. `bob` 的工具结果、Store 文件和首次模型请求使用另一 namespace。
4. 这些记录都在内存里；**跨线程共享**是本实验的结论，不是进程重启后的持久化保证。也没有测试访问控制：实际用户身份应由服务入口认证。

**改一个变量再观察**：把 4.2 中 `run_scene` 的线程 ID 从 `"alice-fresh"` 改成 `"alice-original"`，保持用户仍为 `alice`。先预测草稿读取的状态：它应从预期错误变成成功，后面的 `assert draft_miss.status == "error"` 会停止。看打印出来的 `read_file` 结果核对原因。然后恢复线程 ID、重启内核并从第一格全部运行，四个场景应重新通过。

如果 `memory=` 提示词断言失败，先检查是否预置了对应 Store 文件、路由 key 是否去掉 `/memories/` 前缀，以及是否用了新的线程。下一步可回到 [第 8 章正文](../../content/ch08-long-term-memory.md)了解持久化 Store、更多作用域和记忆整理。重启当前内核即可清理本实验的内存数据。
