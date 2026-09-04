# 第 4 章：任务规划与分解 — 让 Agent 学会拆解复杂任务

> 上一章我们学习了虚拟文件系统如何管理 Agent 的上下文。本章聚焦另一个核心能力——任务规划。`write_todos` 可以帮助 Agent 拆解任务、追踪进度；从 v0.7 开始，这项能力按需启用，不再是每个 Agent 的固定配置。

## 为什么 Agent 需要"规划"能力？

### 简单任务 vs 复杂任务

对于简单任务，Agent 可以一步到位：

```
用户：北京今天天气怎么样？
Agent：[调用天气工具] → 今天北京晴，25°C。
```

但对于复杂任务，一步到位是不可能的：

```
用户：帮我调研 LangGraph 的技术架构，对比三个竞品，写一份 3000 字的分析报告。
```

这个任务涉及：搜索多个信息源、阅读和整理大量资料、对比分析、组织结构、撰写报告。没有规划，Agent 要么遗漏步骤，要么在某个环节陷入死循环。

### 没有规划的 Agent 会怎样？

- **遗漏关键步骤**：直接开始写报告，忘了先搜索竞品信息
- **重复劳动**：搜索了同一个关键词三次，因为它"忘记"已经搜过了
- **半途而废**：上下文太长后，Agent 失去了对整体进度的把控
- **质量不稳定**：有时做得很好，有时莫名跳过重要环节

规划能力让 Agent 能够**先思考再行动**——把大任务拆解为小步骤，然后逐步执行、追踪进度、动态调整。

## 在 v0.7 中显式启用任务规划

`TodoListMiddleware` 会同时注入 `write_todos` 工具、`todos` 状态和规划提示词。v0.7 默认不再安装它，需要时应明确传入：

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

agent = create_deep_agent(
    model=model,
    middleware=[TodoListMiddleware()],
)
```

是否启用，应由任务和产品需求决定：

| 场景 | 建议 |
|---|---|
| 单步问答、短工具调用 | 保持关闭，避免计划比任务本身还长 |
| 长程、多阶段、容易漏步骤的任务 | 启用，并用真实任务检查完成率和轨迹长度 |
| 能力较弱、容易失去主线的模型 | 先做 A/B 评测，通常值得尝试 |
| UI 需要展示计划、当前步骤和进度 | 启用；此时 `todos` 也是产品状态协议 |

## `write_todos` 工具详解

启用后，Deep Agents 会获得 `write_todos` 工具，让 Agent 可以创建和管理任务清单。工具存在不代表每个任务都会调用；具体行为仍由模型、提示词和任务复杂度共同决定。

### 任务的数据结构

每个任务包含以下字段：

```python
{
    "content": "搜索 LangGraph 官方文档，整理核心架构和 API 设计",  # 任务内容
    "status": "pending"  # 状态
}
```

### 三种状态

| 状态 | 含义 | 典型场景 |
|---|---|---|
| `pending` | 待办 | Agent 刚规划出来，还没开始做 |
| `in_progress` | 进行中 | Agent 正在执行这个步骤 |
| `completed` | 已完成 | Agent 确认做完了 |

状态流转：`pending` → `in_progress` → `completed`

### Agent 怎么用 write_todos？

当 Agent 收到一个复杂任务时，它的典型行为是：

**第一步：制定计划**

```
Agent 思考：这个任务比较复杂，我先拆解一下。
Agent 调用 write_todos：
  1. [pending] 搜索 LangGraph 官方文档和核心概念
  2. [pending] 搜索三个竞品（Temporal、Inngest、Prefect）
  3. [pending] 对比分析各产品的优劣势
  4. [pending] 撰写报告大纲
  5. [pending] 撰写完整报告
```

**第二步：逐步执行**

```
Agent 更新任务 1 状态为 in_progress
Agent 调用 internet_search("LangGraph architecture")
Agent 调用 write_file("/workspace/langgraph_notes.md", ...)
Agent 更新任务 1 状态为 completed

Agent 更新任务 2 状态为 in_progress
Agent 调用 internet_search("Temporal vs LangGraph")
...
```

**第三步：动态调整**

在执行过程中，Agent 可能发现需要额外的步骤：

```
Agent 思考：搜索时发现 Prefect 不太合适，应该换成 Durable Objects。
Agent 调用 write_todos 更新列表：
  1. [completed] 搜索 LangGraph 官方文档和核心概念
  2. [in_progress] 搜索三个竞品
  3. [pending] 对比分析各产品的优劣势
  4. [pending] 撰写报告大纲
  5. [pending] 撰写完整报告
  6. [pending] 补充 Durable Objects 的资料 ← 新增
```

![Agent 如何使用 write_todos：制定计划（全部 pending）→ 逐步执行（状态流转 + 调用工具）→ 动态调整（发现新需求，新增步骤）](../public/imgs/10-flowchart-todo-workflow.png)

> [!NOTE]
> **v0.7 提醒**：这张图描述的是已启用 `TodoListMiddleware` 后的典型流程。默认配置中没有 `write_todos`；即使已经启用，图中的步骤也是可用工作方式，不是框架强制执行的状态机。

### 任务清单的持久化

任务清单**持久化在 Agent State 中**，这意味着：

- 在同一个对话中，任务清单不会丢失
- 即使 Agent 的对话历史被总结压缩，任务清单依然完整
- 默认 `general-purpose` 子 Agent 会继承主 Agent 显式传入的 Todo 配置，但仍在自己的状态中维护清单
- `subagents=[...]` 声明的子 Agent 有独立 Middleware 栈，需要规划能力时必须在自己的 spec 中启用 Todo；它也不会读取主 Agent 的清单

## 揭开引擎盖：LangChain 中间件

到目前为止，我们一直从 Deep Agents 的视角看 `write_todos`。如果你想理解它为什么可以按需加入，以及如何扩展，就需要揭开引擎盖，看看底层的 LangChain 中间件机制。

还记得第 1 章的三层架构吗？Deep Agents（Harness）构建在 LangChain（Framework）之上。而 LangChain 提供了一套<strong>中间件（Middleware）</strong>系统——它是 Agent 能力的插件机制。`create_deep_agent()` 内部做的事情，本质上就是把一组中间件**自动组装**到了 Agent 上。

### 先分清两类 Hook

LangChain 中间件提供两类执行边界。它们都叫 Hook，但适合解决的问题并不相同：

| 风格 | Hook | 执行方式 | 适合场景 |
|---|---|---|---|
| **Node-style** | `before_agent`、`before_model`、`after_model`、`after_agent` | 编译成 Agent 图中的独立节点，按生命周期顺序运行 | 校验、状态更新、审计、人工中断 |
| **Wrap-style** | `wrap_model_call`、`wrap_tool_call` | 包裹一次模型或工具调用；可以不调用、调用一次或多次 `handler` | 重试、缓存、降级、请求或响应转换 |

这个区别对 `interrupt()` 尤其重要：Node-style Hook 有清晰的图节点边界，暂停与恢复时更容易推断哪些逻辑会重放；Wrap-style Hook 位于 model/tools 节点内部，恢复时可能连同 `handler` 一起重新执行。因此自定义人工中断优先放在 Node-style Hook 中，Wrap-style 即使技术上可以调用，也不适合作为默认中断边界。

第 9 章会用一个完整例子展示[如何在自定义 Middleware 的 Node-style Hook 中直接调用 `interrupt()`](../ch09-human-in-the-loop/#在自定义-middleware-中使用-interrupt)。

v0.7 可以从三类来源理解 `create_deep_agent()` 的中间件堆栈：

**框架默认层**：
- `FilesystemMiddleware` — 注入 7 个文件工具，并执行 `permissions` 权限规则
- `SummarizationMiddleware` — 上下文自动压缩，触发阈值可配置
- `PatchToolCallsMiddleware` — 内部工具调用修补（框架内部使用）
- Prompt caching 等模型相关能力 — 是否启用取决于模型和 Harness profile

**条件层（按参数自动激活）**：
- `SubAgentMiddleware` — 有子 Agent 时启用，自动加入通用子 Agent；注入 `task` 工具
- `SkillsMiddleware` — 传入 `skills=` 参数时启用，注入技能包
- `AsyncSubAgentMiddleware` — 传入异步子 Agent 时启用
- `MemoryMiddleware` — 传入 `memory=` 参数时启用，注入 AGENTS.md 记忆
- `HumanInTheLoopMiddleware` — 传入 `interrupt_on=` 参数时启用，拦截指定工具调用等待人工审批

**应用选择层**（通过 `middleware=[...]` 传入）：
- `TodoListMiddleware` 等可选策略可以按需加入
- 与默认 Middleware 同名的实例会在原位置换默认实例，而不是在末尾再叠加一个
- 原位置换是完整实例替换，不会把新旧配置按字段合并

理解这三层，你就能：
- 看懂 Deep Agents 内部是怎么拼装出来的
- 自己按需添加新能力（PII 脱敏、模型降级、调用次数限制……）
- 在更底层的 LangChain `create_agent()` 上搭建定制化的 Agent

其中 `FilesystemMiddleware` 的路径授权不需要另写自定义中间件；`permissions=` 的规则模型、默认允许语义与适用边界见[第 11 章：文件系统权限](../ch11-filesystem-permissions/)。

![揭开引擎盖：create_deep_agent() 内部分为常驻层（TodoList、Filesystem、Summarization、PatchToolCalls、AnthropicCaching）、条件层（SubAgent、Skills、Memory、HumanInTheLoop 等按参数激活）和用户自定义层](../public/imgs/11-framework-middleware-assembly.png)

> [!NOTE]
> **v0.7 提醒**：图片中的 TodoList 位于旧版常驻层。当前 Todo 属于应用选择层；同名的 `FilesystemMiddleware` 或 `SummarizationMiddleware` 则会替换默认实例，而且是整实例替换，不是字段合并。

### TodoListMiddleware：write_todos 的真身

`write_todos` 的底层实现是 LangChain 的 `TodoListMiddleware`。无论使用 Deep Agents 的 `create_deep_agent()`，还是更底层的 `create_agent()`，v0.7 都需要显式添加这项能力。下面展示 LangChain 层的手动组合：

> **示意片段**：下面聚焦中间件组装，因此不注册额外的应用工具；运行前需要安装示例中的包并配置 `SILICONFLOW_API_KEY`。

```python
import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from deepagents.middleware import FilesystemMiddleware

model = ChatOpenAI(
    # 任务规划属于复杂推理场景，建议使用能力较强、支持工具调用的模型
    model="zai-org/GLM-5.2",
    api_key=os.environ["SILICONFLOW_API_KEY"],
    base_url="https://api.siliconflow.cn/v1",
)

agent = create_agent(
    model=model,
    tools=[],
    middleware=[
        TodoListMiddleware(),
        FilesystemMiddleware(),   # 自动注入 read_file / write_file 等文件工具
    ],
)
```

添加 `TodoListMiddleware` 后，Agent 会自动获得：

1. **`write_todos` 工具** — 创建和管理任务清单
2. **`todos` 状态** — 保存任务及其状态，供同一 Agent 的后续轮次和 UI 使用
3. **规划指导提示词** — 引导 Agent 在面对复杂任务时先规划再执行

这段代码展示了 LangChain `create_agent()` 的用法。Deep Agents 会提供文件系统、上下文管理和子 Agent 等 Harness 默认能力，但 Todo 仍由应用选择。

### 自定义配置

`TodoListMiddleware` 支持两个可选参数：

```python
TodoListMiddleware(
    system_prompt="...",      # 自定义规划指导提示词
    tool_description="...",   # 自定义 write_todos 工具的描述
)
```

大多数情况下，默认配置就够了。只有当你发现 Agent 的规划行为需要特别引导时（比如"总是先写测试再写代码"），才需要自定义 `system_prompt`。

### SummarizationMiddleware：上下文压缩的真身

第 3 章讲的"对话历史自动总结"，底层就是 `SummarizationMiddleware`。它和 `TodoListMiddleware` 一样，也是 LangChain 的预构建中间件之一。

## 任务规划与上下文管理的协同

在长时间运行的任务中，任务规划和上下文管理需要**协同工作**。

### 问题场景

假设 Agent 正在执行一个包含 10 个步骤的研究任务。执行到第 6 步时，对话历史已经非常长了——前面 5 步的搜索结果、文件读写操作、中间思考过程全部堆在上下文里。

此时，Deep Agents 的上下文管理机制（第 3 章）会自动介入：

1. **大结果卸载**：前面步骤产生的大量搜索结果已经被卸载到文件系统
2. **对话总结**：如果上下文仍然超过触发阈值（默认 85%，可通过 `SummarizationMiddleware` 的 `trigger` 参数自定义），旧的对话会被总结压缩

### 任务清单的锚定作用

关键点在于：**即使对话历史被总结压缩了，任务清单依然完整**。

这意味着 Agent 在总结后仍然知道：

- 总共有哪些步骤
- 哪些已经完成，哪些还在进行
- 下一步该做什么

任务清单充当了 Agent 的"北极星"——无论中间过程如何压缩，Agent 始终不会迷失方向。

### 在 LangChain 中手动组合

理解了中间件机制后，你就能看懂 Deep Agents 内部是怎么组装的。下面这段代码用 LangChain 的 `create_agent()` 手动组合了任务规划和上下文总结两个能力——这基本就是 `create_deep_agent()` 内部做的事情（的一部分）：

> **示意片段**：复用上一个示例定义的 `model`，并省略与中间件组合无关的自定义工具。

```python
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from deepagents.middleware import FilesystemMiddleware, SummarizationMiddleware

agent = create_agent(
    model=model,
    tools=[],
    middleware=[
        TodoListMiddleware(),
        FilesystemMiddleware(),   # read_file / write_file 通过中间件注入
        SummarizationMiddleware(
            model="zai-org/GLM-5.2",  # 总结压缩影响后续推理质量，建议使用能力较强的模型
            trigger=("tokens", 4000),  # 可自定义：("ratio", 0.85) 或 ("tokens", N)
            keep=("messages", 20),
        ),
    ],
)
```

> 在 Deep Agents 中，`SummarizationMiddleware` 仍属于默认上下文管理能力；`TodoListMiddleware` 则需要通过 `middleware=[...]` 显式加入。

## 代码实战：让 Agent 规划并执行研究任务

让我们来看一个完整的例子——让 Agent 自主规划并执行一个多步骤研究任务：

```python
import os
from langchain_openai import ChatOpenAI
from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

# 配置模型
model = ChatOpenAI(
    # 多步骤规划任务建议使用能力较强、支持工具调用的模型
    model="zai-org/GLM-5.2",
    api_key=os.environ["SILICONFLOW_API_KEY"],
    base_url="https://api.siliconflow.cn/v1",
)

# 搜索工具
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def internet_search(query: str, max_results: int = 5) -> dict:
    """搜索互联网获取最新信息。"""
    return tavily_client.search(query, max_results=max_results)

# 创建 Agent，并显式启用 write_todos
agent = create_deep_agent(
    model=model,
    tools=[internet_search],
    middleware=[TodoListMiddleware()],
    system_prompt="""你是一位专业的技术研究员。
面对复杂研究任务时，你会：
1. 先用 write_todos 制定研究计划
2. 逐步执行每个步骤，及时更新进度
3. 将搜索结果写入文件系统整理
4. 最终输出完整的研究报告
""",
)

# 发起一个需要规划的复杂任务
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "请调研 Agent 开发领域的三大 Harness 框架（Deep Agents、Claude Agent SDK、Codex SDK），对比它们的核心能力差异，写一份简要分析报告。"
    }]
})

print(result["messages"][-1].content)
```

在这个例子中，Agent 会自动：

1. 调用 `write_todos` 制定研究计划（搜索→对比→写报告）
2. 逐步执行每个任务，更新状态
3. 用 `write_file` 保存中间搜索结果到虚拟文件系统
4. 最终综合所有信息输出报告

## LangChain 中间件全景：Deep Agents 的能力版图

现在你已经理解了中间件的来源，让我们看看完整的能力版图。框架提供默认层和条件层，应用可以通过 `create_deep_agent(middleware=[...])` 加入可选策略，或原位置换同名默认实例：

**框架默认层**

| 中间件 | 用途 |
|---|---|
| FilesystemMiddleware | 7 个文件工具 + 权限控制 |
| SummarizationMiddleware | 对话历史自动总结（触发阈值可配置） |
| PatchToolCallsMiddleware | 工具调用内部修补（框架内部） |
| 模型 / Provider 相关 Middleware | 由 Harness profile 和实际模型决定 |

**条件层（按参数激活）**

| 参数 | 中间件 | 用途 |
|---|---|---|
| `subagents=` （默认自动包含） | SubAgentMiddleware | `task` 工具 + 子 Agent 委派 |
| `skills=` | SkillsMiddleware | 技能包注入 |
| `subagents=` | AsyncSubAgentMiddleware | 异步子 Agent 任务管理 |
| `memory=` | MemoryMiddleware | AGENTS.md 记忆注入 |
| `interrupt_on=` | HumanInTheLoopMiddleware | 人工审批拦截 |

**可选层（via `middleware=[...]`，LangChain 预构建，Deep Agents 不自动内置）**

| 类别 | 中间件 | 用途 |
|---|---|---|
| **规划** | TodoListMiddleware | 任务规划与追踪，注入 `write_todos` 和 `todos` 状态 |
| **安全** | PIIMiddleware | 个人信息检测和脱敏 |
| **弹性** | ToolRetryMiddleware | 工具调用失败自动重试 |
| | ModelRetryMiddleware | 模型调用失败自动重试 |
| | ModelFallbackMiddleware | 主模型失败自动切换备用模型 |
| **限制** | ToolCallLimitMiddleware | 限制工具调用次数 |
| | ModelCallLimitMiddleware | 限制模型调用次数 |
| **上下文** | ContextEditingMiddleware | 清理旧的工具调用结果 |

![Deep Agents 中间件全景：常驻层（5个始终启用）、条件层（5个按参数激活）、可选层（LangChain 预构建，按需添加），以及不可排除的必要中间件 FilesystemMiddleware + SubAgentMiddleware](../public/imgs/12-infographic-middleware.png)

> [!NOTE]
> **v0.7 提醒**：图片保留了旧版“5 个常驻层”的结构。当前 Todo 不再常驻；`FilesystemMiddleware` 和 `SubAgentMiddleware` 仍支撑核心工具，但同名自定义实例可以在原位置换默认配置。替换时必须给出完整配置，并重新验证权限、Backend 和子 Agent 行为。

## 小结

本章我们学习了两件事——Deep Agents 的任务规划能力，以及它背后的 LangChain 中间件机制：

1. **为什么需要规划**：复杂任务需要先拆解再执行，否则 Agent 会遗漏步骤、重复劳动、半途而废
2. **`write_todos` 工具**：启用 `TodoListMiddleware` 后，任务以 pending → in_progress → completed 三种状态保存在 Agent State 中
3. **LangChain 中间件**：Agent 能力的插件机制。`create_deep_agent()` 的本质就是把一组中间件自动组装到 Agent 上
4. **由表及里**：`write_todos` 的真身是 `TodoListMiddleware`，上下文压缩的真身是 `SummarizationMiddleware`——理解底层，才能自由扩展
5. **能力版图**：`create_deep_agent()` 组合框架默认层、条件层和应用选择层；v0.7 支持同名 Middleware 原位置换，但不会自动合并新旧配置

下一章，我们将学习子 Agent 与上下文隔离——让 Agent 学会"委派"，把复杂子任务交给专门的 Agent 处理。
