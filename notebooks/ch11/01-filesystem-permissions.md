> 本次执行模式：**offline**。源码指纹：`1506d3019279`。

# 第 11 章实验：允许写工作区，为什么还会写到别处？

对应[第 11 章正文](../../content/ch11-filesystem-permissions.md)。假设让 Agent 整理笔记：普通笔记可以修改，私有资料不能读取，报告发布前需要人工确认。我们把这些要求写成权限规则，并观察工具实际执行了什么。

本实验只操作自动创建的教学临时目录。`/workspace/notes.txt` 等是 Agent 看到的虚拟路径，映射到这个临时目录内；不使用用户文件，也不把本地目录称为隔离沙箱。

| 实验 | 预期现象 |
|---|---|
| 全局拒绝写入 | 读取成功，覆盖写入被拒绝，原笔记保留 |
| 只写工作区 allow | 工作区外的教学文件仍能写入，因为未匹配默认允许 |
| allow 后追加全局 deny | 工作区写入成功，工作区外写入失败 |
| 交换规则顺序 | 全局 deny 先命中，工作区也不能写 |
| 先保护私有文件 | 私有文件读取失败；把目录 allow 放在前面则会暴露它 |
| 敏感写入 interrupt | 审批前报告未改，approve 后才写入 |

默认 offline 使用公共脚本模型安排工具请求；权限中间件、文件操作和审批恢复都真实执行。预设的结束回复不表示成功，下面用工具消息与实际文件核查结果。live 可以运行同一实验，但模型是否按要求调用工具需由实际结果验证。

## 1. 环境与三个关键概念

只需基础 Python。每份 Notebook 从第一格建立自己的变量；Jupyter / VS Code 的内核是运行这些代码的 Python 进程，不依赖其他章的内核状态。

按[公共 README](../README.md) 安装 Python 3.12 的锁定环境，在仓库根目录终端运行：

```bash
uv sync --project notebooks --locked
uv run --project notebooks --locked python -m course_notebooks.run ch11-filesystem-permissions
```

默认不需要模型 Key、Docker、数据库或 Agent Server。真实模型需按 README 配置根目录未提交的 `.env`，并在命令末尾添加 `--mode live`；交互式内核先执行 `import os`、设置 `os.environ["COURSE_MODE"] = "live"`，再顺序运行。live 可能产生模型费用，失败不会自动退回 offline。

- **Backend（后端）**负责实际读写。本例使用 `FilesystemBackend(root_dir=..., virtual_mode=True)`，把 Agent 的虚拟路径映射到临时目录。
- **工具请求**是模型提出的操作。`AIMessage.tool_calls` 记录工具名、参数与调用 ID；框架执行或拒绝后，用 `ToolMessage` 返回结果，`tool_call_id` 对应原请求。
- **权限规则**在内置文件工具调用 Backend 前检查操作与路径。规则限制这些工具，不会限制 Notebook 自己的 Python 文件读写；我们用 Python 准备、核查教学文件。

```text
模型提出 read_file / write_file 请求
    ↓
权限检查：从第一条规则开始，首条匹配生效
    ├─ allow → Backend 执行 → 工具结果
    ├─ deny → 权限错误，Backend 不执行
    └─ interrupt → 暂停审批 → 人工决定是否执行
没有匹配规则 → 默认允许
```


```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from course_notebooks.model_config import create_model
from course_notebooks.nbtools import show_runtime, show_text
from course_notebooks.testing import ScriptedChatModel

show_runtime()
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


## 2. 准备同一组文件与请求

每次比较都重新准备下面四个文件，避免上一次写入影响下一次结论。`/outside.txt` 只是**工作区外、Backend 根目录内**的教学文件，不是宿主机的任意文件。私有文件里的内容也是公开的教学文本。

`SEED` 保存初始内容；`WRITE_NOTES` 等字典描述待请求的工具。这里仅准备数据，还没有调用 Agent。`write_file` 在锁定版本中可以覆盖已有文件，因此拒绝写入后要核对原内容仍在。


```python
SEED = {
    "/workspace/notes.txt": "原始笔记\n",
    "/workspace/private.txt": "仅用于演示的私有资料\n",
    "/outside.txt": "工作区外的原始内容\n",
    "/review/report.txt": "尚未发布的旧报告\n",
}
READ_NOTES = {"name": "read_file", "args": {"file_path": "/workspace/notes.txt"},
              "id": "read-notes"}
WRITE_NOTES = {"name": "write_file", "args": {
    "file_path": "/workspace/notes.txt", "content": "整理后的笔记\n"},
    "id": "write-notes"}
WRITE_OUTSIDE = {"name": "write_file", "args": {
    "file_path": "/outside.txt", "content": "工作区外被修改了\n"},
    "id": "write-outside"}
READ_PRIVATE = {"name": "read_file", "args": {"file_path": "/workspace/private.txt"},
                "id": "read-private"}
WRITE_REVIEW = {"name": "write_file", "args": {
    "file_path": "/review/report.txt", "content": "经人工确认的新报告\n"},
    "id": "write-review"}
show_text("初始教学文件：", json.dumps(SEED, ensure_ascii=False, indent=2))
```

    
    初始教学文件：
    {
      "/workspace/notes.txt": "原始笔记\n",
      "/workspace/private.txt": "仅用于演示的私有资料\n",
      "/outside.txt": "工作区外的原始内容\n",
      "/review/report.txt": "尚未发布的旧报告\n"
    }


### 用同一套运行步骤比较规则

`make_agent()` 将模型、Backend 和权限组装成可执行的图（Graph），即模型提出请求、工具返回结果的循环。`invoke()` 启动这个循环，返回的 `result["messages"]` 是 Agent State（运行数据）中的消息历史。

每个实验创建新模型。offline 响应列表按 `calls` 依次提出请求，最后给出结束回复；它不会理解权限或根据错误调整任务。live 使用公共 `create_model()` 的模型配置，收到同样的工具名、参数和顺序要求。


```python
def make_agent(backend, rules, calls, checkpointer=None):
    responses = [AIMessage(content="", tool_calls=[call]) for call in calls]
    responses.append(AIMessage(content="本轮结束；请核对工具结果和实际文件。"))
    return create_deep_agent(
        model=create_model(ScriptedChatModel(responses=responses)),
        backend=backend,
        permissions=rules,
        checkpointer=checkpointer,
        system_prompt=(
            "仅按用户给出的顺序调用指定工具，参数原样保留。"
            "不委派、不规划、不调用其他工具。遇到拒绝不要绕过或重试；"
            "继续处理列表中的下一项，处理完毕后结束。"
        ),
    )


def task_input(calls):
    tasks = [{"name": call["name"], "args": call["args"]} for call in calls]
    return {"messages": [("user", "依次请求以下工具：\n" +
                          json.dumps(tasks, ensure_ascii=False, indent=2))]}
```

`check_calls()` 从模型消息中提取实际请求，核对名称、参数、顺序与结果关联，并分行展示返回内容。嵌套推导式先遍历模型消息，再取出各条消息中的工具调用；`zip()` 将请求与结果逐项配对。

`run_case()` 为一次比较创建临时目录，准备文件、调用 Agent、读取文件副本。所有需要目录的操作都在同一个 `with TemporaryDirectory()` 中：正常结束或抛出 Python 异常都会清理。它不判断某项权限应该放行还是拒绝，具体实验的断言负责检查这一点。


```python
def check_calls(messages, planned_calls):
    calls = [call for message in messages if isinstance(message, AIMessage)
             for call in message.tool_calls]
    expected = [{"name": c["name"], "args": c["args"]} for c in planned_calls]
    actual = [{"name": c["name"], "args": c["args"]} for c in calls]
    assert actual == expected, "工具名称、参数或顺序与任务要求不同"
    replies = [m for m in messages if isinstance(m, ToolMessage)]
    assert len(replies) == len(calls), "工具返回数量不符"
    for call, reply in zip(calls, replies):
        assert reply.tool_call_id == call["id"] and reply.name == call["name"]
        print("请求工具：", call["name"])
        show_text("参数：", json.dumps(call["args"], ensure_ascii=False, indent=2))
        print("调用 ID：", reply.tool_call_id, "状态：", reply.status)
        show_text("实际返回：", reply.text)
    assert isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls
    return replies


def run_case(label, rules, calls):
    print("\n===", label, "===")
    with TemporaryDirectory(prefix="course-ch11-") as folder:
        root = Path(folder)
        for virtual_path, text in SEED.items():
            file = root / virtual_path.lstrip("/")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        backend = FilesystemBackend(root_dir=root, virtual_mode=True)
        agent = make_agent(backend, rules, calls)
        result = agent.invoke(task_input(calls), config={"recursion_limit": 24})
        replies = check_calls(result["messages"], calls)
        files = {path: (root / path.lstrip("/")).read_text(encoding="utf-8")
                 for path in SEED}
    assert not root.exists(), "教学目录没有清理"
    print("教学目录已清理；文件内容副本留在 files 中。")
    return {"result": result, "replies": replies, "files": files}
```

`recursion_limit=24` 限制图的执行步数，超过后报错，不是模型费用上限。目录的真实路径不出现在输出中；离开 `with` 后只保留消息和文件内容副本，后面的检查不需要目录继续存在。

## 3. 只读：能读取，不能覆盖写入

规则的 `operations` 指定操作组，`paths` 指定匹配的虚拟路径，`mode` 指定处理方式。下面的 `write` 组覆盖内置的 `write_file`、`edit_file`、`delete`；`/**` 匹配整个文件空间。先读笔记，再尝试覆盖，预期第二个结果是权限错误，原笔记内容不变。


```python
READ_ONLY = [FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")]
readonly_case = run_case("全局只读", READ_ONLY, [READ_NOTES, WRITE_NOTES])
assert [r.status for r in readonly_case["replies"]] == ["success", "error"]
assert "原始笔记" in readonly_case["replies"][0].text
assert "permission denied" in readonly_case["replies"][1].text
assert readonly_case["files"] == SEED, "被拒绝的写入改变了文件"
show_text("拒绝后实际笔记：", readonly_case["files"]["/workspace/notes.txt"])
```

    
    === 全局只读 ===
    请求工具： read_file
    
    参数：
    {
      "file_path": "/workspace/notes.txt"
    }
    调用 ID： read-notes 状态： success
    
    实际返回：
    @@ lines 1-1 of 1 @@
    原始笔记
    请求工具： write_file
    
    参数：
    {
      "file_path": "/workspace/notes.txt",
      "content": "整理后的笔记\n"
    }
    调用 ID： write-notes 状态： error
    
    实际返回：
    Error: permission denied for write on /workspace/notes.txt
    教学目录已清理；文件内容副本留在 files 中。
    
    拒绝后实际笔记：
    原始笔记


读取请求未命中这条 `write` 规则，所以默认允许。写入命中 `deny`，工具结果的 `status` 是 `error`，返回权限错误；应用核查的笔记仍为“原始笔记”。最终结束回复没有参与成功判断。

## 4. allow 工作区为什么不等于白名单？

规则按列表顺序检查，**第一条同时匹配操作与路径的规则生效**。如果没有匹配规则，默认允许。先只配置工作区 `allow`，然后故意请求写 `/outside.txt`：它不匹配工作区，却仍应写入成功。


```python
WORKSPACE_ALLOW = FilesystemPermission(
    operations=["read", "write"], paths=["/workspace/**"], mode="allow",
)
DENY_ALL = FilesystemPermission(
    operations=["read", "write"], paths=["/**"], mode="deny",
)
allow_only_case = run_case("只有工作区 allow", [WORKSPACE_ALLOW], [WRITE_OUTSIDE])
assert allow_only_case["replies"][0].status == "success"
assert allow_only_case["files"]["/outside.txt"] == WRITE_OUTSIDE["args"]["content"]
show_text("工作区外实际内容：", allow_only_case["files"]["/outside.txt"])
```

    
    === 只有工作区 allow ===
    请求工具： write_file
    
    参数：
    {
      "file_path": "/outside.txt",
      "content": "工作区外被修改了\n"
    }
    调用 ID： write-outside 状态： success
    
    实际返回：
    Updated file /outside.txt
    教学目录已清理；文件内容副本留在 files 中。
    
    工作区外实际内容：
    工作区外被修改了


这个结果说明：`allow` 是一条放行规则，本身不会改变其他路径的默认行为。形成工作区白名单，需要在最后追加全局 `deny`。接下来同时请求工作区与工作区外写入，应只有前者成功。


```python
WORKSPACE_ONLY = [WORKSPACE_ALLOW, DENY_ALL]
workspace_case = run_case("工作区 allow + 全局 deny", WORKSPACE_ONLY,
                          [WRITE_NOTES, WRITE_OUTSIDE])
assert [r.status for r in workspace_case["replies"]] == ["success", "error"]
assert workspace_case["files"]["/workspace/notes.txt"] == WRITE_NOTES["args"]["content"]
assert "permission denied" in workspace_case["replies"][1].text
assert workspace_case["files"]["/outside.txt"] == SEED["/outside.txt"]

reversed_case = run_case("交换顺序：全局 deny 在前", [DENY_ALL, WORKSPACE_ALLOW],
                         [WRITE_NOTES])
assert reversed_case["replies"][0].status == "error"
assert "permission denied" in reversed_case["replies"][0].text
assert reversed_case["files"] == SEED
print("已核对：兜底拒绝放在最后；放在最前面会连工作区一起拒绝。")
```

    
    === 工作区 allow + 全局 deny ===
    请求工具： write_file
    
    参数：
    {
      "file_path": "/workspace/notes.txt",
      "content": "整理后的笔记\n"
    }
    调用 ID： write-notes 状态： success
    
    实际返回：
    Updated file /workspace/notes.txt
    请求工具： write_file
    
    参数：
    {
      "file_path": "/outside.txt",
      "content": "工作区外被修改了\n"
    }
    调用 ID： write-outside 状态： error
    
    实际返回：
    Error: permission denied for write on /outside.txt
    教学目录已清理；文件内容副本留在 files 中。
    
    === 交换顺序：全局 deny 在前 ===
    请求工具： write_file
    
    参数：
    {
      "file_path": "/workspace/notes.txt",
      "content": "整理后的笔记\n"
    }
    调用 ID： write-notes 状态： error
    
    实际返回：
    Error: permission denied for write on /workspace/notes.txt
    教学目录已清理；文件内容副本留在 files 中。
    已核对：兜底拒绝放在最后；放在最前面会连工作区一起拒绝。


前一组中，工作区请求先命中 allow；外部请求跳过第一条，命中全局 deny。后一组中，全局 deny 先命中，后面的 allow 根本不会参与这次判断。规则不是全部叠加，也不是自动选择最具体的一条。

## 5. 私有文件的拒绝规则放在哪里？

`/workspace/private.txt` 同时属于工作区和私有文件。要让它受到保护，必须把具体路径的 deny 放在目录 allow **之前**。下面对同一读取请求比较两种顺序；所有读取内容均为教学文本。


```python
PRIVATE_DENY = FilesystemPermission(
    operations=["read", "write"], paths=["/workspace/private.txt"], mode="deny",
)
PROTECTED = [PRIVATE_DENY, WORKSPACE_ALLOW, DENY_ALL]
protected_case = run_case("先拒绝私有文件", PROTECTED, [READ_PRIVATE])
assert protected_case["replies"][0].status == "error"
assert "permission denied" in protected_case["replies"][0].text
assert SEED["/workspace/private.txt"].strip() not in protected_case["replies"][0].text
assert protected_case["files"] == SEED

exposed_case = run_case("先放行整个工作区", [WORKSPACE_ALLOW, PRIVATE_DENY, DENY_ALL],
                        [READ_PRIVATE])
assert exposed_case["replies"][0].status == "success"
assert SEED["/workspace/private.txt"].strip() in exposed_case["replies"][0].text
print("同一个文件，仅改变规则顺序，读取结果就发生了变化。")
```

    
    === 先拒绝私有文件 ===
    请求工具： read_file
    
    参数：
    {
      "file_path": "/workspace/private.txt"
    }
    调用 ID： read-private 状态： error
    
    实际返回：
    Error: permission denied for read on /workspace/private.txt
    教学目录已清理；文件内容副本留在 files 中。
    
    === 先放行整个工作区 ===
    请求工具： read_file
    
    参数：
    {
      "file_path": "/workspace/private.txt"
    }
    调用 ID： read-private 状态： success
    
    实际返回：
    @@ lines 1-1 of 1 @@
    仅用于演示的私有资料
    教学目录已清理；文件内容副本留在 files 中。
    同一个文件，仅改变规则顺序，读取结果就发生了变化。


拒绝结果不包含私有文件正文；错误顺序下，真实返回中能读到它。规则需要按“具体保护路径 → 业务放行目录 → 全局兜底”组织。这些检查证明的是本次工具调用的边界，不是对模型推理质量的评价。

## 6. interrupt：先暂停，批准后写入

对 `/review/**` 的写入使用 `mode="interrupt"`。框架会根据权限规则配置工具审批，本例不另写 `interrupt_on`。

`InMemorySaver` 是内存 Checkpointer，用于保存 Agent 的状态与待恢复执行进度。`thread_id` 标识这条会话；恢复必须使用相同配置。我们用 `version="v2"` 返回接口：`paused.value` 是 State，`paused.interrupts` 是中断列表。它不是暂停在某一行的 Python 调用栈；恢复会重新进入被中断的节点，节点中的其他副作用仍需考虑幂等性。

下一格在同一临时目录生命周期内完成暂停与批准：先检查待审批动作、实际文件未变、尚无写入 ToolMessage；再用 `Command(resume=...)` 提交 approve，核对工具结果与新文件。`get_state(config)` 读取已保存的快照，`next` 表示还有待继续执行的节点。更完整的决策与恢复说明见[第 9 章正文](../../content/ch09-human-in-the-loop.md)。


```python
REVIEW_RULES = [FilesystemPermission(
    operations=["write"], paths=["/review/**"], mode="interrupt",
)]
with TemporaryDirectory(prefix="course-ch11-review-") as folder:
    review_root = Path(folder)
    report_path = review_root / "review" / "report.txt"
    report_path.parent.mkdir()
    report_path.write_text(SEED["/review/report.txt"], encoding="utf-8")
    review_backend = FilesystemBackend(root_dir=review_root, virtual_mode=True)
    reviewer = make_agent(review_backend, REVIEW_RULES, [WRITE_REVIEW], InMemorySaver())
    config = {"configurable": {"thread_id": "ch11-review"}, "recursion_limit": 24}
    paused = reviewer.invoke(task_input([WRITE_REVIEW]), config=config, version="v2")
    assert len(paused.interrupts) == 1, "应出现一组权限审批中断"
    payload = paused.interrupts[0].value
    expected_action = {"name": WRITE_REVIEW["name"], "args": WRITE_REVIEW["args"]}
    actions = [{"name": a["name"], "args": a["args"]} for a in payload["action_requests"]]
    assert actions == [expected_action], "待审批动作不符合本次任务"
    assert len(payload["review_configs"]) == 1
    assert "approve" in payload["review_configs"][0]["allowed_decisions"]
    assert not any(isinstance(m, ToolMessage) for m in paused.value["messages"])
    assert report_path.read_text(encoding="utf-8") == SEED["/review/report.txt"]
    snapshot = reviewer.get_state(config)
    assert snapshot.next and snapshot.interrupts
    show_text("待审批动作：", json.dumps(actions, ensure_ascii=False, indent=2))
    print("已保存待恢复进度；审批前没有执行写入。")
    show_text("审批前实际文件：", report_path.read_text(encoding="utf-8"))

    resumed = reviewer.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config, version="v2",
    )
    assert not resumed.interrupts
    review_replies = check_calls(resumed.value["messages"], [WRITE_REVIEW])
    assert review_replies[0].status == "success"
    published_report = report_path.read_text(encoding="utf-8")
    assert published_report == WRITE_REVIEW["args"]["content"]
    assert not reviewer.get_state(config).next
    show_text("批准后实际文件：", published_report)

assert not review_root.exists(), "审批实验留下了教学目录"
print("审批实验目录已清理。")
```

    
    待审批动作：
    [
      {
        "name": "write_file",
        "args": {
          "file_path": "/review/report.txt",
          "content": "经人工确认的新报告\n"
        }
      }
    ]
    已保存待恢复进度；审批前没有执行写入。
    
    审批前实际文件：
    尚未发布的旧报告
    请求工具： write_file
    
    参数：
    {
      "file_path": "/review/report.txt",
      "content": "经人工确认的新报告\n"
    }
    调用 ID： write-review 状态： success
    
    实际返回：
    Updated file /review/report.txt
    
    批准后实际文件：
    经人工确认的新报告
    审批实验目录已清理。


审批前看到旧报告与待审批写入，没有工具执行结果；approve 后出现关联到 `write-review` 的成功结果，文件变成新报告。这里是 Notebook 代码代表审查方批准，没有图形审批界面。Checkpointer 使用内存，进程退出后存档不再保留；临时文件目录已经删除。

## 7. 练习、边界与常见问题

### 改一条路径再观察

1. 把第 5 节 `PRIVATE_DENY.paths` 中的 `/workspace/private.txt` 改为 `/workspace/other.txt`，先预测原私有文件还能否读取。
2. 重启内核并全部运行。第 5 节“先拒绝私有文件”的请求会跳过不匹配的 deny，命中目录 allow，输出应出现教学私有内容；原本要求 error 的断言会失败。
3. 这表示规则没有覆盖目标路径，不是框架忽略了 deny。该次比较的目录在断言前已经清理。恢复原路径，重启内核并全部运行，实验应再次通过。

### 权限控制的范围

- `FilesystemPermission` 控制内置文件工具；Notebook 的 Python、应用直接调用 Backend、自定义工具、MCP 或 execute 不由这组工具规则统一约束。实际接入其他入口时，需要分别配置控制措施。
- 本例使用无 execute 的 `FilesystemBackend`。锁定版本还会限制权限规则与支持命令执行的 Backend 的组合，不能仅加一条 deny 就声称 Shell 已被保护。
- 本例演示单文件 read_file / write_file，不覆盖目录删除、批量搜索、子 Agent 规则继承或 CompositeBackend 路由；这些属于正文和相关章节的进一步主题。
- 临时目录只提供教学文件管理，不提供进程隔离。普通 Python 异常由 with 清理；强行杀死内核可能留下临时目录，不保证这种情况下的自动回收。
- offline 验证权限与审批机制；live 的工具选择与真实模型质量需要另行验证。

| 现象 | 检查什么 |
|---|---|
| 工作区外仍能写入 | 是否只有 allow、忘了末尾全局 deny |
| 工作区也被拒绝 | 全局 deny 是否排在目录 allow 前面 |
| 私有文件可以读取 | 路径是否匹配，私有 deny 是否先于目录 allow |
| 中断无法恢复 | 是否配置 Checkpointer、是否使用原 thread_id 与 Agent 实例 |
| live 的调用断言失败 | 核对实际工具名、参数和顺序，不以 offline 的结束回复代替证据 |

实验目录已清理，剩余消息与文件内容副本都在内核内存中；重启内核即可释放。回到[第 11 章正文](../../content/ch11-filesystem-permissions.md)了解完整权限策略，贡献时参考[Notebook 制作指南](../CONTRIBUTING.md)。
