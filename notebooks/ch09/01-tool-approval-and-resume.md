> 本次执行模式：**offline**。源码指纹：`efac4ed82069`。

# 第 9 章实验：工具审批前，Agent 到底暂停在哪里？

对应[第 9 章正文](../../content/ch09-human-in-the-loop.md)。假设 Agent 准备发送一封上线通知：我们想先检查收件人，必要时修改或拒绝。模型已经提出工具调用，是否意味着邮件已经发送？暂停后如何接着执行？

这种在执行过程中请人参与决策的方式叫 **Human-in-the-Loop（HITL，人工介入）**。本实验用只写入内存列表的教学工具观察审批流程，**不会发送真实邮件**。

| 场景 | 预期现象 | 核对证据 |
|---|---|---|
| 暂停等待审批 | 有调用请求，工具尚未运行 | `action_requests`、执行记录与 State 快照 |
| `approve` | 按原参数运行一次 | 实际执行参数和成功的 `ToolMessage` |
| `edit` | 按修改后的参数运行一次 | 执行记录中的新收件人和工具返回 |
| `reject` | 工具不运行，模型收到拒绝原因 | 空执行记录和错误状态的反馈 |
| `respond` | 占位工具不运行，人的回答成为结果 | 空执行记录和成功状态的人工回答 |

最后观察两项工具请求的批量审批，以及决策数量不匹配时的真实报错。实验验证框架的审批与恢复机制，不以模型说“完成”作为成功证据。

## 1. 环境与运行模式

只需基础 Python；每份 Notebook 从第一格独立运行。按[公共 README](../README.md) 安装 Python 3.12 的锁定环境，并选择 `notebooks/.venv` 对应的 Jupyter / VS Code 内核。内核是运行代码、保存变量的 Python 进程；不依赖前几章留下的变量。

在仓库根目录的**终端**运行：

```bash
uv sync --project notebooks --locked
uv run --project notebooks --locked python -m course_notebooks.run ch09-human-in-the-loop
```

默认 **offline** 使用脚本模型预先安排工具请求和结束回复；中间件、工具函数、Checkpointer 与恢复过程真实执行。不需要模型 Key、Agent Server、数据库或外部服务。随附输出来自 offline，不证明真实模型能正确选择工具。

切换真实模型时，按 README 配置未提交的根目录 `.env`，在运行命令末尾加 `--mode live`。可能产生模型费用；配置或调用失败会直接报错。交互式运行时，先执行 `import os` 和 `os.environ["COURSE_MODE"] = "live"`，再从下一格开始顺序运行。live 仍使用同一组教学工具和断言，不能将离线结果当作真实模型验证。


```python
import json
from copy import deepcopy

from deepagents import create_deep_agent
from langchain.tools import tool
from langchain_core.callbacks import BaseCallbackHandler
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


### 先认清消息、状态与执行位置

`AIMessage` 是模型消息，其中的 `tool_calls` 表示“请求调用”，尚不代表工具已经执行。执行结果或审批反馈会写成 `ToolMessage`；它的 `tool_call_id` 对应请求的 `id`，用来关联同一次调用的请求与结果。

Deep Agent 本身是一张 LangGraph **图（Graph）**。图里的**节点（Node）**各自执行一步工作，例如调用模型、处理审批或运行工具。以下以批准邮件为例，一次用户请求会经过两个模型步骤：

```text
用户输入
  ↓
model：模型提出邮件工具调用
  ↓
after_model：暂停，等待人工审批
  ↓ 批准后继续
tools：执行邮件工具，记录参数并返回结果
  ↓
model：读取工具结果，给出最终回复
```

**State** 是这条流程当前的数据，本例主要读取其中的消息。**Checkpointer** 是 LangGraph 的存档组件，保存 State 和恢复所需的执行进度；每次保存的快照叫 **Checkpoint（检查点）**。

`thread_id` 标识一条逻辑会话。同一张图可以处理多个会话，恢复时用原来的 ID 找到相应存档；这里的 thread 不是操作系统线程。本例用 `InMemorySaver` 保存快照，数据只存在于当前内核的内存中。

## 2. 定义两个可观察的教学工具

先定义工具，稍后再交给 Agent 使用。`@tool` 把普通 Python 函数包装成 Agent 可调用的工具，并提供函数名称、参数和说明。

- `send_email` **只记录参数并返回 JSON**，便于检查是否执行、执行了几次，以及最终用了哪个收件人。
- `ask_user` 是询问用户的占位工具。后面用 `respond` 提交人的回答，应该跳过这个函数，因此执行记录中不应出现 `ask_user`。

`make_tools(records)` 接收一个空列表，返回上述两个工具。内部函数会继续引用这个列表，每次调用都往其中追加记录；各实验传入各自的列表，记录就不会混在一起。`json.dumps()` 把参数字典转成文本，`ensure_ascii=False` 让中文保持可读。


```python
def make_tools(records):
    @tool
    def send_email(to: str, subject: str, body: str) -> str:
        """记录教学邮件的收件人、主题和正文，不发送真实邮件。"""
        args = {"to": to, "subject": subject, "body": body}
        records.append({"name": "send_email", "args": args})
        return json.dumps(args, ensure_ascii=False)

    @tool
    def ask_user(question: str) -> str:
        """提出需要人类回答的问题；通过 HITL respond 提供真实回答。"""
        records.append({"name": "ask_user", "args": {"question": question}})
        return "占位工具已运行，尚未取得用户回答。"

    return [send_email, ask_user]

ORIGINAL_ARGS = {
    "to": "all@example.com",
    "subject": "上线通知",
    "body": "测试与构建已通过，计划明天上线。",
}
EMAIL_CALL = {"name": "send_email", "args": ORIGINAL_ARGS, "id": "mail-1"}
ASK_CALL = {
    "name": "ask_user", "args": {"question": "报告按月还是按季度汇总？"},
    "id": "question-1",
}
print("教学工具已定义；尚未执行。")
```

    教学工具已定义；尚未执行。


## 3. 组装 Agent，并配置审批策略

本节创建 Agent，暂不发起任务。关键配置是 `interrupt_on`：按工具名指定是否需要审批，以及允许哪几种决定。本例的邮件工具允许 `approve`、`edit`、`reject`；询问工具只允许 `respond`。

后面还要观察模型实际被调用了几次。`ModelRequestRecorder` 是一个回调：每次框架开始调用模型时，自动执行 `on_chat_model_start()`，把输入消息记入 `inputs`。它只观察，不修改模型输入或回复。


```python
class ModelRequestRecorder(BaseCallbackHandler):
    def __init__(self):
        self.inputs = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.inputs.append(list(messages[0]))
```

`new_experiment(planned_calls, thread_id)` 把重复的组装步骤放在一个函数里。输入分别是本次要提出的工具请求和会话 ID；每次调用都创建新的 Agent、执行记录、模型和内存存档，避免不同审批实验互相影响。

默认 offline 下，`ScriptedChatModel` 按 `responses` 列表返回两条预设消息：第一次提出 `planned_calls` 中的工具请求，第二次给出结束回复。它不会理解输入或判断工具结果，所以结束回复不能证明工具成功。这个响应列表会循环，每个独立实验都要使用新模型。

`create_model()` 负责选择运行模式。live 下，任务要求会作为用户输入交给真实模型，工具请求由模型生成；没有满足要求时，后面的断言会报错。`deepcopy()` 复制请求字典，避免一个实验修改另一个实验的数据。

函数返回一个字典，后面按字段取出所需对象：

| 字段 | 本实验中的用途 |
|---|---|
| `agent` | 发起任务、恢复审批、读取状态 |
| `records` | 核对工具实际执行次数与参数 |
| `recorder` | 查看模型实际收到的输入消息 |
| `plan` | 生成本次用户任务，并核对待审批请求 |
| `config` | 保存 `thread_id` 和记录模型输入的回调；启动与恢复共用它 |


```python
def new_experiment(planned_calls, thread_id):
    records = []
    recorder = ModelRequestRecorder()
    model = create_model(ScriptedChatModel(responses=[
        AIMessage(content="", tool_calls=deepcopy(planned_calls)),
        AIMessage(content="本轮结束；请以执行记录和工具结果为准。"),
    ]))
    agent = create_deep_agent(
        model=model,
        tools=make_tools(records),
        checkpointer=InMemorySaver(),
        interrupt_on={
            "send_email": {"allowed_decisions": ["approve", "edit", "reject"]},
            "ask_user": {"allowed_decisions": ["respond"]},
        },
        system_prompt=(
            "只提出用户指定的工具调用，参数原样保留。不要委派或使用其他工具。"
            "若有多项请求，在同一条消息中提出。"
            "收到审批后的工具结果时，总结结果并结束，不要再次调用工具。"
            "教学邮件只记录参数，不是真实邮件服务。"
        ),
    )
    return {
        "agent": agent, "records": records, "recorder": recorder,
        "plan": deepcopy(planned_calls),
        "config": {"configurable": {"thread_id": thread_id},
                   "callbacks": [recorder]},
    }
```

## 4. 启动任务，确认工具还没有执行

`invoke()` 启动一次图执行。本例传入用户消息；遇到审批中断时，它会返回当前结果，让调用方查看并提交决定。

本实验沿用正文的 `version="v2"`：`paused.value` 是 State，`paused.interrupts` 是中断列表。v2 不是 HITL 的必要条件；默认接口也支持中断，只是返回字典，并在 `__interrupt__` 中放中断信息。

`start_experiment()` 为后面的场景复用启动与检查步骤：先把 `plan` 转成用户任务并调用 `invoke()`，再读取中断内容。`action_requests` 列出待审批的工具及参数，`review_configs` 列出相应工具允许的决定；`zip()` 按位置配对展示。后面提交决定时也要保持这个顺序。

`assert` 在条件不成立时停止实验。这里检查待审批请求符合任务要求，且 `records` 仍为空。这样才能确认“模型已提出调用，工具尚未执行”。


```python
def start_experiment(experiment):
    requested = [{"name": call["name"], "args": call["args"]}
                 for call in experiment["plan"]]
    instruction = "请执行以下教学工具任务：\n" + json.dumps(
        requested, ensure_ascii=False, indent=2,
    )
    paused = experiment["agent"].invoke(
        {"messages": [("user", instruction)]},
        config=experiment["config"], version="v2",
    )
    assert len(paused.interrupts) == 1, "应产生一组工具审批中断"
    payload = paused.interrupts[0].value
    actions = payload["action_requests"]
    reviews = payload["review_configs"]
    assert len(actions) == len(reviews) == len(requested)
    actual = [{"name": action["name"], "args": action["args"]} for action in actions]
    assert actual == requested, "待审批工具或参数与本实验要求不同"
    assert experiment["records"] == [], "待审批工具已经运行"
    assert experiment["recorder"].inputs, "没有记录到实际模型请求"
    experiment["calls"] = deepcopy(paused.value["messages"][-1].tool_calls)
    experiment["model_calls_before"] = len(experiment["recorder"].inputs)
    print("线程：", experiment["config"]["configurable"]["thread_id"])
    for index, (action, review) in enumerate(zip(actions, reviews), start=1):
        print(f"待审批动作 {index}：{action['name']}")
        print("  调用 ID：", experiment["calls"][index - 1]["id"])
        show_text("  参数：", json.dumps(action["args"], ensure_ascii=False, indent=2))
        print("  允许决策：", ", ".join(review["allowed_decisions"]))
    print("工具执行次数：", len(experiment["records"]))
    return paused
```

现在创建一封邮件的实验，使用会话 ID `ch09-approve`。`new_experiment()` 完成组装，`start_experiment()` 才真正发起任务；返回值 `paused` 留待下面检查。


```python
approve_case = new_experiment([EMAIL_CALL], "ch09-approve")
paused = start_experiment(approve_case)
```

    线程： ch09-approve
    待审批动作 1：send_email
      调用 ID： mail-1
    
      参数：
    {
      "to": "all@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
      允许决策： approve, edit, reject
    工具执行次数： 0


上面输出了 `send_email` 的收件人、主题、正文，以及允许的三种决定。工具执行次数仍是 **0**：模型提出了请求，中间件已暂停，工具函数尚未运行。

### 检查 Checkpoint：暂停在哪个节点？

`get_state(config)` 读取这条会话最新的快照。下面查看三个字段：`values` 是保存的 State，`next` 是待继续执行的节点，`interrupts` 是待解决的中断。

在锁定版本中，`next` 应指向 `HumanInTheLoopMiddleware.after_model`。我们还要检查最后一条消息：模型提出的邮件请求是否已经保存在 State 中？这决定了恢复时能否沿用已有请求。


```python
snapshot = approve_case["agent"].get_state(approve_case["config"])
assert snapshot.next and snapshot.interrupts, "没有保存待恢复的审批"
assert snapshot.values["messages"][-1].tool_calls == approve_case["calls"]
print("待执行节点：", ", ".join(snapshot.next))
print("待解决中断数：", len(snapshot.interrupts))
print("State 已保存的调用：", snapshot.values["messages"][-1].tool_calls[0]["name"])
print("审批前实际模型请求数：", approve_case["model_calls_before"])
```

    待执行节点： HumanInTheLoopMiddleware.after_model
    待解决中断数： 1
    State 已保存的调用： send_email
    审批前实际模型请求数： 1


上面显示待执行节点是审批中间件，且 State 已保存 `send_email` 请求；审批前模型实际调用了一次。模型步骤已经结束，暂停的是后面的审批步骤。第 5 节会继续检查恢复后模型收到的消息，确认它读取了工具结果，而没有重新生成待审批请求。

## 5. 恢复并核对四种决策

`Command(resume={"decisions": [...]})` 用来提交人工决定。把它作为新的 `invoke()` 输入，并使用原来的 Agent 和 `config`，就能找到同一 `thread_id` 的存档并继续执行。`decisions` 列表要与待审批动作一一对应。

下面的决定直接写在代码中，代表用户已经看过请求并做出选择；本例没有另外搭建审批界面。

### 5.1 approve：按原参数执行

先批准第 4 节暂停的邮件任务。预期 `send_email` 按原参数执行一次，收件人仍是 `all@example.com`；工具返回结果后，模型给出结束回复。


```python
approved = approve_case["agent"].invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config=approve_case["config"], version="v2",
)
```

恢复结果保存在 `approved` 中。它包含完整消息历史，可以通过 `approved.value["messages"]` 查看；但最后一条模型回复不能单独证明邮件工具运行成功。

为四种决定复用同一套检查，下面定义 `check_outcome()`。它只读取结果、核对并打印，不发起任务或调用工具。调用时提供两组预期值：

- `expected_records`：工具应实际执行哪些操作；空列表表示不应执行工具。
- `expected_feedback`：模型应收到什么反馈，每项是 `(状态, 内容)`，按原工具请求顺序排列。

函数依次检查执行记录、工具结果和恢复后的模型输入。工具结果通过 `tool_call_id` 对应原请求；嵌套列表推导式则先遍历模型消息，再取出各条消息中的 `tool_calls`。邮件结果中的末行 JSON 用 `json.loads()` 还原成字典，打印时展开字段并保留中文；人工修改参数的原始说明仍保存在消息历史中。


```python
def check_outcome(experiment, result, expected_records, expected_feedback):
    assert not result.interrupts, "仍有未解决的中断"
    # 先看工具真正做了什么，再看返回给模型的消息。
    assert experiment["records"] == expected_records, "执行次数或实际参数不符"
    messages = result.value["messages"]
    calls = [call for message in messages if isinstance(message, AIMessage)
             for call in message.tool_calls]
    assert calls == experiment["calls"], "恢复后出现额外或改变的工具请求"
    assert len(expected_feedback) == len(calls)
    replies = [message for message in messages if isinstance(message, ToolMessage)]
    assert len(replies) == len(calls), "工具结果数量不符"
    for call, (status, expected) in zip(calls, expected_feedback):
        matched = [reply for reply in replies if reply.tool_call_id == call["id"]]
        assert len(matched) == 1, "工具结果没有唯一对应到原调用"
        reply = matched[0]
        assert reply.name == call["name"] and reply.status == status
        if isinstance(expected, dict):
            actual_args = json.loads(reply.text.splitlines()[-1])
            assert actual_args == expected, "工具返回没有反映实际参数"
        elif status == "error":
            assert expected in reply.text, "拒绝原因没有反馈给模型"
        else:
            assert reply.text == expected, "人工回答没有原样成为工具结果"
        print("工具结果：", reply.name)
        print("  状态：", reply.status)
        print("  调用 ID：", reply.tool_call_id)
        if isinstance(expected, dict):
            if "\nTool response:\n" in reply.text:
                print("框架附有人工修改参数的说明；下面展开实际执行参数。")
            show_text("  工具实际返回的参数：",
                      json.dumps(actual_args, ensure_ascii=False, indent=2))
        else:
            show_text("  返回内容：", reply.text)
    # 只检查恢复后的模型调用，它们应已收到这批工具结果。
    resumed_inputs = experiment["recorder"].inputs[experiment["model_calls_before"]:]
    assert resumed_inputs, "恢复后没有调用模型读取工具结果"
    for model_input in resumed_inputs:
        seen_ids = {message.tool_call_id for message in model_input
                    if isinstance(message, ToolMessage)}
        assert all(call["id"] in seen_ids for call in calls), (
            "恢复后的模型输入缺少工具结果，可能重跑了审批前的模型步骤"
        )
    assert isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls
    assert not experiment["agent"].get_state(experiment["config"]).next
    print("工具实际执行次数：", len(experiment["records"]))
    print("实际模型请求数（暂停前 / 完成后）：",
          experiment["model_calls_before"], "/", len(experiment["recorder"].inputs))
```


```python
check_outcome(
    approve_case, approved,
    [{"name": "send_email", "args": ORIGINAL_ARGS}],
    [("success", ORIGINAL_ARGS)],
)
```

    工具结果： send_email
      状态： success
      调用 ID： mail-1
    
      工具实际返回的参数：
    {
      "to": "all@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
    工具实际执行次数： 1
    实际模型请求数（暂停前 / 完成后）： 1 / 2


执行记录和成功的工具结果都显示：原参数执行了一次。offline 下，模型请求数从 **1** 变成 **2**；第二次请求已包含邮件结果，是工具执行之后的新模型步骤。审批前生成工具请求的模型步骤没有重跑。

### 5.2 edit：修改收件人再执行

创建独立实验，仍让模型提出原来的收件人。人类把它改为 `team@example.com`，保留主题和正文。`edited_action` 必须提供工具 `name` 与完整的 `args`。

`{**ORIGINAL_ARGS, "to": EDITED_TO}` 先复制原字典中的字段，再覆盖收件人；原始请求、主题和正文保持不变。在锁定版本中，消息历史仍保留模型原始请求，真正执行时才使用修改后的参数。因此要查看执行记录和工具返回，核对实际收件人。


```python
edit_case = new_experiment([EMAIL_CALL], "ch09-edit")
start_experiment(edit_case)
EDITED_TO = "team@example.com"
edited_args = {**ORIGINAL_ARGS, "to": EDITED_TO}
edited = edit_case["agent"].invoke(
    Command(resume={"decisions": [{
        "type": "edit",
        "edited_action": {"name": "send_email", "args": edited_args},
    }]}),
    config=edit_case["config"], version="v2",
)
check_outcome(
    edit_case, edited,
    [{"name": "send_email", "args": edited_args}],
    [("success", edited_args)],
)
assert edit_case["records"][0]["args"]["to"] == "team@example.com", (
    "教学目标要求通知项目组 team@example.com，实际收件人已改变"
)
print("原请求收件人：", ORIGINAL_ARGS["to"])
print("实际执行收件人：", edit_case["records"][0]["args"]["to"])
```

    线程： ch09-edit
    待审批动作 1：send_email
      调用 ID： mail-1
    
      参数：
    {
      "to": "all@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
      允许决策： approve, edit, reject
    工具执行次数： 0
    工具结果： send_email
      状态： success
      调用 ID： mail-1
    框架附有人工修改参数的说明；下面展开实际执行参数。
    
      工具实际返回的参数：
    {
      "to": "team@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
    工具实际执行次数： 1
    实际模型请求数（暂停前 / 完成后）： 1 / 2
    原请求收件人： all@example.com
    实际执行收件人： team@example.com


输出最后两行分别是原请求收件人 `all@example.com` 和实际执行收件人 `team@example.com`。成功的工具结果也返回了新地址，说明修改影响了工具执行，而不只是改了展示文本。

### 5.3 reject：工具不执行，拒绝原因交回模型

创建新实验并拒绝发送。`message` 写明拒绝原因和希望模型接下来怎么做。预期 `records` 仍为空，框架把拒绝原因写入 `status="error"` 的 `ToolMessage`。


```python
reject_case = new_experiment([EMAIL_CALL], "ch09-reject")
start_experiment(reject_case)
REJECT_REASON = "用户拒绝发送，请只保留草稿，不要重试发送。"
rejected = reject_case["agent"].invoke(
    Command(resume={"decisions": [{"type": "reject", "message": REJECT_REASON}]}),
    config=reject_case["config"], version="v2",
)
check_outcome(reject_case, rejected, [], [("error", REJECT_REASON)])
```

    线程： ch09-reject
    待审批动作 1：send_email
      调用 ID： mail-1
    
      参数：
    {
      "to": "all@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
      允许决策： approve, edit, reject
    工具执行次数： 0
    工具结果： send_email
      状态： error
      调用 ID： mail-1
    
      返回内容：
    User rejected the tool call for `send_email` with reason:
      用户拒绝发送，请只保留草稿，不要重试发送。
    工具实际执行次数： 0
    实际模型请求数（暂停前 / 完成后）： 1 / 2


输出中的执行次数是 **0**，返回内容包含 `REJECT_REASON`。这里的 `error` 表示调用被拒绝；工具没有运行，也没有抛出 Python 异常。拒绝原因已进入恢复后的模型输入。本例只检查这条反馈，不创建或保存邮件草稿。

### 5.4 respond：人的回答代替占位工具结果

新实验只提出 `ask_user` 请求。用 `respond` 回答“按季度汇总，并排除测试数据”，预期占位函数不执行，但模型收到成功的 `ToolMessage`，内容就是人的回答。

`respond` 用于人直接提供工具结果。不想发送邮件时应使用 `reject`；本例也只为 `ask_user` 允许 `respond`。


```python
respond_case = new_experiment([ASK_CALL], "ch09-respond")
start_experiment(respond_case)
HUMAN_ANSWER = "按季度汇总，并排除测试数据。"
responded = respond_case["agent"].invoke(
    Command(resume={"decisions": [{"type": "respond", "message": HUMAN_ANSWER}]}),
    config=respond_case["config"], version="v2",
)
check_outcome(respond_case, responded, [], [("success", HUMAN_ANSWER)])
```

    线程： ch09-respond
    待审批动作 1：ask_user
      调用 ID： question-1
    
      参数：
    {
      "question": "报告按月还是按季度汇总？"
    }
      允许决策： respond
    工具执行次数： 0
    工具结果： ask_user
      状态： success
      调用 ID： question-1
    
      返回内容：
    按季度汇总，并排除测试数据。
    工具实际执行次数： 0
    实际模型请求数（暂停前 / 完成后）： 1 / 2


输出中工具执行次数仍是 **0**，工具结果却是 `success`，并原样包含 `HUMAN_ANSWER`。这是人工回答成为了结果，不表示占位函数运行成功；恢复后的模型已收到这条回答。

## 6. 两项动作：按请求顺序提交决策

当同一条模型消息提出多个需要审批的工具调用，中间件把它们打包进一个中断。本例先请求给 `team@example.com` 发邮件，再请求给 `all@example.com` 发邮件；我们批准第一项、拒绝第二项。

`decisions[0]` 对应 `action_requests[0]`，按位置配对，不按工具名查找。框架会检查决策数量和允许类型；本例两项都叫 `send_email`，都允许批准或拒绝，即使把两个决定写反也不会因此报错。所以要保留请求顺序，确认每个决定属于哪项动作。


```python
BATCH_CALLS = [
    {"name": "send_email", "args": {**ORIGINAL_ARGS, "to": "team@example.com"},
     "id": "batch-team"},
    {"name": "send_email", "args": ORIGINAL_ARGS, "id": "batch-all"},
]
batch_case = new_experiment(BATCH_CALLS, "ch09-batch")
start_experiment(batch_case)
BATCH_REASON = "只通知项目组，取消全员通知，不要重试。"
batch_result = batch_case["agent"].invoke(
    Command(resume={"decisions": [
        {"type": "approve"},
        {"type": "reject", "message": BATCH_REASON},
    ]}),
    config=batch_case["config"], version="v2",
)
check_outcome(
    batch_case, batch_result,
    [{"name": "send_email", "args": BATCH_CALLS[0]["args"]}],
    [("success", BATCH_CALLS[0]["args"]), ("error", BATCH_REASON)],
)
```

    线程： ch09-batch
    待审批动作 1：send_email
      调用 ID： batch-team
    
      参数：
    {
      "to": "team@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
      允许决策： approve, edit, reject
    待审批动作 2：send_email
      调用 ID： batch-all
    
      参数：
    {
      "to": "all@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
      允许决策： approve, edit, reject
    工具执行次数： 0


    工具结果： send_email
      状态： success
      调用 ID： batch-team
    
      工具实际返回的参数：
    {
      "to": "team@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
    工具结果： send_email
      状态： error
      调用 ID： batch-all
    
      返回内容：
    User rejected the tool call for `send_email` with reason:
      只通知项目组，取消全员通知，不要重试。
    工具实际执行次数： 1
    实际模型请求数（暂停前 / 完成后）： 1 / 2


输出中 `batch-team` 对应成功结果，`batch-all` 对应拒绝反馈；工具实际执行次数是 **1**，唯一的执行记录指向项目组地址。这样既核对了两个结果，也确认只执行了批准的那一项。

### 错误示例：两项动作只提交一项决定

再创建独立实验，故意少提交一个决定。预期 `ValueError` 指出决策数量不匹配，且工具执行次数仍为 0。这里只捕获该预期错误；其他异常照常报错。

这次 `invoke()` 会因恢复输入不合法而失败。它没有完成任务，也没有返回一次新的审批中断；下面不继续恢复这条失败的会话。要重复本实验，可重启内核并从第一格运行。实际审批程序应在提交前核对请求与决定的数量、顺序和允许类型。


```python
invalid_case = new_experiment(BATCH_CALLS, "ch09-invalid-count")
start_experiment(invalid_case)
try:
    invalid_case["agent"].invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=invalid_case["config"], version="v2",
    )
except ValueError as error:
    assert "does not match" in str(error), "出现了其他 ValueError"
    show_text("预期的数量错误：", str(error))
else:
    raise AssertionError("缺少一项决策时应拒绝恢复")
assert invalid_case["records"] == [], "错误决策导致了工具执行"
print("校验失败后的工具执行次数：", len(invalid_case["records"]))
```

    线程： ch09-invalid-count
    待审批动作 1：send_email
      调用 ID： batch-team
    
      参数：
    {
      "to": "team@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
      允许决策： approve, edit, reject
    待审批动作 2：send_email
      调用 ID： batch-all
    
      参数：
    {
      "to": "all@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
      允许决策： approve, edit, reject
    工具执行次数： 0
    
    预期的数量错误：
    Number of human decisions (1) does not match number of hanging tool calls
      (2).
    校验失败后的工具执行次数： 0


错误信息中的 `(1)` 和 `(2)` 分别表示提交的决定数与待审批调用数。工具执行次数为 **0**，说明数量校验失败时尚未执行邮件工具。

## 7. 恢复边界、练习与清理

本次实验观察到：工具请求先进入 State，审批前执行次数为 0；`approve` 保留参数，`edit` 改变实际参数，`reject` 跳过调用并反馈拒绝原因，`respond` 跳过占位函数并返回人工回答。

### Checkpoint 能恢复什么？

Checkpoint 保存会话的 State 和执行进度，不能备份整个 Python 进程或函数调用栈。它也不限于每个 prompt 结束后保存一次：LangGraph 通常在图的执行步骤之间保存快照，具体写入时机还受运行配置影响。

恢复 `interrupt()` 时，LangGraph 会重新执行发生中断的节点（或包含中断的任务）。中断之前的普通代码可能再运行一次。对照本例的三个步骤更容易理解：

| 步骤 | 本例恢复时发生什么 |
|---|---|
| 审批前的模型步骤 | 已结束，工具请求保存在 State 中，沿用已有结果 |
| `after_model` 审批步骤 | 重新进入，读取 `Command` 中的决定并处理审批 |
| 工具之后的模型步骤 | 收到工具结果后新执行一次，用于给出最终回复 |

如果你在同一个节点里先调用 LLM 或写外部数据，再调用 `interrupt()`，恢复可能重复前面的调用。可以把审批前的工作拆成独立节点；对不能重复的外部动作还要设计**幂等性**，也就是同一业务请求重复执行时，不产生重复效果，例如用唯一业务 ID 防止重复发送。

把外部动作放在审批之后也不自动保证只执行一次：若邮件已经发送，程序却在保存执行结果前崩溃，恢复时仍可能再次发送。Checkpointer 本身无法消除这种重复。

`InMemorySaver` 的数据随内核退出而丢失。本实验只验证当前进程中的审批恢复；跨进程恢复、数据库持久化、并发审批和真实邮件投递均未验证。进一步说明见 [LangGraph 中断文档](https://docs.langchain.com/oss/python/langgraph/interrupts)与 [Checkpointer 文档](https://docs.langchain.com/oss/python/langgraph/checkpointers)。

### 改一个变量再观察

1. 只把 5.2 中 `EDITED_TO` 改为 `"review@example.com"`，先预测实际收件人，再重启内核并从第一格运行。
2. 观察 5.2 的工具结果：应出现新地址，但随后固定要求 `"team@example.com"` 的断言会失败。这是“工具按新参数执行成功，却不再满足原收件人要求”的区别。
3. 恢复 `EDITED_TO = "team@example.com"`，重启内核并全部运行。各项检查应通过；第 6 节的数量错误仍会出现，并由代码按预期捕获。

### 常见问题与下一步

| 现象 | 检查什么 |
|---|---|
| 没有审批中断 | 模型是否真的提出了对应工具调用，`interrupt_on` 是否包含工具名 |
| 恢复时缺状态或没有继续 | 是否保留同一个 Agent 和 Checkpointer，并使用原来的 `thread_id` |
| 决策报错 | 数量是否匹配、类型是否允许；再按原请求顺序核对每项决定，以免选错动作 |
| live 断言失败 | 查看实际请求、参数和工具结果；真实模型可能没有遵循任务要求，不能用 offline 结果替代 |

本实验只使用内存对象，没有启动服务或创建磁盘文件；重启内核即可清理存档与执行记录。回到[第 9 章正文](../../content/ch09-human-in-the-loop.md)了解条件审批、子 Agent 配置与自定义中断；章节作者参见[贡献指南](../CONTRIBUTING.md)。
