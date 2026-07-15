# AgentSeek 准备篇（上）：用生命周期工作流启动 DeepAgents 模板

> 完成本章后，你会得到一个可运行的 DeepAgents 研究应用。AgentSeek 会负责检查环境、安装项目依赖并启动前后端。
>
> 本文命令于 2026-07-15 验证。AgentSeek 和模板会继续更新；如果任务名称与本文不同，以 `agentseek task --list` 的输出为准。
>
> **视频说明**：页面中的视频录制于旧版 `agentseek-cli`。新版命令以本文为准，视频将在重新录制后更新。

## AgentSeek 管理什么

AgentSeek 是一个面向 AI 应用开发的模板与生命周期工具。你通过模板创建项目，再用一组固定命令管理不同项目：

| 阶段 | 命令 | 用途 |
|------|------|------|
| 创建 | `agentseek create` | 从模板生成可编辑的项目 |
| 查看 | `agentseek info` | 查看项目入口、环境要求和任务 |
| 准备 | `agentseek task` | 运行模板声明的依赖安装等一次性任务 |
| 检查 | `agentseek doctor` | 静态检查文件、uv、Node.js、npm 和环境变量 |
| 运行 | `agentseek dev` | 启动模板声明的本地开发进程 |

每个生成项目都包含 `.agentseek/lifecycle.toml`。这个文件声明当前模板需要哪些工具、环境变量、任务和本地服务。AgentSeek 读取它，不接管应用自己的框架代码。

## 1. 准备本地环境

本章使用 `deepagents/research` 模板。你需要：

| 依赖 | 要求 | 用途 |
|------|------|------|
| Python | 3.12 或 3.13 | 运行 AgentSeek 和 DeepAgents 后端 |
| uv | 当前稳定版 | 安装 CLI 和 Python 依赖 |
| Node.js、npm | 当前 LTS 版本 | 运行 React 前端 |

安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装 AgentSeek：

```bash
uv tool install agentseek
```

如果你已经安装过当前包，可以升级：

```bash
uv tool upgrade agentseek
```

如果终端仍显示 `agentseek-cli 0.0.x`，先移除旧包，再安装当前包：

```bash
uv tool uninstall agentseek-cli
uv tool install agentseek
```

确认命令已经可用：

```bash
agentseek version
agentseek --help
```

你应该在帮助信息中看到 `create`、`info`、`task`、`doctor` 和 `dev`。

## 2. 选择并创建模板

查看当前 CLI 识别的模板：

```bash
agentseek create --list-templates
```

模板列表会随 AgentSeek 更新。本课程使用 `deepagents/research`，它包含 DeepAgents 研究 Agent、Tavily 搜索和 React 前端。

创建项目并使用模板默认值：

```bash
agentseek create deepagents/research --no-input
```

进入生成目录：

```bash
cd research_deepagent
```

如果你想自定义项目名称、模型和端口，去掉 `--no-input`，再按提示填写模板变量。

## 3. 查看生命周期配置

先查看项目摘要：

```bash
agentseek info
```

再查看模板提供的一次性任务：

```bash
agentseek task --list
```

当前 `deepagents/research` 模板会列出两个准备任务：

```text
sync      Install Python dependencies with uv.
frontend  Install frontend dependencies.
```

任务名称属于模板配置。以后如果输出发生变化，请运行输出中对应的依赖安装任务。

项目中的关键文件如下：

```text
research_deepagent/
├── .agentseek/lifecycle.toml
├── .env.example
├── frontend/
│   ├── .env.example
│   ├── package.json
│   └── src/
├── langgraph.json
├── pyproject.toml
└── src/research_deepagent/
    ├── agent.py
    ├── prompts.py
    └── tools.py
```

## 4. 安装项目依赖

运行模板声明的后端依赖任务：

```bash
agentseek task sync
```

安装前端依赖：

```bash
agentseek task frontend
```

这两个任务当前分别执行 `uv sync` 和 `npm install --prefix frontend`。你可以在 `.agentseek/lifecycle.toml` 中查看实际命令。

## 5. 配置模型和搜索服务

复制后端和前端环境文件：

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

打开 `.env`，选择一个模型供应商，并填写对应的 Key。默认配置使用 OpenAI：

```bash
AGENTSEEK_MODEL_PROVIDER=openai
AGENTSEEK_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_API_BASE=

TAVILY_API_KEY=<your-tavily-api-key>

LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
```

`<your-openai-api-key>` 和 `<your-tavily-api-key>` 是占位符。请替换为你自己的值，不要把真实 Key 提交到 Git。

使用 Anthropic 时，修改模型供应商、模型名称和 Key：

```bash
AGENTSEEK_MODEL_PROVIDER=anthropic
AGENTSEEK_MODEL=claude-3-5-sonnet-latest
ANTHROPIC_API_KEY=<your-anthropic-api-key>
```

使用 Gemini 时：

```bash
AGENTSEEK_MODEL_PROVIDER=google_genai
AGENTSEEK_MODEL=gemini-2.5-pro
GOOGLE_API_KEY=<your-google-api-key>
```

OpenAI 兼容服务仍使用 `AGENTSEEK_MODEL_PROVIDER=openai`，并通过 `OPENAI_API_BASE` 和 `OPENAI_API_KEY` 配置地址与凭证。不要改用 `QWEN_API_KEY` 等模板未声明的变量。

例如，通过 SiliconFlow 使用 GLM 时可以这样配置：

```bash
AGENTSEEK_MODEL_PROVIDER=openai
AGENTSEEK_MODEL=<从模型广场复制的完整-GLM-模型-ID>
OPENAI_API_BASE=https://api.siliconflow.cn/v1
OPENAI_API_KEY=<your-siliconflow-api-key>
```

SiliconFlow 的模型会上线或下线。不要长期照抄某个模型 ID；运行前请在 [SiliconFlow 模型广场](https://cloud.siliconflow.cn/models) 确认当前可用的完整名称。本章验证时使用的是 `zai-org/GLM-5.2`。

`TAVILY_API_KEY` 用于研究 Agent 的网络搜索。你可以在 [Tavily](https://app.tavily.com/) 创建 Key。

## 6. 检查启动条件

运行就绪检查：

```bash
agentseek doctor
```

AgentSeek 会检查 uv、Node.js、npm、必需文件、依赖目录和环境变量。如果检查失败，请先修复每一项，再继续启动。

预览开发进程，不启动服务：

```bash
agentseek dev --dry-run
```

你应该看到两个进程：

- LangGraph 后端，默认地址为 `http://127.0.0.1:2024`
- React 前端，默认地址为 `http://127.0.0.1:5174`

## 7. 可选：为下一章开启 LangSmith Trace

下一章会用 `langsmith-trace` 分析这次研究过程。如果你准备继续该实操，请先在 `.env` 中开启 Trace：

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your-langsmith-api-key>
LANGSMITH_PROJECT=deepagents-course
```

`<your-langsmith-api-key>` 是占位符。请在 [LangSmith](https://smith.langchain.com/settings) 创建自己的 Key，并只把真实值写入不会提交到 Git 的 `.env`。

LangChain 和 LangGraph 会自动记录 Trace，不需要修改应用代码。`LANGSMITH_PROJECT` 用于把本章的运行集中到 `deepagents-course` 项目；如果省略，Trace 通常会进入 `default` 项目。

不要把真实 Key 直接写进 Shell 命令，也不要使用 `--api-key`。命令内容可能进入 Shell 历史、进程列表或编码助手日志。

Trace 可能包含提示词、工具参数和模型输出。本章只使用公开研究问题。如果你的输入包含敏感数据，请先阅读 LangSmith 的数据脱敏设置，不要照搬本章配置。

如果你暂时不使用 LangSmith，请保持：

```bash
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
```

## 8. 启动并验证应用

启动前后端：

```bash
agentseek dev
```

保持这个终端运行。在另一个终端中进入同一项目目录，检查两个服务：

```bash
agentseek doctor --live
```

打开 `http://127.0.0.1:5174`，输入：

```text
Research what LangGraph 1.0 added vs 0.x. Cite sources.
```

运行正常时，你会看到：

- Agent 创建研究计划并更新待办状态
- 模型选择委派时，界面展示研究子 Agent 的任务卡
- 最终报告展示搜索得到的来源链接
- 最终回答以 Markdown 渲染，并附带来源链接

深度研究会进行多轮模型调用、搜索和网页读取，不同模型可能需要几分钟。运行期间请保持 `agentseek dev` 和前端页面打开；页面生成 thread URL 后，可以用它重新打开同一会话。

如果你在上一节开启了 LangSmith，可以在运行期间打开 [LangSmith](https://smith.langchain.com/)，进入 `deepagents-course` 项目。最新 Trace 会在研究完成前出现；等待最终报告生成后，再检查完整耗时。

你应该能找到：

- 名为 `research` 的根 Trace
- `research-agent` 子 Agent
- `ChatOpenAI` 模型调用
- `tavily_search` 搜索调用
- `write_todos`、文件工具和 middleware 包装层

本文使用 SiliconFlow GLM 的实测运行完成了 4/4 个任务，用时约 473.5 秒。该数字只说明 5–10 分钟的流程已经走通；你的模型、网络、搜索结果和 Run 数量可能不同。

下一章不会要求你理解所有 middleware 节点。你只需要保留这条 Trace，并学会区分根流程、子 Agent、实际模型调用和工具调用。

回到运行 `agentseek dev` 的终端，按 `Ctrl+C` 停止前后端。

## 网络问题排查

`agentseek create` 需要访问 GitHub。先检查仓库连接：

```bash
git ls-remote https://github.com/ob-labs/agentseek.git
```

如果连接失败，请先修复当前终端的网络或代理配置。不要通过删除 `~/.cookiecutters` 缓存来绕过连接问题。

你也可以从已经下载到本地的模板目录创建项目：

```bash
agentseek create /absolute/path/to/agentseek/templates/deepagents/research --no-input
```

依赖下载速度较慢时，可以按团队或所在网络的要求设置 `UV_INDEX_URL` 和 npm registry。镜像服务会变化，请在使用前验证来源和可用性。

## 本章完成结果

你现在拥有：

- 一个可编辑的 `deepagents/research` 项目
- 一套由 `.agentseek/lifecycle.toml` 声明的本地开发流程
- 可通过 `agentseek doctor` 检查、由 `agentseek dev` 启动的前后端
- 如果启用了 LangSmith，一条可供下一章分析的真实研究 Trace

下一章将为编码助手安装 `langchain-dev-guide` 和 `langsmith-trace`，帮助你继续修改和调试这个项目。

参考来源：[AgentSeek 快速开始](https://github.com/ob-labs/agentseek/blob/main/docs/get-started/index.zh.md)、[CLI 参考](https://github.com/ob-labs/agentseek/blob/main/docs/reference/cli.zh.md)、[deepagents/research 模板](https://github.com/ob-labs/agentseek/tree/main/templates/deepagents/research)、[SiliconFlow OpenAI 兼容配置](https://docs.siliconflow.cn/cn/usercases/use-siliconcloud-in-KiloCode)、[LangSmith Tracing Quickstart](https://docs.langchain.com/langsmith/observability-quickstart)。
