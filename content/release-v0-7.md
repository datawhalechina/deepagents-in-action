# Deep Agents v0.7：更轻、更透明、更可配置的 Harness

> 一个已经在线运行的 Deep Agent 升级到 v0.7 后，账单可能下降，也可能没有明显变化；它可能继续稳定完成任务，也可能突然不再生成 Todo。原因在于 v0.7 调整了默认 Harness 替应用做决定的范围。

本课程从 Deep Agents 0.5 开始，前面的章节也保留了框架从 0.5、0.6 逐步演进的痕迹。v0.7 延续这条学习路径，并把当前课程基线向前推进了一步：它减少每轮固定携带的通用上下文，把规划等策略交还给应用，并补齐文件工具和 Middleware 的配置能力。新读者可以直接以最新 0.7.x 补丁版本开始；旧读者应先完成本章的迁移检查，再继续后续实验。

Deep Agents v0.7 撤掉了一批不再普遍必要的脚手架：默认基础提示词变空、工具说明缩短、`TodoListMiddleware` 改为按需启用。框架也开放了 Middleware 的原位替换，并调整文件工具的能力与输出语义。

架构上的变化很清楚：默认层更薄，原先藏在框架里的策略需要由应用显式选择。

本章以 [`deepagents==0.7.0` changelog](https://docs.langchain.com/oss/python/releases/changelog#deepagents-v0-7-0) 和 [Deep Agents v0.7 发布博客](https://www.langchain.com/blog/deep-agents-v0-7)为首发行为基线，并继续核对其中指向的评测报告、官方文档和实现 PR。重点是识别受影响的应用、决定是否恢复旧默认值，以及验证升级后的行为。

日常学习和迁移应安装当前 0.7.x 补丁版本，同时限制在同一个 minor 版本内：

```bash
uv add --upgrade "deepagents>=0.7,<0.8"
uv run python -c "import deepagents; print(deepagents.__version__)"
```

提交项目的 `uv.lock`，或保存等价的环境快照，才能记录实际解析到的精确版本。如果要逐项复现 v0.7.0 首发 changelog，再在独立临时环境固定版本：

```bash
uv add "deepagents==0.7.0"
```

不要直接在生产环境原地升级。v0.7 同时改变默认 Middleware、Backend 兼容接口和文件工具输出，单看“能否成功 import”无法证明迁移完成。

## 1. 先判断哪些默认策略变了

从使用者视角看，v0.7 有四组变化；从架构视角看，它们指向同一个方向。

| 表面变化 | 设计判断 | 应用需要接手的责任 |
|---|---|---|
| 默认基础提示词变空，工具说明缩短 | 现代模型更能从工具 Schema 理解接口，不必重复阅读教程式说明 | 写清真正属于业务的系统提示词，并用 Trace 检查冲突与冗余 |
| Todo 不再默认启用 | 显式计划不是所有任务都需要的普遍增益 | 根据任务长度、模型能力和 UI 需求决定是否恢复 |
| 同名 Middleware 可以原位替换 | 内置栈应提供合理默认值，但不应封死阈值、模型和提示词 | 显式管理替换实例的完整配置与继承范围 |
| 文件工具更强、更有界 | Agent 需要高效处理大文件和大目录，同时避免无限搜索 | 重新审查删除、覆盖写入、输出解析、权限和结果截断 |

逐条浏览 changelog、机械地问“这个功能我用不用”，很容易漏掉隐式依赖。先回答这些问题：

1. 我的应用以前依赖了哪些**隐式默认值**？
2. 哪些默认值在我的任务里仍然有价值，应该显式恢复？
3. 哪些地方消费了文件工具的**原始文本或 Backend 兼容接口**？
4. 我用什么业务评测证明更轻的 Harness 没有改变关键行为？

后面的内容都围绕这四个问题展开。

## 2. 如何正确理解“基础输入 Token 减少 65%”

官方给出的两个数字描述的是不同范围：

- 默认 Agent 的工具 Schema 描述从 **4,005 Token 降到 2,302 Token**，降幅 43%。其中 `task` 工具说明从 1,664 降到 389 Token，是最大的单项缩减。
- 加上空基础提示词和 Todo 改为可选后，一个默认 Agent 的简单回合输入从 **5,395 Token 降到 1,895 Token**，基础输入降幅约 65%。

这两个数字说明“每一轮都要携带的框架固定成本”明显降低，但不能推导出“任意应用总成本下降 65%”。真实调用还包含：

- 用户消息与历史对话
- Skills、Memory 和应用自己的系统提示词
- 工具调用参数及结果
- 子 Agent 轨迹
- Summarization 与失败重试
- 模型提供商的缓存命中与计费规则

如果一次长程任务本来就有几十万 Token 的历史和工具结果，少掉约 3,500 个基础输入 Token 仍然有价值，但占总成本的比例不会是 65%。

### 2.1 端到端评测呈现的是“总体趋势”，不是统一收益

官方新的 [Deep Agents 评测体系](https://www.langchain.com/blog/how-we-benchmark-deep-agents)不再只依赖小型单元题，而是覆盖三类 Agent 工作：

| 评测类别 | 观察什么 | 为什么与升级有关 |
|---|---|---|
| Autonomous | 编程、数据分析、长程工具使用等端到端任务 | 检查删掉脚手架后，Agent 是否还能自主完成多步工作 |
| Conversational | 模拟用户参与的多轮对话 | 检查更少的默认提示是否影响追问、工具选择和会话目标 |
| Long-context / Retrieval | 在随任务提供的长上下文中检索和组合答案 | 检查更轻的 Prompt 是否让模型丢失长上下文能力 |

Harbor 评测任务同时包含运行环境、任务说明和验收脚本。评分看的是 Agent 修改的文件与环境状态，而不只看最终回复是否“像答案”。每个任务还会重复运行，以降低 Agent 非确定性造成的偶然波动。

在 v0.6.12 与 v0.7 的跨版本对比中，官方对 36 个任务、每个任务 3 次 rollout，覆盖四种模型。精确结果比“普遍更省”更有指导意义：

| 模型 | Reward 变化 | Token 变化 | 成本变化 | 应该怎样读 |
|---|---:|---:|---:|---|
| `gpt-5.6-luna` | +3.8% | -35.5% | -15.2% | Token 与成本下降最明确，Reward 变化仍在不确定区间内 |
| `gemini-3.6-flash` | -6.7% | -4.7% | -8.1% | 三项置信区间都跨过零，不能据此断言一定变好或变差 |
| `claude-sonnet-4-6` | +3.1% | +31.3% | +36.8% | 两个高难自治任务产生更长轨迹，抵消了基础 Prompt 的节省 |
| `claude-opus-4-8` | -5.1% | -25.4% | -16.4% | Token 下降明确；Reward 与成本变化仍不能视为普遍结论 |

所有模型的 Reward 置信区间都跨过零，因此官方结论是“整体质量没有可测量的回退”，不能改写成“v0.7 让所有模型质量提升”。Luna 和 Opus 的 Token 降幅更明确，Luna 的成本下降也更明确；Sonnet 的结果则说明，基础开销更低不保证 Agent 轨迹更短。

### 2.2 对项目的实际指导

升级验收至少要分开记录三类指标：

1. **基础开销**：简单回合的 input tokens，验证默认 Harness 确实变轻。
2. **轨迹效率**：完成同一任务所需的模型轮次、工具调用数、子 Agent 调用数和重试数。
3. **业务结果**：任务是否通过真实验收，而不是最终文本是否看起来合理。

如果只比较第一项，很容易在 Sonnet 一类场景里得到错误结论。生产决策应以自己的模型、提示词、工具集和任务分布为准。

## 3. 默认 Prompt 变空：把业务指令与工具接口分开

v0.7 移除了 Deep Agents 原先附加的通用基础提示词，也删掉了与工具 Schema 重复的 Middleware 使用说明。这里删除的是“框架代写的通用做事方法”，不是 Skills、Memory 或文件路径路由等只有运行时才知道的信息。

这一变化背后有两个 context engineering 原则：

- **接口优于示例**：清晰的工具名称、参数类型、枚举和约束可以直接表达可用动作；大量 few-shot 示例可能反而把模型限制在示例展示的探索路径里。
- **避免重复**：同一条约束同时写进系统提示词和工具描述，不会自动得到双倍遵从，却会永久增加每轮输入并增加冲突概率。

这与 Anthropic 在[新一代模型的 context engineering 经验](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)中报告的方向一致：他们为更强模型大幅精简 Claude Code 系统提示词，并强调通过接口设计而不是大量工具调用示例来引导模型。

### 3.1 自定义系统提示词现在更“说了算”

以前，应用传入的 `system_prompt` 会与框架基础提示词共同构成上下文。即使两段文字没有直接冲突，也可能重复规定语气、规划或工作方式。v0.7 的默认基础层为空，应用提示词的含义更直接：

```python
from deepagents import create_deep_agent


agent = create_deep_agent(
    model=model,
    system_prompt=(
        "你是代码迁移助手。先读取仓库中的版本约束和测试入口，"
        "只修改与迁移目标有关的文件；完成后运行项目已有测试，"
        "并明确报告未能验证的部分。"
    ),
)
```

不要因为“旧版有一段长基础 Prompt”就把旧内容完整复制进应用。先从任务真正需要的约束开始，再通过失败案例补充。否则会把 v0.7 刚移除的固定成本和潜在冲突重新带回来。

可以用下面的顺序诊断升级后的行为差异：

1. 检查工具 Schema 是否已经表达了约束，不要先向系统提示词重复粘贴。
2. 检查应用是否依赖旧基础 Prompt 中的通用行为，例如主动验证、进度播报或少问问题。
3. 只补充对业务结果有影响的规则，并为它建立评测样例。
4. 观察 LangSmith Trace，确认新增提示没有让模型产生额外解释、规划或循环。

## 4. Todo 改为可选：规划是一种策略，不是固定税费

`create_deep_agent()` 在 v0.7 中不再默认安装 `TodoListMiddleware`。没有显式启用时，以下三项会一起消失：

- `write_todos` 工具
- `todos` state channel
- Todo 规划提示词

官方在 GPT-5.6 Terra、Claude Opus 4.8 和 GLM 5.2 上比较后，没有观察到 Todo 带来统计显著的准确率提升；其中两种模型的 Token 使用还更高。因此框架不再让所有调用为显式规划付费。

这并不等于“Todo 没用”。它的价值取决于任务与产品：

| 场景 | 建议 | 原因 |
|---|---|---|
| 单步问答、短工具调用 | 保持关闭 | 计划本身可能比任务还长 |
| 长程、多阶段、容易漏步骤的任务 | 启用 | 显式状态能帮助模型跨多轮保持目标 |
| 能力较弱或容易失去主线的模型 | 先做 A/B 评测，通常值得尝试 | 较弱模型更依赖外部脚手架 |
| UI 要展示计划、当前步骤和进度 | 启用 | Todo 同时是产品状态协议，不只是模型提示 |
| 后台批处理，只关心最终产物 | 默认关闭，再用评测决定 | 用户不需要可见计划，先避免固定成本 |

需要恢复时，从 LangChain Middleware 导入：

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware


agent = create_deep_agent(
    model=model,
    middleware=[TodoListMiddleware()],
)
```

### 4.1 注意 Todo 的继承范围

v0.7 的实现有意区分两类子 Agent：

- 默认的 `general-purpose` 子 Agent 会继承主 Agent 显式传入的 Todo 实例。
- 声明式 `subagents=[...]` 拥有独立 Middleware 栈，不会自动继承主 Agent 的 Todo，需要在自己的 spec 中启用。

```python
from langchain.agents.middleware import TodoListMiddleware


researcher = {
    "name": "researcher",
    "description": "执行需要多个检索与验证步骤的研究任务",
    "system_prompt": "先规划证据收集步骤，再逐项完成并标记状态。",
    "middleware": [TodoListMiddleware()],
}

agent = create_deep_agent(
    model=model,
    subagents=[researcher],
)
```

OpenAI Codex harness profile 是例外：它的系统提示词明确依赖 `write_todos`，所以 profile 会自动保留 Todo。迁移时不要只按包版本猜测工具集合，应以实际 profile 和 Trace 为准。

如果 Todo 被用于前端进度，升级测试必须覆盖 state channel，而不能只确认最终答案仍然生成。第 4 章的[任务规划与分解](../ch04-task-planning/)讲解了 Todo 的工作机制；本节关注的是 v0.7 后如何决定是否为它付费。

## 5. Middleware 原位覆盖：可配置不等于配置会自动合并

过去，如果应用向 `middleware=` 传入一个自定义 `SummarizationMiddleware`，框架会因为它与默认实例重名而报重复错误。v0.7 改为按 `.name` 匹配：自定义实例与某个内置 Middleware 同名时，会在原位置换掉默认实例。

这让应用可以调整摘要模型、触发阈值和提示词，而不必拆掉整个 Harness：

```python
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.middleware import SummarizationMiddleware


backend = StateBackend()

agent = create_deep_agent(
    model=model,
    backend=backend,
    middleware=[
        SummarizationMiddleware(
            model=summary_model,
            backend=backend,
            trigger=("fraction", 0.5),
            keep=("messages", 20),
            summary_prompt=(
                "总结此前对话，原样保留文件路径、已确认的决定、"
                "未完成事项和失败原因。"
            ),
        )
    ],
)
```

默认摘要通常在上下文窗口使用到约 85% 时触发。对工具结果多、长对话中容易出现 context rot 的应用，提前到 50% 可能更稳，但会增加摘要频率与信息损失风险。阈值不是越低越好，需要同时检查摘要调用成本和后续任务成功率。

### 5.1 覆盖规则与继承规则

根据 [Middleware 覆盖实现](https://github.com/langchain-ai/deepagents/pull/4251)，v0.7 的规则是：

1. `.name` 与内置实例相同：在原位置替换，保留栈的相对顺序。
2. 没有同名默认实例：插入核心 Middleware 之后、profile / prompt caching / memory 尾部之前。
3. 默认 `general-purpose` 子 Agent 会继承主 Agent 对默认实例的覆盖。
4. 声明式子 Agent 独立构建自己的栈，需要在各自 spec 中配置。
5. 某些必须位于尾部的 Middleware 仍保持既定顺序，例如工具排除逻辑要在工具注入完成后运行。

### 5.2 最容易忽略的陷阱：这是整实例替换

同名覆盖不是字段级 merge。传入自定义 `FilesystemMiddleware` 或 `SummarizationMiddleware` 后，框架不会把默认实例中的 Backend、工具说明、权限状态或其他构造参数逐字段补到新实例里。

因此应遵循两个规则：

- 共享同一个 Backend 实例，避免主 Agent 与 Middleware 实际读写不同文件空间。
- 把替换实例当成完整配置重新审查，不要只关注自己想改的那一个字段。

`deepagents==0.7.0` 中，文件权限由框架通过私有配置注入默认 `FilesystemMiddleware`。如果应用一边使用顶层 `permissions=`，一边又替换整个文件 Middleware，不能假定拒绝规则会自动合并进新实例。更稳妥的做法是升级到经过验证的最新 0.7.x 补丁版本、避免依赖私有参数，并用真实的允许/拒绝调用做回归测试。工具从模型界面消失，不代表权限边界仍然成立。

## 6. 文件工具：更高效，也更需要重新审查副作用

文件系统是 Deep Agents 的上下文管理层。v0.7 既补充能力，也给大目录搜索设置边界。

| 变化 | v0.7 行为 | 对现有应用的影响 |
|---|---|---|
| `write_file` | 目标存在时直接完整覆盖 | 以前依赖“已存在即报错”的保护逻辑会失效 |
| `delete` | 加入默认文件工具，可删除文件或递归删除目录 | 工具面新增高风险副作用，需要权限、审批或 allowlist |
| `read_file` 分页 | 返回总行数、剩余行数和下一次 `offset` | Agent 可直接跳到下一页或文件尾部，减少盲目重复读取 |
| `grep` / `glob` 超时 | 返回已找到的有效结果并标记 `truncated` | “成功”可能只是部分成功，调用方必须保留不完整语义 |
| `grep` 匹配数 | Agent 工具默认最多 1,000 个匹配并流式消费本地 `rg` 输出 | 避免大仓库无限占用内存和上下文；宽查询需要主动收窄 |
| 空 `ls` / `glob` | 文本变为 `No files found`，不再是 `[]` | 解析原始输出的代码需要修改 |
| `read_file` 行号槽 | 行号后使用两个空格，不再是固定宽度加 Tab | 按 Tab 切分或模拟 `cat -n` 的解析器会失败 |

### 6.1 覆盖写入与精确编辑的职责更清楚

现在的推荐语义是：

- 完整重写文件：使用 `write_file`
- 只修改局部：先 `read_file`，再使用 `edit_file` 做精确字符串替换

这样可以避免为了完整重写而把整个旧文件作为 `edit_file.old_string` 再发回模型，减少不必要 Token。但它也移除了一层误覆盖保护。对配置、凭证、生产脚本等敏感路径，不能依赖旧错误行为，应显式使用 `FilesystemPermission`、HITL 或只读工具集合。

### 6.2 `delete` 是写操作，而且目录删除是全有或全无

支持删除的 Backend 会向 Agent 暴露 `delete`。递归删除目录时，权限层会检查目标与所有后代路径：只要其中任何路径命中拒绝规则，整个删除都不执行，而不是留下一棵删了一半的目录树。符号链接会删除链接本身，不跟随到目标。

如果应用不需要删除，最小权限原则是根本不暴露它：

```python
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.middleware import FilesystemMiddleware


backend = StateBackend()

agent = create_deep_agent(
    model=model,
    backend=backend,
    middleware=[
        FilesystemMiddleware(
            backend=backend,
            tools=["read_file", "ls", "glob", "grep"],
        )
    ],
)
```

这个 allowlist 只控制八个内置文件工具，不会删除应用自定义工具。`read_file` 是 `FilesystemMiddleware` 的必需能力，不能从列表中排除；`execute` 和 `delete` 还会继续受 Backend 能力限制，allowlist 只能收窄，不能把 Backend 不支持的能力变出来。

v0.7 的后续修复还确保被排除的工具会从 `ToolNode` 注册表中移除，不是只对模型隐藏。主 Agent 的同名覆盖会传给默认 `general-purpose` 子 Agent；声明式子 Agent 仍要单独限制。

工具 allowlist 解决的是“模型能调用哪些内置工具”，不是完整的文件访问控制。路径级规则、Shell、自定义工具与 MCP 的边界见[第 11 章：文件系统权限](../ch11-filesystem-permissions/)。

### 6.3 部分搜索结果不是错误，但也不是全集

大目录上的 `grep` / `glob` 以前可能超时、挂起，或丢掉已经找到的匹配。v0.7 会返回现有匹配，并用 `truncated=True` 表示结果不完整。对于 Agent-facing 工具，这类超时后的部分结果可以是成功的 `ToolMessage`，模型会收到“缩小路径或模式”的提示。

直接消费 Backend 结果的应用需要明确区分：

```python
result = backend.grep("TODO", path="/workspace")

if result.error:
    raise RuntimeError(result.error)

for match in result.matches or []:
    consume(match)

if result.truncated:
    schedule_narrower_search()
```

不能用“没有异常”推断搜索完整，也不能因为 `truncated=True` 丢掉已经返回的有效匹配。`CompositeBackend` 会在任何一个路由结果不完整时传播 `truncated=True`。

`grep` 的 1,000 匹配上限是 `FilesystemMiddleware` 面向模型的默认值，模型可以通过 `max_count` 调整；直接调用 Backend 时默认仍是无上限。`context_lines` 在 v0.7.0 首先加入本地 `FilesystemBackend.grep()` 的直接调用接口，并没有同时成为所有 Backend 和模型工具的统一参数。不要看到 changelog 的“可选上下文行”就假设任意 Agent-facing `grep` 都支持同一 Schema。

### 6.4 分页元数据优化的是轨迹，不只是输出格式

`read_file(offset=..., limit=...)` 在没有分页元数据时，模型需要猜测文件是否还有内容、下一页从哪里开始。v0.7 的尾部提示会报告已读行范围、总行数、剩余行数和下一 `offset`。

官方针对 301 行文件的评测中，两种模型都能把读取次数稳定降低到两次，并直接跳向文件尾部。这类改动解释了为什么 Harness 优化不能只看 Prompt Token：更好的工具反馈会改变整个调用轨迹。

## 7. v0.6 → v0.7：会阻塞升级的兼容变化

Todo 是最显眼的 breaking change，但不是唯一一个。Backend 兼容层和原始输出解析更容易在上线后才暴露问题。

### 7.1 Backend Factory 被移除

从 v0.5 开始废弃的 Backend Factory 在 v0.7 被正式删除。`create_deep_agent()` 现在接收具体的 `BackendProtocol` 实例，而不是根据 runtime 创建 Backend 的 callable。

```python
# v0.6.x：旧兼容写法
agent = create_deep_agent(
    backend=lambda runtime: StoreBackend(),
    store=store,
)
```

应迁移为显式实例，并为 `StoreBackend` 配置 namespace：

```python
from deepagents import create_deep_agent
from deepagents.backends import StoreBackend


backend = StoreBackend(
    namespace=lambda runtime: (runtime.server_info.user.identity,),
)

agent = create_deep_agent(
    model=model,
    backend=backend,
    store=store,
)
```

这种变化不只是类型收紧。以前隐式的 assistant-id namespace fallback 被移除，应用必须明确文件属于哪个用户、租户或业务范围。namespace 设计错误可能导致跨用户读取，不能为了通过类型检查随便填一个常量。

同时需要处理这些兼容项：

- 删除 `BackendFactory`、`BACKEND_TYPES`、`FileFormat` 和 `Unset` 的使用
- 删除 `StateBackend(runtime=...)`、`StoreBackend(runtime=...)` 的旧参数
- 迁移 `ls_info`、`glob_info`、`grep_raw` 和旧的纯字符串 `read()` 接口
- 使用当前 `ls` / `glob` / `grep` / `ReadResult` API
- 删除 `SummarizationMiddleware(history_path_prefix=...)`；历史卸载改为使用配置好的 Backend
- 认识到 `FilesystemBackend` 与 `LocalShellBackend` 默认 `virtual_mode=True`

新文件的 `FileData.content` 使用字符串。旧版本持久化的 `list[str]` 仍可读取，并会在下一次覆盖或编辑时转换，因此不需要为了升级一次性重写全部存量文件；但序列化器和自定义 Backend 应同时接受迁移期数据。

### 7.2 原始工具输出解析器必须单独排查

如果应用只把工具结果交回模型，格式变化通常由模型自然适应。如果应用自己解析 `ToolMessage.content`，以下写法都值得检查：

- 把空目录结果与字符串 `"[]"` 比较
- 对 `read_file` 每行执行 `split("\t", 1)`
- 假设行号永远占固定宽度
- 把 `ToolMessage.status == "success"` 当成搜索完整
- 假设 `write_file` 在文件已存在时一定失败

对机器消费的逻辑，优先使用 Backend 的结构化结果，不要把给模型阅读的文本格式当成稳定协议。

### 7.3 先做静态扫描，再运行真实迁移测试

可以从这几组搜索开始：

```bash
rg -n 'BackendFactory|BACKEND_TYPES|FileFormat|Unset|history_path_prefix' .
rg -n 'ls_info|glob_info|grep_raw' .
rg -n 'backend\s*=\s*(lambda|[A-Za-z_][A-Za-z0-9_]*_factory)' .
rg -n 'split\("\\t"|cat -n|No files found|write_file' .
```

搜索结果不是迁移完成证明。它只能找出常见旧符号，找不到业务代码对 Todo state、工具存在性或错误语义的隐式依赖。

## 8. 两组“按需关注”的能力

下面的更新有价值，但不应该挤占所有读者的迁移注意力。

### 8.1 Provider 级 Prompt Caching

- AWS Bedrock 用户可以通过 `deepagents[aws]` 使用 Prompt caching 支持。
- 安装兼容版本的 `langchain-fireworks` 时，Deep Agents 会为主 Agent 和子 Agent 自动加入 Fireworks prompt-cache session affinity。

它们优化的是特定提供商的缓存复用，不改变所有模型的通用调用方式。验收时应检查缓存读写 Token、session / thread affinity 和实际账单，而不是只确认 Middleware 已加载。

### 8.2 NVIDIA Nemotron 3 Ultra Harness Profile

v0.7 提供 Nemotron 3 Ultra 的内置 Harness profile，覆盖 NVIDIA / ChatNVIDIA、Baseten、Fireworks、OpenRouter、Nebius 和 Together 等入口，并加入工具调用兼容修复、循环控制、最终答案保护和 NIM app-origin 标记。

这类实现把模型特有的差异放进 Harness profile，业务规则仍留在应用调用处。如果不使用 Nemotron，这部分不是升级阻塞项；如果使用，则应额外关注 profile 可能增加的一次修复轮次，以及错误工具调用被自动修正后的 Trace。

## 9. 从课程 0.5/0.6 基线升级到 0.7

如果你已经跑通过课程早期示例，不需要推倒重来。保留原来的任务、输入和 Trace 作为对照，再按下面七步升级；这些旧结果正好能帮助你判断 v0.7 是降低了固定成本，还是改变了实际行为。

### 第一步：记录 v0.6 基线

选择能代表生产分布的任务，至少覆盖：

- 一个短问答或单工具任务
- 一个长程多步骤任务
- 一个会调用子 Agent 的任务
- 一个大文件分页读取或大目录搜索任务
- 一个权限拒绝或人工审批任务

保存成功率、输入 / 输出 Token、模型轮次、工具调用数、子 Agent 数、延迟和成本。

### 第二步：在隔离环境升级到当前 0.7.x

使用 `deepagents>=0.7,<0.8` 获取当前补丁版本，并锁定项目的依赖快照；只有排查某项首发行为时，才用 `==0.7.0` 单独复现。不要让“升级 Deep Agents”与“同时升级模型、提示词和业务工具”混在同一批变更里。

### 第三步：迁移会直接报错的 API

处理 Backend factory、显式 Store namespace、移除符号、`history_path_prefix` 和旧 Backend 方法。此阶段目标是让应用完成初始化和基本调用。

### 第四步：逐项声明原先依赖的默认策略

问清楚：

- 是否需要 Todo？主 Agent 和每个声明式子 Agent 是否一致？
- 自定义系统提示词是否缺少旧默认层曾提供的关键业务行为？
- 是否要覆盖 Summarization 的模型、阈值或提示词？
- `delete` 和覆盖写入是否符合权限模型？
- 文件工具是否应使用 allowlist 收窄？

### 第五步：重写原始输出解析测试

加入空目录、带 Tab 缩进文件、分页文件、截断搜索、已存在文件覆盖和递归删除拒绝等样例。对结构化 Backend 结果与 Agent-facing 文本分别测试，不要混为一种协议。

### 第六步：在 LangSmith 中做同任务对比

逐条比较 v0.6 与 v0.7 Trace：

| 观察项 | 异常信号 | 可能动作 |
|---|---|---|
| 首轮 input tokens | 没有明显下降 | 检查应用 Prompt、Skills、Memory 或工具描述是否占主导 |
| 模型轮次 | 明显增加 | 检查 Todo 移除、工具说明过短或模型进入循环 |
| `write_todos` / `todos` | UI 依赖但已消失 | 显式恢复 `TodoListMiddleware` |
| Summarization 触发点 | 太晚导致 context rot，或太早丢信息 | 用同名覆盖调整 `trigger`、`keep` 和摘要提示词 |
| 文件搜索 | `truncated` 后仍直接下结论 | 引导模型缩小路径，或让调用方继续分片搜索 |
| 文件副作用 | 出现意外覆盖或删除 | 收窄工具、加强路径权限或增加 HITL |

### 第七步：渐进放量，以业务验收决定是否继续

先让一部分流量进入 v0.7，比较相同任务类型的成功率与成本。基础 Token 下降是好信号，但只有业务结果稳定、轨迹没有异常放大时，才说明迁移真正完成。

## 10. 最终决策表

| 如果你的应用…… | v0.7 的建议动作 |
|---|---|
| 只做短任务，没有进度 UI | 保持 Todo 关闭，享受更轻默认层 |
| 运行长程任务或较弱模型 | 显式启用 Todo，并用业务评测验证收益 |
| 使用对话摘要 | 用同名 `SummarizationMiddleware` 调整阈值，但把它当完整实例配置 |
| 解析文件工具原始文本 | 把输出格式迁移列为阻塞项，优先改用结构化结果 |
| 暴露真实文件系统 | 审查 `delete`、覆盖写入、allowlist、路径权限与 HITL |
| 使用 StoreBackend | 移除 factory，设计显式 namespace，并做租户隔离测试 |
| 依赖 Provider 缓存或 Nemotron | 验证对应 profile / integration 的 Trace 与账单，不把它当通用收益 |

v0.7 的实用价值在于重新划清边界：默认层保持轻量，工具接口说明能力，应用选择策略，评测检查结果。模型和任务继续变化时，这种分工比不断扩张的通用系统提示词更容易维护。

## 参考资料

- [Deep Agents v0.7 发布博客](https://www.langchain.com/blog/deep-agents-v0-7)
- [`deepagents` v0.7.0 changelog 与迁移提示](https://docs.langchain.com/oss/python/releases/changelog#deepagents-v0-7-0)
- [How we benchmark Deep Agents](https://www.langchain.com/blog/how-we-benchmark-deep-agents)
- [Customize Deep Agents：Middleware 覆盖](https://docs.langchain.com/oss/python/deepagents/customization#override-a-default-middleware-instance)
- [Deep Agents Overview：Task planning](https://docs.langchain.com/oss/python/deepagents/overview#task-planning)
- [Deep Agents Overview：Virtual filesystem access](https://docs.langchain.com/oss/python/deepagents/overview#virtual-filesystem-access)
- [PR #5009：精简内置工具说明与跨模型评测](https://github.com/langchain-ai/deepagents/pull/5009)
- [PR #4929：Todo 改为 opt-in 与完整实验结果](https://github.com/langchain-ai/deepagents/pull/4929)
- [PR #4251：按名称覆盖默认 Middleware](https://github.com/langchain-ai/deepagents/pull/4251)
- [PR #4541：移除 Backend 兼容层](https://github.com/langchain-ai/deepagents/pull/4541)
- [PR #4109：`write_file` 支持覆盖](https://github.com/langchain-ai/deepagents/pull/4109)
- [PR #4540：`read_file` 分页元数据](https://github.com/langchain-ai/deepagents/pull/4540)
- [PR #4063：`grep` / `glob` 部分结果与 `truncated`](https://github.com/langchain-ai/deepagents/pull/4063)
- [PR #4570：`grep` 匹配上限与流式输出](https://github.com/langchain-ai/deepagents/pull/4570)
- [PR #4706：本地 Backend 的 `grep` 上下文行](https://github.com/langchain-ai/deepagents/pull/4706)
- [PR #3851：递归删除与权限语义](https://github.com/langchain-ai/deepagents/pull/3851)
- [PR #4325：文件工具 allowlist](https://github.com/langchain-ai/deepagents/pull/4325)
- [PR #4698：被排除的工具不可执行](https://github.com/langchain-ai/deepagents/pull/4698)
