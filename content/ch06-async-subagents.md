# 第 6 章：异步子 Agent — 让主 Agent 同时驱动多个子任务

> 上一章我们学习了同步子 Agent，主 Agent 通过 `task` 工具委派、然后**等待**子 Agent 跑完。但是，当子任务要花上几分钟、甚至几十分钟时，主 Agent 在用户面前就成了“死机状态”——既无法继续聊，也无法插话调整方向。本章学习 Deep Agents 0.5.0 的预览特性：**Async Subagent（异步子 Agent）**——主 Agent 立即拿到任务 ID 就返回，子 Agent 在后台继续跑；用户可以随时问进度、追加要求，甚至中途取消。

> ⚠️ Async Subagent 是 `deepagents>=0.5.0` 的**预览特性**（preview），仍在迭代中，API 可能变化。本章对应的代码示例需要部署到 LangSmith Deployments 或自托管的 Agent Protocol 服务。

## 同步子 Agent 的瓶颈

回顾上一章的多子 Agent 协作模式：

```python
# 主 Agent 调用同步子 Agent
result = task(name="researcher", task="深入调研 LangGraph 生态")
# 此时主 Agent 在等待——可能要等 60 秒、120 秒，甚至更久
# 用户只能盯着对话框转圈
```

同步子 Agent 在两类场景下会让用户体验非常糟糕：

1. **长程任务**：如深度调研、大规模代码迁移、批量数据处理，子 Agent 工作时间从分钟级到小时级；
2. **可交互任务**：用户在子 Agent 跑到一半时，发现需要补充约束（"换个数据源再来一次"、"加上 2024 年的数据"），但同步模式下根本插不进去。

更糟的是——同步子 Agent 在被主 Agent `task()` 调用期间，**主 Agent 自己也被阻塞**。这意味着：在子 Agent 完成之前，用户无法和主 Agent 继续聊别的话题。

异步子 Agent 解决的就是这两件事：**不阻塞主线对话**，**支持中途控制**。

## 同步 vs 异步：六个维度的对比

| 维度 | 同步子 Agent | 异步子 Agent |
|---|---|---|
| **执行模型** | 阻塞——主 Agent 等到完成才能继续 | 非阻塞——立即返回任务 ID |
| **并发性** | 可并行触发，但主 Agent 仍被整批阻塞 | 完全并行，主 Agent 全程不阻塞 |
| **中途追加指令** | ❌ 不支持 | ✅ `update_async_task` 注入新指令 |
| **取消** | ❌ 不支持 | ✅ `cancel_async_task` 立即终止 |
| **状态性** | 无状态——每次调用相互独立 | 有状态——子 Agent 拥有自己的线程，会话历史持续累积 |
| **典型场景** | 一问一答、毫秒级到秒级的快速委派 | 几分钟以上的研究、编码、迁移等长程任务，需要在对话中互动管理 |

![同步 vs 异步子 Agent：左侧主 Agent 委派后被阻塞、用户只能等待；右侧主 Agent 拿到任务 ID 立即返回，用户可继续对话、查看进度、追加指令或取消任务](../public/imgs/15-comparison-sync-vs-async.png)

简单的判定法则：**子任务能在 5 秒内完成**，用同步；**子任务可能跑数分钟以上、且过程需要可交互**，上异步。

## 配置异步子 Agent

异步子 Agent 用 `AsyncSubAgent` 类来声明，每一个都指向一台 [Agent Protocol](https://github.com/langchain-ai/agent-protocol) 服务（最常见的就是 LangSmith Deployments，也可以是你自托管的兼容服务）：

```python
from deepagents import AsyncSubAgent, create_deep_agent

async_subagents = [
    AsyncSubAgent(
        name="researcher",
        description="深度研究 Agent，用于多次搜索 + 信息综合的调研任务",
        graph_id="researcher",
        # 不传 url → 使用 ASGI 进程内传输（与主 Agent 同部署在一个 server）
    ),
    AsyncSubAgent(
        name="coder",
        description="编码 Agent，用于代码生成、改写与代码评审",
        graph_id="coder",
        # url="https://coder-deployment.langsmith.dev"   # 可选：远程 HTTP 传输
    ),
]

agent = create_deep_agent(
    model="google_genai:gemini-3.5-flash",
    subagents=async_subagents,
)
```

### 字段一览

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | ✅ | 唯一标识，主 Agent 启动任务时用它指定子 Agent |
| `description` | ✅ | 能力描述，主 Agent 据此决定何时把任务委派给它 |
| `graph_id` | ✅ | Agent Protocol 服务上的 graph / assistant ID；LangGraph 部署需在 `langgraph.json` 中注册 |
| `url` | 可选 | 不填走进程内 ASGI 传输；填了走远程 HTTP 传输 |
| `headers` | 可选 | 远程模式下的自定义 HTTP 头，用于自托管服务的鉴权 |

如果是 LangGraph 部署，所有 graph 写在同一份 `langgraph.json` 中，就构成"同部署"形态。

## 主 Agent 的 5 把"遥控器"

声明 `AsyncSubAgent` 后，[`AsyncSubAgentMiddleware`](https://reference.langchain.com/python/deepagents/middleware/async_subagents/AsyncSubAgentMiddleware) 会自动给主 Agent 注入 5 个工具——把它们当成主 Agent 操控后台子任务的"遥控器"：

| 工具 | 作用 | 返回 |
|---|---|---|
| `start_async_task` | 启动一个新的后台任务 | 任务 ID（立即返回） |
| `check_async_task` | 查询任务当前状态与结果 | 状态 + 结果（若完成） |
| `update_async_task` | 给运行中的任务追加新指令 | 确认 + 更新后状态 |
| `cancel_async_task` | 终止运行中的任务 | 确认信息 |
| `list_async_tasks` | 列出所有任务（含实时状态） | 任务总览 |

主 Agent 像调用普通工具一样调用它们，中间件负责处理远程线程的创建、运行管理与状态持久化。

### 一次完整生命周期

把这 5 个工具串起来，就是一段标准对话：

```
用户：帮我深入调研一下 LangGraph 多 Agent 架构。
主 Agent → start_async_task("researcher", "调研 LangGraph 多 Agent 架构")
           → 返回 task_id: abc-123
主 Agent ← 「已经派 researcher 在后台开干，任务 ID：abc-123，
            你可以继续问别的，也可以随时让我查进度。」

用户：先帮我把这段 Python 代码格式化一下。
主 Agent ← （直接处理，researcher 仍在后台跑）

用户：刚才那个调研有进展吗？
主 Agent → check_async_task("abc-123")
           ← status: running
主 Agent ← 「还在跑，已经搜了 4 个关键词，预计还要几分钟。」

用户：补一下：重点关注 supervisor / network / hierarchical 这三种拓扑。
主 Agent → update_async_task("abc-123", "重点关注三种拓扑：supervisor / network / hierarchical")
           ← 已注入新指令

用户：算了，先停一下。
主 Agent → cancel_async_task("abc-123")
           ← cancelled
```

![异步子 Agent 生命周期：launch 立即返回任务 ID；用户继续对话；check 查询进度；update 中途追加指令；cancel 取消任务；list 列出所有任务。主 Agent 全程不阻塞](../public/imgs/16-flowchart-async-lifecycle.png)

如果把视角换成三泳道的时序图，可以更清晰地看到三方之间的消息流——用户、主 Agent 与 Agent Protocol 服务之间，请求与返回（实线 / 虚线）一来一回，中间是用户继续聊天的"非阻塞区"：

![异步子 Agent 时序图：用户向主 Agent 发起调研请求；主 Agent 调用 Agent Protocol 服务 launch 拿到 task_id 后立刻把控制权返还用户；后台 researcher 跑任务；用户后续询问进度，主 Agent 通过 check 拿到结果再回给用户](../public/imgs/17-sequence-async-protocol.png)

### 5 个工具底层做了什么

理解每个工具的实际行为，能帮你写出更合理的提示词：

- **`start_async_task`（launch）**：在 Agent Protocol 服务上**新建一个 thread**、启动一次 run，把任务描述作为输入；返回 thread ID 作为 task ID。主 Agent 拿到 ID 就回到对话循环，**不会轮询等待**。
- **`check_async_task`（check）**：读取 run 的当前状态。若已完成，再读 thread state 拿到子 Agent 的最终输出；若仍在跑，直接告诉用户"运行中"。
- **`update_async_task`（update）**：在**同一 thread** 上以 `interrupt` 多任务策略发起一次新 run——前一次 run 被打断，子 Agent 带着完整对话历史 + 新指令重新启动。任务 ID 保持不变。
- **`cancel_async_task`（cancel）**：调用 `runs.cancel()` 终止远程 run，并把本地任务标记为 `"cancelled"`。
- **`list_async_tasks`（list）**：遍历所有跟踪中的任务。已结束（success / error / cancelled）的从缓存返回；未结束的并发地向服务端拉取实时状态。

## 任务元数据为何要单开一个 channel？

主 Agent 的 graph state 中专门有一个 `async_tasks` 通道，独立于消息历史，存放每个任务的：task ID、子 Agent 名、thread ID、run ID、状态、`created_at`、`last_checked_at`、`last_updated_at`。

为什么不直接放在工具消息里？因为 Deep Agents 的上下文一旦逼近上限会**自动压缩对话历史**（参见第 3 章的上下文工程）。如果任务 ID 只活在某条 ToolMessage 里，压缩后就丢了——主 Agent 会瞬间"忘了"自己派出去的所有任务，再也无法 check 或 cancel。

把元数据搬到独立 channel 之后：消息历史可以放心被压缩、被裁剪，主 Agent 永远能通过 `list_async_tasks` 找回**自己派过的所有任务**。

> 这是 Deep Agents 一贯的设计哲学：**会被截断的放消息历史，必须长存的进 state channel**——和虚拟文件系统、TodoList 是同一套思路。

## 两种传输：ASGI vs HTTP

### ASGI 传输（同部署，推荐起手式）

`AsyncSubAgent` 不传 `url` 时，LangGraph SDK 会走 **ASGI 传输**——SDK 调用直接进程内函数路由，不走网络。LangGraph 部署需要把所有 graph 注册到同一个 `langgraph.json`。

ASGI 优势：

- **零网络延迟**：调用即函数调用
- **零额外鉴权配置**：本地进程互信
- **子 Agent 仍跑在独立 thread 上**，状态隔离不打折

绝大多数项目从这里起步就够了。

### HTTP 传输（远程，按需切换）

加上 `url` 字段就切换到 **HTTP 传输**，SDK 调用走网络发到远程 Agent Protocol 服务：

```python
AsyncSubAgent(
    name="researcher",
    description="研究 Agent",
    graph_id="researcher",
    url="https://my-research-deployment.langsmith.dev",
)
```

LangGraph 部署的鉴权由 SDK 自动处理：从环境变量读取 `LANGSMITH_API_KEY`（或 `LANGGRAPH_API_KEY`）。自托管的 Agent Protocol 服务可能用别的鉴权方案，按需通过 `headers` 传。

**什么时候用 HTTP？**

- 子 Agent 需要**独立扩缩容**
- 子 Agent 要不一样的资源画像（GPU / 大内存）
- 子 Agent 由**另一个团队**维护、独立发布

## 三种部署拓扑

| 拓扑 | 形态 | 推荐场景 |
|---|---|---|
| **单部署（Single）** | 所有 Agent 同部署，全部用 ASGI | **绝大多数项目的起点**：一台服务好运维、零网络延迟 |
| **拆分部署（Split）** | 主 Agent 一台，子 Agent 一台，全用 HTTP | 子 Agent 资源画像或扩缩容策略与主 Agent 显著不同 |
| **混合（Hybrid）** | 一部分子 Agent 走 ASGI（同部署），另一部分走 HTTP（远程） | 大多数子 Agent 同部署省事，少数特殊子 Agent 单独扩 |

混合形态长这样：

```python
async_subagents = [
    AsyncSubAgent(
        name="researcher",
        description="研究 Agent",
        graph_id="researcher",
        # 不传 url → ASGI（同部署）
    ),
    AsyncSubAgent(
        name="coder",
        description="编码 Agent",
        graph_id="coder",
        url="https://coder-deployment.langsmith.dev",
        # 传了 url → HTTP（远程）
    ),
]
```

**起手式建议**：先用单部署 + ASGI，等遇到具体的扩缩容/团队边界问题再拆。

## 最佳实践

### 1. 本地开发要把 worker pool 调大

每个活跃 run 占用一个 worker 槽位。一个主 Agent 同时跑 3 个子 Agent，至少需要 4 个槽位（1 主 + 3 子）。槽位不够，新启动的任务会**排队**——表现就是 `start_async_task` 一直拿不到 ID。

```bash
langgraph dev --n-jobs-per-worker 10
```

### 2. 描述要具体，行为导向

主 Agent 靠 `description` 决定派给谁。两个对照：

```python
# ✅ 好
AsyncSubAgent(
    name="researcher",
    description="深度网络调研，需要多次搜索 + 信息综合时使用",
    graph_id="researcher",
)

# ❌ 差
AsyncSubAgent(
    name="helper",
    description="帮你处理事情",
    graph_id="helper",
)
```

### 3. 用 thread ID 串联追踪

LangGraph 部署里，每次异步子 Agent 运行都是一次普通的 LangGraph run，在 LangSmith 中完整可见。主 Agent 的 trace 会显示 launch / check / update / cancel / list 这些工具调用；每个子 Agent 的运行是另一条 trace，**通过 thread ID（也就是 task ID）就能把两边对上**。出问题时这条线索极其重要。

## 常见问题排查

### 问题 1：刚启动就立刻轮询 check

**症状**：主 Agent 调完 `start_async_task` 立刻又调 `check_async_task`，循环往复——异步直接退化成"伪同步"。

**解法**：中间件本身已经在系统提示词里加了相关规则。如果模型仍然不听话，在你自己的主 Agent system_prompt 里再强化一次：

```python
agent = create_deep_agent(
    model="google_genai:gemini-3.5-flash",
    system_prompt="""...你的指令...

派出异步子 Agent 之后，**必须立刻把控制权交还给用户**；
不要在没有用户提问的情况下主动 check_async_task。""",
    subagents=async_subagents,
)
```

### 问题 2：报告了一个过时的状态

**症状**：用户问进度，主 Agent 直接引用对话历史里某个旧状态，没有发起新的 check。

**解法**：中间件提示词里写了"对话历史中的任务状态永远是过时的"。如果模型还是踩坑，在主 Agent 的 system_prompt 里再加上一条："回答任务进度前，必须先调用 `check_async_task` 或 `list_async_tasks`"。

### 问题 3：任务 ID 被截断或改写

**症状**：模型把 `abc-123-def-456-...` 缩写成 `abc-123` 或 `abc...`，导致 check / cancel 找不到任务。

**解法**：中间件已经要求模型使用完整 task ID。如果某个模型固执地截断，可以在 system_prompt 中加一条："始终使用完整的 task_id，不要截断、不要缩写、不要改写"，或者换个更听话的模型。

### 问题 4：启动子 Agent 长时间不返回

**症状**：`start_async_task` 卡住，迟迟拿不到任务 ID。

**解法**：worker pool 被打满。`langgraph dev` 启动时加上 `--n-jobs-per-worker 10`（或更大），按你预期的并发量调整。

## 参考实现

LangChain 官方提供了一个完整可跑的示例仓库：[async-deep-agents](https://github.com/langchain-ai/async-deep-agents)，Python 与 TypeScript 双版本，演示了一个主 Agent + researcher + coder 子 Agent 的部署形态，配套部署到 LangSmith Deployments。读完本章后，强烈建议把这个仓库 clone 下来跑一遍，亲眼看看主 Agent "派活之后立刻能继续聊"的实际效果。

## 小结

本章我们解锁了 Deep Agents 0.5.0 的预览特性 Async Subagent：

1. **核心动机**：突破同步子 Agent 的两个瓶颈——**主 Agent 不再被阻塞**，**任务可以中途追加指令或取消**。
2. **5 把遥控器**：`start` / `check` / `update` / `cancel` / `list`，主 Agent 像调普通工具一样用它们操控后台子任务。
3. **状态独立通道**：任务元数据存在 `async_tasks` channel 中，与消息历史解耦——即便上下文被压缩，任务 ID 永不丢失。
4. **两种传输**：默认 ASGI（同部署、零延迟），按需切换 HTTP（远程、可独立扩缩容）。
5. **三种拓扑**：单部署 / 拆分部署 / 混合，**起手用单部署**，按工程需要再拆。
6. **避坑要点**：worker pool 要足够、描述要具体、永远基于实时 `check` 而非对话历史报告状态。

下一章我们将学习 Skills——可复用的 Agent 能力包，让 Agent 获得领域专属的多步骤工作流与知识模板。

