# 第 10 章：沙箱执行 — 让 Agent 安全地运行代码

> Agent 一旦能写文件、运行 Shell 命令、安装依赖，就拥有了很强的执行能力。问题是：这些操作绝不能直接碰到宿主机的代码、环境变量和凭证。本章学习如何把执行环境交给远程沙箱，让 Agent 可以安全地写代码、运行测试和生成文件。

## 沙箱是什么？

在 Deep Agents 中，**沙箱（Sandbox）是一种 Backend**：它定义 Agent 操作文件和执行命令的隔离环境。

普通 Backend（例如 `StateBackend`、`FilesystemBackend`、`StoreBackend`）提供文件操作；沙箱 Backend 在此基础上额外提供 `execute`，使 Agent 能在沙箱内运行 Shell 命令：

| 能力 | 普通 Backend | 沙箱 Backend |
|---|---|---|
| 查看、读取、写入、编辑、删除文件 | `ls`、`read_file`、`write_file`、`edit_file`、`delete` | 同样支持 |
| 查找文件与内容 | `glob`、`grep` | 同样支持 |
| 运行 Shell 命令 | 不支持 | `execute` |
| 执行位置 | Backend 对应的存储环境 | 与宿主环境隔离的远程环境 |

因此，沙箱不是“给工具加一个权限开关”。它是 Agent 的**执行环境边界**：Agent 在其中写脚本、运行命令和安装依赖，不能直接读取宿主机文件、环境变量或干扰宿主进程。

当 Agent 调用 `execute` 时，它传入命令字符串，拿到命令输出、退出码，以及输出过大时的截断提示。大型结果会被保存为文件，Agent 再用 `read_file` 分段读取，避免一次把大量日志塞进模型上下文。

## 为什么需要沙箱？

代码执行型 Agent 的行为无法在提示词阶段完全预测。它可能需要：

- 克隆仓库、运行测试、安装依赖
- 读取 CSV、使用 `pandas` 分析数据、生成图表或演示文稿
- 编写临时脚本，反复运行、检查和修复

如果这些操作直接落在宿主机，Agent 可能读到 `.env`、破坏工作目录，或让意外命令影响其他进程。沙箱把这些风险限制在独立环境中：沙箱失败不会丢失 Agent 的对话状态，销毁沙箱后其中的文件和进程也会消失。

但要注意边界：**沙箱保护宿主机，并不自动解决提示注入或数据外传。** 如果攻击者能影响 Agent 的输入，Agent 仍可能在沙箱内执行危险命令；如果网络未受限，它也可能通过 HTTP 或 DNS 向外发送数据。后文会专门讨论这部分安全设计。

## 两种集成模式

“沙箱”描述的是执行环境，Agent 可以在不同位置运行。官方文档归纳为两种模式：

| 模式 | Agent 在哪里运行 | 优点 | 代价 |
|---|---|---|---|
| Agent in sandbox | Agent 与代码都在沙箱内 | 环境与本地开发更接近，Agent 与运行环境紧密耦合 | 密钥需放入沙箱；更新 Agent 要重建镜像；还要维护 HTTP 或 WebSocket 通信层 |
| Sandbox as tool | Agent 在宿主服务，代码任务交给远程沙箱 | Agent 逻辑可即时更新；密钥和 Agent 状态留在沙箱外；可以并行使用多个沙箱 | 每次远程执行有网络延迟 |

在大多数 Deep Agents 应用中，推荐使用 **Sandbox as tool**：你的应用进程保有模型与凭证，Agent 通过 Backend 调用远程沙箱的 `execute`、`read_file`、`write_file` 等工具。这样既保留了隔离边界，又不会把 API Key 复制到 Agent 可读取的环境中。

## 快速上手：LangSmith Sandboxes

LangSmith Sandboxes 是官方的一方托管方案。先安装沙箱依赖：

```bash
uv add "langsmith[sandbox]"
# 或 pip install "langsmith[sandbox]"
```

然后创建一个沙箱，包装成 `LangSmithSandbox` Backend，并传给 `create_deep_agent`：

```python
from deepagents import create_deep_agent
from deepagents.backends import LangSmithSandbox
from langchain_anthropic import ChatAnthropic
from langsmith.sandbox import SandboxClient

client = SandboxClient()
sandbox = client.create_sandbox()
backend = LangSmithSandbox(sandbox=sandbox)

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-6"),
    system_prompt="You are a Python coding assistant with sandbox access.",
    backend=backend,
)

try:
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Create a small Python package and run pytest",
        }]
    })
    print(result["messages"][-1].content)
finally:
    # 无论 Agent 是否成功，都清理远程资源
    client.delete_sandbox(sandbox.name)
```

这里最关键的是 `backend=backend`。Deep Agents 会检测 Backend 是否实现了沙箱协议；只有实现了该协议，模型才会看到 `execute` 工具。其余文件系统工具建立在 Backend 的沙箱执行能力之上。

> `finally` 不是装饰性代码。沙箱会持续占用资源并产生费用；短任务应明确停止或删除。不同提供商的销毁 API 不同，请使用各自集成文档中的生命周期方法。

## Agent 工具与文件传输 API：两个平面

初学者最容易混淆的地方是：**Agent 在沙箱内操作文件**，和**应用在宿主机与沙箱之间搬运文件**，是两套不同的 API。

| 谁调用 | 方法 | 用途 |
|---|---|---|
| LLM / Agent | `read_file`、`write_file`、`edit_file`、`delete`、`ls`、`glob`、`grep`、`execute` | 在沙箱内部完成任务 |
| 你的应用代码 | `upload_files()`、`download_files()` | 在 Agent 运行前后跨越宿主机与沙箱边界 |

### 运行前：上传种子文件

例如，把项目代码或输入数据放入沙箱。`upload_files()` 使用绝对路径和 `bytes` 内容：

```python
backend.upload_files([
    ("/src/index.py", b"print('Hello')\n"),
    ("/pyproject.toml", b"[project]\nname = 'my-app'\n"),
])
```

之后 Agent 可以用 `read_file` 读取这些文件，或用 `execute` 运行它们。你也可以用这一层预先放入配置、数据或依赖 Agent 完成任务所需的文件。

### 运行后：提取产物

Agent 完成后，应用用 `download_files()` 取回构建产物、报告或图表，并显式处理单个文件的失败结果：

```python
results = backend.download_files([
    "/src/index.py",
    "/output.txt",
])

for result in results:
    if result.content is not None:
        print(f"{result.path}: {result.content.decode()}")
    else:
        print(f"Failed to download {result.path}: {result.error}")
```

这条边界很重要：模型不需要、也不应该知道宿主机的文件系统布局。宿主应用决定哪些输入可以进入沙箱，哪些产物可以离开沙箱。

## 选择沙箱提供商

Deep Agents 的沙箱能力通过 Backend 集成提供。当前官方文档列出的集成包括：

| 提供商 | 对应集成 |
|---|---|
| LangSmith | `LangSmithSandbox` |
| Amazon Bedrock AgentCore | `AgentCoreSandbox` |
| Daytona | `DaytonaSandbox` |
| E2B | `E2BSandbox` |
| Modal | `ModalSandbox` |
| NVIDIA OpenShell | `OpenShellSandbox` |
| Runloop | `RunloopSandbox` |
| Vercel | `VercelSandbox` |

它们都把提供商原生沙箱包装为 Deep Agents Backend。选择时优先确认四件事：运行时是否适合你的任务、区域和合规要求、网络与凭证控制能力，以及创建、复用和销毁沙箱的生命周期语义。具体安装包、认证和 API 以各集成的官方文档为准。

## 生命周期：每次对话创建，还是跨对话复用？

沙箱不是无状态函数调用。它包含文件、已安装的依赖和正在运行的进程，因此首先要定义它的作用域：

| 作用域 | 行为 | 适用情况 | 注意事项 |
|---|---|---|---|
| Thread-scoped（默认） | 每个对话线程各有一个沙箱；同一 `thread_id` 的后续轮次复用它 | 用户任务彼此独立 | 线程结束或 TTL 到期时应清理 |
| Assistant-scoped | 同一个 Assistant 的所有线程复用同一沙箱 | 需要跨对话保留仓库、依赖或缓存 | 状态会累积；需要 TTL、快照或定期清理策略 |

对于允许用户回到旧任务的应用，创建沙箱时应设置空闲 TTL，并保存 `thread_id`（或 `assistant_id`）与 sandbox name / metadata 的映射。下一次调用先查找已有沙箱，不存在时再创建。这样能兼顾多轮对话的连续性和资源成本。

## 安全设计：隔离不等于信任

安全设计的原则很简单：**不要把秘密放进沙箱。** 不要通过环境变量、挂载文件或 Provider 的 secrets 参数注入 API Key、Token、数据库凭证等。只要 Agent 能读取它，提示注入攻击者也有机会把它外传。

更安全的两种模式是：

1. **宿主侧工具（首选）**：认证逻辑和密钥保留在你的应用服务里。Agent 只调用一个工具名，例如 `publish_report`，但无法查看这个工具使用的凭证。
2. **凭证注入代理**：由网络代理拦截沙箱向外发出的请求，在转发前添加认证头。沙箱仍只发送普通请求，不接触密钥。并非每个提供商都支持这种能力。

即使不存放密钥，仍应落实以下措施：

- 不需要联网时，阻断或限制沙箱网络；这能减少数据外传通道
- 需要外部副作用的操作结合 Human-in-the-Loop 审批，而不是让 Agent 直接执行
- 审查沙箱输出后再让宿主应用使用它；沙箱生成的代码、报告和文件都应视为不可信输入
- 用中间件过滤或脱敏工具输出中的敏感模式
- 为沙箱设置最小权限、短生命周期，并监控异常的出站网络行为

把沙箱看作“降低宿主机风险的执行边界”，而不是“自动让 Agent 可信”。只有把密钥、网络、审批和产物消费也纳入设计，才能形成完整的安全闭环。

## 本章小结

- 沙箱 Backend 为 Deep Agents 提供隔离文件系统和 `execute`，让 Agent 能安全地完成代码执行型任务
- 对多数应用，Sandbox as tool 让 Agent 与密钥留在宿主服务、把代码执行交给远程环境，是更易维护的模式
- `upload_files()` / `download_files()` 由应用控制，Agent 的文件工具只在沙箱内部工作
- 明确 thread-scoped 或 assistant-scoped 生命周期，并用 TTL 与清理逻辑控制成本和状态累积
- 沙箱不能消除提示注入和网络外传风险；永远不要将密钥放入沙箱，并将所有产物视为不可信输入

## 官方参考

- [Deep Agents Sandboxes](https://docs.langchain.com/oss/python/deepagents/sandboxes)
- [Deep Agents Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [LangSmith Sandboxes](https://docs.langchain.com/langsmith/sandboxes)
