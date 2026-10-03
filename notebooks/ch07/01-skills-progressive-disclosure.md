> 本次执行模式：**offline**。源码指纹：`116d592ca8c8`。

# 第 7 章实验：Skill 的说明何时进入模型上下文？

对应[第 7 章正文](../../content/ch07-skills.md)。假设我们给 Agent 一份“发布前检查”技能：`SKILL.md` 写使用步骤，`references/checks.md` 写两条具体检查项。Agent 刚启动时，会一次看到这两份文件的全部内容吗？

本实验按一次任务的时间顺序观察：

| 时刻 | 预期进入模型请求的内容 | 怎么证明 |
|---|---|---|
| 刚收到用户任务 | 技能名称、用途和 `SKILL.md` 路径 | 记录第一次实际模型请求 |
| Agent 读取 `SKILL.md` 后 | 技能正文，包括参考文件路径 | 核对 `read_file` 的调用与返回、下一次模型请求 |
| Agent 再读取参考文件后 | “单元测试通过”等具体检查项 | 核对第二次 `read_file` 的返回、后续模型请求 |

最后删除参考文件再执行一次，观察读取失败时工具怎样报告错误。**这里要验证的是 Deep Agents 的加载与工具循环**；默认脚本模型按公开规则发出读取请求，它本身没有判断何时需要某个 Skill 的能力。

## 1. 环境与运行模式

本章可独立从第一格执行，只需要基础 Python。沿用[公共 README](../README.md) 的 Python 3.12、锁文件和模型配置，不依赖前两章的内核状态，也不需要 Agent Server。

在仓库根目录运行：

```bash
uv sync --project notebooks --locked
uv run --project notebooks --locked python -m course_notebooks.run ch07-skills
```

默认 `offline` 用脚本模型规定读取顺序，Skills 中间件、文件工具和消息循环真实执行。随附输出来自 offline，不代表真实模型的选工具能力。

要调用真实模型，按 README 配置根目录 `.env`，在命令末尾添加 `--mode live`；可能产生模型费用，配置或调用失败会直接报错。交互式运行时，先执行 `import os` 和 `os.environ["COURSE_MODE"] = "live"`，再从下一格开始顺序运行。


```python
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain.agents.middleware import wrap_model_call
from langchain_core.messages import AIMessage, ToolMessage

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


## 2. 准备一个最小技能包

Skill 是一个目录。这里的 `SKILL.md` 分成两段：`---` 包围的 **frontmatter** 声明名字和用途；下面的 Markdown 正文才是具体步骤。正文指向另一份检查清单：

```text
临时目录（运行时自动创建并清理）
└── skills/
    └── release-check/
        ├── SKILL.md                  ← 名称、用途、使用步骤
        └── references/checks.md      ← 两条发布检查项
```

我们用两句**正常的业务文字**作观察线索：“只按参考清单列出检查项”只出现在 `SKILL.md` 正文，“单元测试通过”只出现在参考资料里。第一次模型请求若出现它们，就表示内容提前进入了上下文。变量 `BODY_MARKER`、`REFERENCE_MARKER` 只是下面断言用的短名字，并非 Skills 的特殊语法；检查项也没有需要记忆的编号。

下一格只定义文本并打印给**读者**看；此时还没创建 Agent，也没有把文件内容送给模型。


```python
SKILL_PATH = "/skills/release-check/SKILL.md"
REFERENCE_PATH = "/skills/release-check/references/checks.md"
DESCRIPTION = "当用户需要发布前检查清单时，读取本地资料并列出检查项。"
BODY_MARKER = "只按参考清单列出检查项"
REFERENCE_MARKER = "单元测试通过"
SECOND_CHECK = "构建产物中没有调试日志"

SKILL_TEXT = f"""---
name: release-check
description: {DESCRIPTION}
---
# 发布检查技能
1. 使用 read_file 读取 `{REFERENCE_PATH}`。
2. {BODY_MARKER}，不要添加资料中没有的要求。
3. 如果读取失败，报告缺失路径并停止，不要猜测检查项。
"""
REFERENCE_TEXT = f"""# 发布前检查清单
- {REFERENCE_MARKER}
- {SECOND_CHECK}
"""

show_text("SKILL.md（此时只是展示给读者）", SKILL_TEXT)
show_text("references/checks.md（此时只是展示给读者）", REFERENCE_TEXT)
```

    
    SKILL.md（此时只是展示给读者）
    ---
    name: release-check
    description: 当用户需要发布前检查清单时，读取本地资料并列出检查项。
    ---
    # 发布检查技能
    1. 使用 read_file 读取 `/skills/release-check/references/checks.md`。
    2. 只按参考清单列出检查项，不要添加资料中没有的要求。
    3. 如果读取失败，报告缺失路径并停止，不要猜测检查项。
    
    references/checks.md（此时只是展示给读者）
    # 发布前检查清单
    - 单元测试通过
    - 构建产物中没有调试日志


## 3. 脚本模型只提出下一步，文件工具真正执行

默认 offline 模式需要一个可复现的“模型回复”。`scripted_reply(messages, tool_names)` 在每次模型请求时运行：它看当前消息里已有多少个 `ToolMessage`（工具返回），然后产生下一条 `AIMessage`。其中的 `tool_calls` 表示**请求**调用工具，不是脚本模型自己读取了文件。

```text
第一次模型回复：请求 read_file(SKILL.md)
        ↓ Deep Agents 执行文件工具，产生第一个 ToolMessage
第二次模型回复：从刚收到的正文里找出参考文件路径，请求 read_file(checks.md)
        ↓ Deep Agents 再执行文件工具，产生第二个 ToolMessage
第三次模型回复：根据第二个工具结果给出结束消息
```

下一格中的正则表达式 `re.search(...)` 只做一件事：从**实际返回的** `SKILL.md` 文本里取出反引号包住的参考文件路径。若文件返回错误，就停止，不再请求资料。切换到 live 模式后 `create_model()` 使用真实模型，这段脚本不会决定工具调用。


```python
def scripted_reply(messages, tool_names):
    assert "read_file" in tool_names
    results = [message for message in messages if isinstance(message, ToolMessage)]
    if not results:
        path = SKILL_PATH  # 第一轮：先请求技能正文
    elif results[-1].status == "error":
        return AIMessage(content="资料读取失败，停止处理：\n" + results[-1].text)
    elif len(results) == 1:
        # 第二轮：从实际工具返回的 SKILL.md 中提取参考文件路径。
        match = re.search(r"`(/skills/[^`]+/references/[^`]+)`", results[-1].text)
        assert match, "技能正文没有给出资料路径"
        path = match.group(1)
    else:
        # 第三轮：把实际读到的清单放进结束消息。
        return AIMessage(content="读取到的检查清单：\n" + results[-1].text)
    return AIMessage(content="", tool_calls=[{
        "name": "read_file", "args": {"file_path": path},
        "id": f"read-{len(results) + 1}",
    }])
```

## 4. 创建 Agent，并记录每次真正发给模型的请求

`FilesystemBackend(root_dir=..., virtual_mode=True)` 让 Agent 使用 `/skills/...` 虚拟路径，对应临时目录中的文件。`skills=["/skills/"]` 给的是**技能目录的父目录**，让 Skills 中间件发现 `release-check`。中间件会扫描文件并把技能名称、用途和路径加入提示词；它读取磁盘以完成扫描，不等于把整份正文都放进模型上下文。

`@wrap_model_call` 把一个 Python 函数注册为模型调用前后的中间件。本例只用它观察输入，不更改请求。`run_agent(root)` 分三步：

1. `observe_request` 在每次模型调用前抄下当时的提示词、消息文本和已有工具返回 ID，然后把请求原样交给下一层；它只观察，不生成回复。
2. `create_deep_agent(...)` 组装后端、Skills 中间件和模型。
3. `invoke(...)` 送入用户任务。框架反复调用模型与 `read_file`，直到模型不再请求工具。`recursion_limit=12` 给循环设置上限。

记录的 `requests` 是**模型在各时刻实际收到的内容**；`result["messages"]` 则保存用户消息、模型提出的工具请求和工具执行后的返回。后面会用两者核对披露顺序。


```python
def run_agent(root):
    requests = []

    @wrap_model_call
    def observe_request(request, handler):
        system = request.system_message.text if request.system_message else ""
        requests.append({
            "system": system,
            "context": "\n".join([system, *(m.text for m in request.messages)]),
            "tool_ids": {m.tool_call_id for m in request.messages
                         if isinstance(m, ToolMessage)},
        })
        return handler(request)

    agent = create_deep_agent(
        model=create_model(ScriptedChatModel(responder=scripted_reply)),
        backend=FilesystemBackend(root_dir=str(root), virtual_mode=True),
        skills=["/skills/"],
        middleware=[observe_request],
        system_prompt="用中文完成本地技能任务；不要联网、委派或写文件。",
    )
    result = agent.invoke({"messages": [{
        "role": "user",
        "content": "请使用 release-check 技能列出发布前检查项。"
                   "先读取技能正文，再读取它指定的资料。"
                   "资料缺失时报告路径并停止，不要猜测。",
    }]}, config={"recursion_limit": 12})
    return result, requests
```

## 5. 执行“资料存在”和“资料缺失”两个场景

下面先在临时目录写出两份文件，运行一次任务；随后**只删除参考清单**，用新的 Agent 和空对话重跑同一任务。这样失败场景不会借用上一轮已经读到的清单。

`show_reads` 按调用 ID 把 `AIMessage.tool_calls` 与 `ToolMessage` 配对，打印每次读取的路径、状态和返回文本。`with TemporaryDirectory()` 管理整个生命周期：离开代码块时会清理目录，即使中途出错也一样。这里的最终答复用纯文本打印，清单标题不会变成 Notebook 的章节标题。


```python
def show_reads(label, result):
    print(f"\n=== {label} ===")
    calls = {c["id"]: c for m in result["messages"]
             if isinstance(m, AIMessage) for c in m.tool_calls}
    for message in result["messages"]:
        if isinstance(message, ToolMessage):
            call = calls[message.tool_call_id]
            print(f"read_file({call['args']['file_path']}) "
                  f"[id={message.tool_call_id}] → {message.status}")
            show_text("工具返回：", message.text, width=78)
    show_text("最终答复：", result["messages"][-1].text)


with TemporaryDirectory(prefix="ch07-skills-") as directory:
    root = Path(directory)
    skill_file = root / SKILL_PATH.lstrip("/")
    reference_file = root / REFERENCE_PATH.lstrip("/")
    reference_file.parent.mkdir(parents=True)
    skill_file.write_text(SKILL_TEXT, encoding="utf-8")
    reference_file.write_text(REFERENCE_TEXT, encoding="utf-8")

    success, success_requests = run_agent(root)
    show_reads("资料存在", success)

    reference_file.unlink()
    missing, missing_requests = run_agent(root)
    show_reads("资料缺失", missing)

assert not root.exists(), "临时目录未清理"
print("\n临时技能目录已清理。")
```

    
    === 资料存在 ===
    read_file(/skills/release-check/SKILL.md) [id=read-1] → success
    
    工具返回：
    @@ lines 1-8 of 8 @@
    ---
    name: release-check
    description: 当用户需要发布前检查清单时，读取本地资料并列出检查项。
    ---
    # 发布检查技能
    1. 使用 read_file 读取 `/skills/release-check/references/checks.md`。
    2. 只按参考清单列出检查项，不要添加资料中没有的要求。
    3. 如果读取失败，报告缺失路径并停止，不要猜测检查项。
    read_file(/skills/release-check/references/checks.md) [id=read-2] → success
    
    工具返回：
    @@ lines 1-3 of 3 @@
    # 发布前检查清单
    - 单元测试通过
    - 构建产物中没有调试日志
    
    最终答复：
    读取到的检查清单：
    @@ lines 1-3 of 3 @@
    # 发布前检查清单
    - 单元测试通过
    - 构建产物中没有调试日志
    
    === 资料缺失 ===
    read_file(/skills/release-check/SKILL.md) [id=read-1] → success
    
    工具返回：
    @@ lines 1-8 of 8 @@
    ---
    name: release-check
    description: 当用户需要发布前检查清单时，读取本地资料并列出检查项。
    ---
    # 发布检查技能
    1. 使用 read_file 读取 `/skills/release-check/references/checks.md`。
    2. 只按参考清单列出检查项，不要添加资料中没有的要求。
    3. 如果读取失败，报告缺失路径并停止，不要猜测检查项。
    read_file(/skills/release-check/references/checks.md) [id=read-2] → error
    
    工具返回：
    Error: File '/skills/release-check/references/checks.md' not found
    
    最终答复：
    资料读取失败，停止处理：
    Error: File '/skills/release-check/references/checks.md' not found
    
    临时技能目录已清理。


## 6. 检查证据：文件先被读取，内容才进入请求

先用 `read_pairs` 把每次 `read_file` 请求与**同一调用 ID**的工具返回配对。若工具没返回、返回找错请求或工具名不一致，就不能据此判断文件是否读取成功。

下一格 `check_disclosure` 会按顺序检查四件事：

1. 第一次模型请求里有技能的**名称、用途、路径**，但没有正文句子和具体检查项。
2. 第一个 `read_file` 成功返回 `SKILL.md`；只有从下一次模型请求起，正文句子才出现。
3. 第二个 `read_file` 读取参考清单；只有它成功返回后，具体检查项才出现。
4. 删除参考文件的场景得到真实 `error`，最终答复包含缺失路径，并且没有复用上一次的检查项。

这些检查比“最终答复看起来正确”更强，因为最终答复可能来自脚本的预设文字。下面的循环与 `assert` 只是将这四个可观察条件写成自动检查。


```python
def read_pairs(result):
    calls = {}
    pairs = []
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                assert call["id"] not in calls, "未返回的工具调用 ID 重复"
                calls[call["id"]] = call
        elif isinstance(message, ToolMessage):
            assert message.tool_call_id in calls, "工具返回没有对应调用"
            call = calls.pop(message.tool_call_id)
            assert message.name == call["name"], "工具名称不匹配"
            if call["name"] == "read_file":
                pairs.append((call, message))
    assert not calls, "工具调用缺少返回"
    return pairs
```

`check_disclosure` 同时用于两次运行。`resource_exists=True` 表示资料存在；`False` 表示预期读取失败。函数先检查两种场景共有的前两阶段，再分别检查成功内容或错误反馈。


```python
def check_disclosure(result, requests, *, resource_exists):
    pairs = read_pairs(result)
    paths = [call["args"]["file_path"] for call, _ in pairs]
    assert SKILL_PATH in paths and REFERENCE_PATH in paths, "缺少必要读取"
    skill_index, ref_index = paths.index(SKILL_PATH), paths.index(REFERENCE_PATH)
    assert skill_index < ref_index, "应先读取技能正文，再读取资料"
    skill_call, skill_reply = pairs[skill_index]
    ref_call, ref_reply = pairs[ref_index]
    assert skill_reply.status == "success"
    assert all(line in skill_reply.text for line in SKILL_TEXT.splitlines())

    # 第一次请求：只能看到技能目录信息，不能提前看到文件正文。
    first = requests[0]
    assert all(value in first["system"]
               for value in ("release-check", DESCRIPTION, SKILL_PATH))
    assert BODY_MARKER not in first["context"]
    assert REFERENCE_MARKER not in first["context"]

    # 每条请求：相关工具返回出现之后，相应文件内容才能进入上下文。
    for request in requests:
        if skill_call["id"] not in request["tool_ids"]:
            assert BODY_MARKER not in request["context"], "技能正文提前进入上下文"
        if ref_call["id"] not in request["tool_ids"]:
            assert REFERENCE_MARKER not in request["context"], "资料提前进入上下文"
    after_skill = next(r for r in requests if skill_call["id"] in r["tool_ids"])
    assert BODY_MARKER in after_skill["context"]
    assert ref_call["id"] not in after_skill["tool_ids"], "两个读取阶段未分开"
    after_ref = next(r for r in requests if ref_call["id"] in r["tool_ids"])

    final = result["messages"][-1]
    assert isinstance(final, AIMessage) and not final.tool_calls
    if resource_exists:
        assert ref_reply.status == "success"
        assert all(line in ref_reply.text for line in REFERENCE_TEXT.splitlines())
        assert REFERENCE_MARKER in after_ref["context"]
        assert all(item in final.text for item in (REFERENCE_MARKER, SECOND_CHECK))
    else:
        assert ref_reply.status == "error"
        assert REFERENCE_PATH in ref_reply.text and "not found" in ref_reply.text
        assert REFERENCE_PATH in final.text
        assert all(item not in final.text for item in (REFERENCE_MARKER, SECOND_CHECK))
        assert all(REFERENCE_MARKER not in r["context"] for r in requests)
```


```python
for label, result, requests, exists in [
    ("资料存在", success, success_requests, True),
    ("资料缺失", missing, missing_requests, False),
]:
    check_disclosure(result, requests, resource_exists=exists)
    print(f"\n{label}：文件调用和披露顺序已核对")
    for index, request in enumerate(requests, 1):
        if REFERENCE_MARKER in request["context"]:
            stage = "目录 + 技能正文 + 参考清单"
        elif BODY_MARKER in request["context"]:
            stage = "目录 + 技能正文"
        else:
            stage = "仅技能目录"
        print(f"  第 {index} 次模型请求：{stage}")
    if exists:
        relevant = [line for line in requests[0]["system"].splitlines()
                    if "release-check" in line]
        show_text("首次请求中的技能目录片段：", "\n".join(relevant))
```

    
    资料存在：文件调用和披露顺序已核对
      第 1 次模型请求：仅技能目录
      第 2 次模型请求：目录 + 技能正文
      第 3 次模型请求：目录 + 技能正文 + 参考清单
    
    首次请求中的技能目录片段：
    - **release-check**: 当用户需要发布前检查清单时，读取本地资料并列出检查项。
      -> Read `/skills/release-check/SKILL.md` for full instructions
    
    资料缺失：文件调用和披露顺序已核对
      第 1 次模型请求：仅技能目录
      第 2 次模型请求：目录 + 技能正文
      第 3 次模型请求：目录 + 技能正文


## 7. 改一个检查项，再观察

在第 2 节只改 `SECOND_CHECK` 的文字，例如改成 `"发布前更新变更日志"`，然后**重启内核，从第一格运行全部**。先预测：

- 第一次模型请求仍只有技能目录，新的检查项不会提前出现。
- 成功场景第二次 `read_file` 应返回新文字，最终答复也会随真实工具结果改变；断言使用同一个 `SECOND_CHECK`，因此应继续通过。
- 缺失场景仍报文件不存在，不能借用成功场景的检查项。

看第 5 节的工具返回和第 6 节的三次请求顺序核对预测。若任一断言失败，先检查是否只改了这个变量、是否从第一格重跑；恢复原值后再完整运行。脚本模型按规则读取文件，不能用这个实验评价真实模型的发布建议质量。

## 小结与清理

- `skills=["/skills/"]` 让 Skills 中间件发现技能，第一次请求只包含目录信息。
- Agent 经 `read_file` 取得 `SKILL.md` 正文，再按其中路径读取参考清单；具体检查项在工具返回后才进入模型请求。
- frontmatter 能解析，不保证引用的资料存在；缺失资料由实际读取工具报告错误。
- 临时文件已由 `TemporaryDirectory` 清理，重跑第 5 节会创建全新的目录和 Agent。

继续阅读[第 7 章正文](../../content/ch07-skills.md)中的多来源技能与子 Agent 继承；下一章是[记忆管理](../../content/ch08-long-term-memory.md)。
