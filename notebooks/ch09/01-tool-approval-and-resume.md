> 本次执行模式：**offline**。源码指纹：`94de032adb94`。

# 第 9 章实验：工具审批前，Agent 到底暂停在哪里？

对应[第 9 章正文](../../content/ch09-human-in-the-loop.md)。假设 Agent 准备发送一封上线通知：我们想先检查收件人，必要时修改或拒绝。模型已经提出工具调用，是否意味着邮件已经发送？暂停后如何接着执行？

本实验用只写入内存列表的教学工具回答这些问题，**不会发送真实邮件，也不删除文件**。

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

`AIMessage` 是模型消息，其中的 `tool_calls` 表示“请求调用”，尚不代表工具执行。`ToolMessage` 是工具执行或审批反馈产生的消息；`tool_call_id` 对应请求的 `id`，便于核对两者是否属于同一次调用。

Deep Agent 本身是一张 LangGraph **图（Graph）**，内部的**节点（Node）**负责模型调用、工具执行和中间件逻辑。一次用户请求可以循环经过这些节点：

```text
用户输入 → model：提出工具调用 → after_model：人工审批
                                          ↓ 批准后
用户得到回复 ← model：读取工具结果 ← tools：运行函数
```

**State** 是这条执行流程当前的数据，包括消息等字段。**Checkpointer** 是 LangGraph 的存档组件，保存 State 与恢复所需的执行进度；`thread_id` 是逻辑会话 ID，不是操作系统线程。同一个图可以服务多个会话，恢复时必须用原来的 ID。这里使用 `InMemorySaver`，只在当前内核的内存里保存存档。

## 2. 定义两个可观察的教学工具

`@tool` 把普通 Python 函数的名称、参数和说明提供给 Agent。`send_email` 在这里**只记录参数并返回 JSON**；`ask_user` 是等人工回答的占位工具。如果 `respond` 正确跳过了它，执行记录中就不应有 `ask_user`。

`make_tools(records)` 接收一个空列表。内部函数会继续引用这个列表，所以每个实验可以拥有自己的执行记录，不会混入上一次的结果。JSON 只是把字典变成可核对的文本，不涉及网络。


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

为了比较不同决策，`new_experiment()` 每次创建新的执行列表、模型和 `InMemorySaver`。`planned_calls` 是公开的实验计划：offline 的第一条模型消息提出这些请求，第二条结束；它不会理解工具结果。列表会循环，因此每个独立实验都使用新模型，后面还要核对工具是否真的运行。

live 时，`create_model()` 改用 README 配置的真实模型；同一份任务要求会作为用户输入发给模型，实际请求由模型生成。如果没有按要求提出调用，断言会解释未满足的目标。

`interrupt_on` 按工具名设置策略：邮件仅允许批准、修改或拒绝；问用户的工具仅允许人工回答。`ModelRequestRecorder` 是只读回调：框架每次真正调用模型时，它记录输入消息，用于判断恢复时是否沿用了已有工具请求。


```python
class ModelRequestRecorder(BaseCallbackHandler):
    def __init__(self):
        self.inputs = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.inputs.append(list(messages[0]))


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

`invoke()` 启动一次图执行。本实验沿用正文的 `version="v2"`：`result.value` 是 State，`result.interrupts` 是中断列表。**v2 不是 HITL 的必要条件**；默认接口也支持中断，只是用字典中的 `__interrupt__` 返回中断信息。

下面的函数为各场景复用启动代码。它展示两组审批字段：`action_requests` 是待审的工具及参数，`review_configs` 是各工具允许的决策。`zip()` 按顺序配对展示；后面提交的决策也必须保持这个顺序。

`assert` 在条件不成立时停止实验。这里同时检查实际模型请求、实际中断和空执行记录，防止把预设调用误认为已完成操作。


```python
def start_experiment(experiment):
    requested = [{"name": call["name"], "args": call["args"]}
                 for call in experiment["plan"]]
    instruction = "请执行以下教学工具任务：\n" + json.dumps(requested, ensure_ascii=False)
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


上面应看到 `send_email` 的收件人、主题、正文，以及三种允许决策。执行次数仍是 **0**：模型提出了请求，中间件已暂停，工具函数尚未运行。

### 检查 Checkpoint：暂停在哪个节点？

`get_state(config)` 读取这条会话最新的状态快照。`values` 是 State；`next` 是待继续执行的节点；`interrupts` 是待解决的中断。下面只展示有关字段，避免打印完整提示词。

在锁定版本中，`next` 应指向 `HumanInTheLoopMiddleware.after_model`。模型节点已经结束，待审批的 `AIMessage.tool_calls` 已保存在 State 中。因此恢复审批时，通常复用这条模型结果，不必重新让模型选择同一个工具。


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


## 5. 恢复并核对四种决策

`Command(resume={"decisions": [...]})` 提交人工决定；恢复必须使用原来的 `config`，从而找到同一 `thread_id` 的存档。`decisions` 是按待审批动作顺序排列的列表。

下面的检查函数核对三类证据：

1. 工具实际执行记录是否与预期相同，包含执行次数和参数。
2. 每个待审调用是否只有一个对应结果，且工具名、调用 ID、状态和内容正确。
3. 恢复后的实际模型请求是否包含这些结果，避免把结束回复当作成功证据。

两个 `for` 的列表推导式是在“遍历模型消息，再取出每条消息的工具调用”。结果与请求通过 `tool_call_id` 关联；`edit` 的工具结果会带有人工改参说明；原始消息保留在 `result.value["messages"]` 中。输出用 `json.loads()` 将末行的教学邮件 JSON 还原为字典，核对并逐字段展示实际参数，避免框架说明中的 Unicode 转义干扰阅读。


```python
def check_outcome(experiment, result, expected_records, expected_feedback):
    assert not result.interrupts, "仍有未解决的中断"
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
        print(f"工具结果：{reply.name}；状态：{reply.status}；调用 ID：{reply.tool_call_id}")
        if isinstance(expected, dict):
            if "\nTool response:\n" in reply.text:
                print("框架附有人工改参说明；原始 ToolMessage 保留在 result.value 中。")
            show_text("  工具实际返回的参数：",
                      json.dumps(actual_args, ensure_ascii=False, indent=2))
        else:
            show_text("  返回内容：", reply.text)
    resumed_inputs = experiment["recorder"].inputs[experiment["model_calls_before"]:]
    assert resumed_inputs, "恢复后没有调用模型读取工具结果"
    for model_input in resumed_inputs:
        seen_ids = {message.tool_call_id for message in model_input
                    if isinstance(message, ToolMessage)}
        assert all(call["id"] in seen_ids for call in calls), "恢复重新调用了未含工具结果的模型步骤"
    assert isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls
    assert not experiment["agent"].get_state(experiment["config"]).next
    print("工具实际执行次数：", len(experiment["records"]))
    print("实际模型请求数（暂停前 / 完成后）：",
          experiment["model_calls_before"], "/", len(experiment["recorder"].inputs))
```

### 5.1 approve：按原参数执行

批准当前邮件。预期只新增一条记录，收件人仍为 `all@example.com`；工具结果成功，并对应原始调用 ID。


```python
approved = approve_case["agent"].invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config=approve_case["config"], version="v2",
)
check_outcome(
    approve_case, approved,
    [{"name": "send_email", "args": ORIGINAL_ARGS}],
    [("success", ORIGINAL_ARGS)],
)
```

    工具结果：send_email；状态：success；调用 ID：mail-1
    
      工具实际返回的参数：
    {
      "to": "all@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
    工具实际执行次数： 1
    实际模型请求数（暂停前 / 完成后）： 1 / 2


看执行记录和成功工具结果：原参数执行了一次。offline 下，模型请求数从 **1** 变成 **2**；新增请求已经包含邮件结果，表示这是工具之后的新模型步骤，不是重新生成审批前的请求。

### 5.2 edit：修改收件人再执行

创建独立实验，仍让模型提出原来的收件人。人类把它改为 `team@example.com`，保留主题和正文。`edited_action` 必须提供工具 `name` 与完整的 `args`。

在锁定版本中，消息历史可能保留模型原始请求，框架在真正执行时替换参数。因此要检查**执行记录和工具返回**，不能只看最初那条 `AIMessage`。


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
assert edit_case["records"][0]["args"]["to"] == "team@example.com"
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
    工具结果：send_email；状态：success；调用 ID：mail-1
    框架附有人工改参说明；原始 ToolMessage 保留在 result.value 中。
    
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


预期实际收件人是 `team@example.com`。`{**ORIGINAL_ARGS, "to": ...}` 先展开原字典，再覆盖一个字段；它没有修改原始请求，也没有丢掉主题和正文。

### 5.3 reject：工具不执行，拒绝原因交回模型

拒绝邮件并说明下一步。预期记录仍为空；框架生成 `status="error"` 的反馈，表示该调用没有执行，而不是教学工具抛了 Python 异常。


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
    工具结果：send_email；状态：error；调用 ID：mail-1
    
      返回内容：
    User rejected the tool call for `send_email` with reason:
      用户拒绝发送，请只保留草稿，不要重试发送。
    工具实际执行次数： 0
    实际模型请求数（暂停前 / 完成后）： 1 / 2


### 5.4 respond：人的回答代替占位工具结果

新实验只调用 `ask_user`。我们回答“按季度汇总，排除测试数据”。预期占位函数没有执行，但框架生成成功的 `ToolMessage`，内容就是人的回答。

**respond 不是拒绝。**不想发送邮件应使用 `reject`；`respond` 表示人类代替工具给出结果，适用于本来就需要人回答的问题。


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
    工具结果：ask_user；状态：success；调用 ID：question-1
    
      返回内容：
    按季度汇总，并排除测试数据。
    工具实际执行次数： 0
    实际模型请求数（暂停前 / 完成后）： 1 / 2


## 6. 两项动作：按请求顺序提交决策

当同一条模型消息提出多个需要审批的工具调用，中间件把它们打包进一个中断。本例计划两封教学邮件：先发给 `team@example.com`，再发给 `all@example.com`。对第一个请求批准，对第二个请求拒绝。

`decisions[0]` 对应 `action_requests[0]`，不是按工具名称查找；即使两项都叫 `send_email`，也要保持位置对应。框架校验数量和允许类型，**不会推断你是不是把两个同类型决策写反了**。实际审批界面应保留请求与决策的对应关系。


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
    工具结果：send_email；状态：success；调用 ID：batch-team
    
      工具实际返回的参数：
    {
      "to": "team@example.com",
      "subject": "上线通知",
      "body": "测试与构建已通过，计划明天上线。"
    }
    工具结果：send_email；状态：error；调用 ID：batch-all
    
      返回内容：
    User rejected the tool call for `send_email` with reason:
      只通知项目组，取消全员通知，不要重试。
    工具实际执行次数： 1
    实际模型请求数（暂停前 / 完成后）： 1 / 2


### 错误示例：两项动作只提交一项决定

再创建全新的实验，故意少提交一个决定。预期 `ValueError` 明确指出决策数量不匹配，且工具执行次数仍为 0。这里只捕获该预期错误；其他异常照常暴露，不会伪装成成功。

这是**恢复请求的校验失败**，不是新的人工中断。下面保留失败现场，不继续在这个实验上提交恢复请求。想重新实验时，重启内核并从第一格运行；真实审批程序应在提交前核对数量、顺序和允许类型，并按自身错误处理流程处理失败。


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


## 7. 恢复边界、练习与清理

本次实验观察到：工具请求先进入 State，审批前执行次数为 0；`approve` 保留参数，`edit` 改变实际参数，`reject` 不执行并反馈拒绝，`respond` 不执行占位函数并返回人工回答。

### Checkpoint 能恢复什么？

- Checkpoint 是会话 State 和执行进度的存档，不是整个 Python 进程或调用栈的备份；也不是每个 prompt 结束后才存一次。LangGraph 通常在执行步骤边界保存，具体持久化时机还受运行配置影响。
- `interrupt()` 恢复时会重新进入发生中断的节点或任务，中断之前的普通代码可能重跑。本例审批位于独立的 `after_model` 节点，前面模型节点的结果已保存；新增模型请求是在工具结果到达之后发生的。
- 如果自行把 LLM 调用、外部写操作和 `interrupt()` 放进同一个节点，恢复可能重复这些调用。应拆清执行边界，并为不能重复的业务动作设计幂等性，例如用唯一业务 ID 去重。即使把动作放在审批之后，也不自动保证“恰好执行一次”：动作完成但结果尚未保存时崩溃，恢复仍可能再次执行。
- `InMemorySaver` 在内核退出后丢失数据。本实验验证当前进程中的恢复，不验证跨进程恢复、数据库持久化、并发审批或真实邮件投递。[LangGraph 中断说明](https://docs.langchain.com/oss/python/langgraph/interrupts)与[Checkpointer 文档](https://docs.langchain.com/oss/python/langgraph/checkpointers)有进一步说明。

### 改一个变量再观察

1. 只把 5.2 中 `EDITED_TO` 改为 `"review@example.com"`，先预测实际执行收件人；从第一格重跑。
2. 观察 5.2 的成功工具结果：应出现新地址。随后固定要求 `"team@example.com"` 的断言应失败。这说明批准了修改后的参数，实验的原始业务目标却发生了变化；不能只看成功状态。
3. 恢复 `EDITED_TO = "team@example.com"`，重启内核并全部运行，所有预期检查应重新通过，包括被捕获的数量错误。

### 常见问题与下一步

| 现象 | 检查什么 |
|---|---|
| 没有审批中断 | 是否真的提出了对应工具调用，`interrupt_on` 是否包含工具名 |
| 恢复时缺状态或没有继续 | 是否保留同一个 Agent/Checkpointer，并使用原来的 `thread_id` |
| 决策报错 | 是否与请求数量和顺序一致，决策类型是否在 `allowed_decisions` 中 |
| live 断言失败 | 看实际请求、参数和工具结果；真实模型可能没有遵循实验任务，不能退回 offline 声称通过 |

本实验只分配内存对象，没有启动服务或创建磁盘文件；重启内核即可清理全部存档与执行记录。回到[第 9 章正文](../../content/ch09-human-in-the-loop.md)了解条件审批、子 Agent 配置与自定义中断；章节作者参见[贡献指南](../CONTRIBUTING.md)。
