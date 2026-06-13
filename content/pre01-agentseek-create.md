# AgentSeek CLI（上）— 用 create 命令快速搭建模板应用

## 什么是 AgentSeek CLI

AgentSeek 是一个智能体工程化套件（Agent Engineering Toolkit），提供从脚手架搭建到部署的完整项目生命周期管理。它的专属命令行工具 **AgentSeek CLI** 是统一的操作入口。

安装完成后，运行 `agentseek --help` 可以看到完整的命令结构：

```
Usage: agentseek [OPTIONS] COMMAND [ARGS]...

AgentSeek project-lifecycle CLI. Scaffold, run, build, deploy, manage API
services, skills, and context.

╭─ Options ─────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                       │
╰───────────────────────────────────────────────────────────────────╯
╭─ Environment ─────────────────────────────────────────────────────╮
│ version  Show version information.                                │
╰───────────────────────────────────────────────────────────────────╯
╭─ Project ─────────────────────────────────────────────────────────╮
│ create   Create a new agent project from a pre-built template.    │
│ run      Start the project locally after completing .env config.  │
│ build    Build the project into a container image.                │
│ deploy   Generate deployment manifests (docker-compose / k8s).    │
╰───────────────────────────────────────────────────────────────────╯
╭─ Services ────────────────────────────────────────────────────────╮
│ api      Forward API runtime commands to `agentseek-api`.         │
│ ctx      ContextSeek — semantic context layer.                    │
│ skills   Manage agent skills via the upstream skills CLI.         │
╰───────────────────────────────────────────────────────────────────╯
```

本章聚焦 **Project** 分组中最常用的功能：**`agentseek create`**。

## 环境准备

### 前置要求

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.12+ | 需要现代 Python 特性支持 |
| uv | 最新版 | Python 包管理器，推荐统一使用 |
| Node.js | 18+ | 仅在运行含前端的模板时需要 |
| npm | 9+ | 前端依赖安装 |

> 本系列统一使用 [uv](https://docs.astral.sh/uv/) 作为 Python 包管理器。安装方式：
>
> ```bash
> # macOS / Linux
> curl -LsSf https://astral.sh/uv/install.sh | sh
>
> # Windows (PowerShell)
> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
> ```

### 安装 AgentSeek CLI

```bash
uv tool install agentseek-cli
```

安装完成后，验证版本：

```bash
agentseek version
# agentseek-cli 0.0.3
```

## 使用 agentseek create

### 第一步：查看可用模板

在创建之前，先看看线上有哪些模板可供选择：

```bash
agentseek create --list-templates
```

输出（模板列表会持续更新）：

```
  deepagents (3 templates)
  ────────────────────────────────────────────────────────────
    deepagents/content-builder
      DeepAgents content builder with brand memory, skills,
      subagents, image generation, and streamed UI.
    deepagents/default
      Local create_deep_agent runnable bound to agentseek-langchain.
    deepagents/research
      Pure DeepAgents research agent with Tavily search
      and streamed tool/sub-agent UI.

  langchain (4 templates)
  ────────────────────────────────────────────────────────────
    langchain/cli-remote
      Remote LangGraph CLI agent bridged via LangGraphClientRunnable.
    langchain/default
      LangChain create_agent + CopilotKit middleware
      over agentseek-langchain.
    langchain/markdown-messages
      Pure LangChain create_agent + langgraph dev backend,
      useStream + react-markdown frontend.
    langchain/sandbox
      DeepAgents sandbox coding agent with LangSmith sandbox backend.

  bub (2 templates)
  ────────────────────────────────────────────────────────────
    bub/contextseek
      Bub agent with ContextSeek semantic memory layer.
    bub/default
      Lightweight Bub agent: agentseek gateway + CopilotKit frontend.

  Usage:
    agentseek create <type>/<name>    e.g. agentseek create langchain/cli-remote
    agentseek create <type>           use default template for the type
    agentseek create                  interactive selection
```

> 所有模板源码托管在 [AgentSeek 主仓库](https://github.com/ob-labs/agentseek) 的 `templates/` 目录下，欢迎提 [Issue](https://github.com/ob-labs/agentseek/issues) 或 PR 贡献新模板。

### 第二步：创建模板应用

选定模板后，用一条命令创建。我们以 **deepagents/research**（深度研究）为例——这是一个经典的多子 Agent 并行调研场景：

```bash
agentseek create deepagents/research
```

系统会启动交互式引导（基于 Cookiecutter），提示你填写配置项：

```
project_name [deep-research]:           # 项目名称，直接回车用默认值
project_slug [deep_research]:           # 本地目录名
author [Your Name]:                     # 作者名称
model_provider [openai]:                # 模型供应商 (openai/anthropic/google)
model_name [gpt-4.1]:                   # 默认模型
include_frontend [yes]:                 # 是否包含前端演示界面
```

> **快速模式**：如果不想逐项填写，使用 `--no-input` 跳过交互，全部使用默认值：
>
> ```bash
> agentseek create deepagents/research --no-input
> ```

创建完成后，进入项目目录：

```bash
cd deep_research
```

### 第三步：了解项目结构

查看模板生成的文件：

```
.
├── src/                    # 后端 Agent 代码
│   ├── agent.py           # 主 Agent 定义
│   ├── graph.py           # LangGraph 图定义
│   ├── tools.py           # 工具函数
│   └── ...
├── frontend/              # 前端展示界面（Next.js）
│   ├── package.json
│   ├── src/
│   └── ...
├── .env.example           # 环境变量模板
├── langgraph.json         # LangGraph 部署配置
├── pyproject.toml         # Python 项目配置
└── README.md              # 模板使用说明（必读！）
```

两个核心目录：

- **`src/`** — 后端 Agent 逻辑，基于 LangChain + LangGraph
- **`frontend/`** — 前端对话界面，可选，纯后端项目可删除此目录

## 配置环境变量

### 第四步：复制并编辑 .env 文件

```bash
cp .env.example .env
```

打开 `.env` 文件，你会看到如下结构：

```bash
# --- Model + provider connection -------------------------------------------
# 选择一个供应商，只填对应区块即可
AGENTSEEK_MODEL_PROVIDER=openai
AGENTSEEK_MODEL=gpt-4.1-mini

# OpenAI / OpenAI-compatible
OPENAI_API_BASE=
OPENAI_API_KEY=<your-openai-api-key>

# Qwen / DashScope (OpenAI-compatible)
# AGENTSEEK_MODEL_PROVIDER=qwen
# AGENTSEEK_MODEL=qwen3-max
# QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
# QWEN_API_KEY=<your-dashscope-api-key>

# Anthropic
# AGENTSEEK_MODEL_PROVIDER=anthropic
# AGENTSEEK_MODEL=claude-3-5-sonnet-latest
# ANTHROPIC_API_KEY=
# ANTHROPIC_API_URL=

# Gemini / Google
# AGENTSEEK_MODEL_PROVIDER=google_genai
# AGENTSEEK_MODEL=gemini-2.5-pro
# GOOGLE_API_KEY=
# GOOGLE_API_BASE=

# --- Tavily (required for tavily_search) ------------------------------------
# Get a key at https://app.tavily.com — free tier is enough.
TAVILY_API_KEY=<your-tavily-key>

# --- LangSmith (optional, for tracing) --------------------------------------
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your-langsmith-key>
# LANGSMITH_PROJECT=my-custom-project
```

### 配置要点

- **模型供应商**：设置 `AGENTSEEK_MODEL_PROVIDER` 和 `AGENTSEEK_MODEL`，选择一个供应商填写对应 API Key 即可。国内用户推荐使用通义千问（DashScope）。
- **Tavily 搜索 Key**：`deepagents/research` 模板需要网络搜索，在 [app.tavily.com](https://app.tavily.com/) 获取免费 Key。
- **LangSmith Tracing**（强烈推荐）：在 [smith.langchain.com](https://smith.langchain.com/) 注册后，进入 Settings → API Keys 创建 Token 填入即可。个人用户每月 5000 次免费 Trace 额度。

## 运行模板应用

### 第五步：安装依赖

```bash
uv sync
npm install --prefix frontend
```

### 第六步：启动后端

```bash
uv run langgraph dev --port 2024 --no-browser
```

后端默认监听 `http://127.0.0.1:2024`。去掉 `--no-browser` 参数会自动弹出 LangSmith Studio，可在 Studio 中查看 Graph 结构并调试。

### 第七步：启动前端

新开一个终端窗口：

```bash
npm run --prefix frontend dev
```

前端默认监听 `http://127.0.0.1:5174`。

### 第八步：验证前后端连通

打开 `http://127.0.0.1:5174`，尝试提问：

```
Research what LangGraph 1.0 added vs 0.x. Cite sources.
```

你会看到：

1. Agent 自动生成了 **To-Do List**（任务列表）
2. 多个 **Sub-Agent**（子智能体）被并行唤起
3. 每个子任务完成后更新任务状态
4. 最终生成完整的研究报告

## 在 LangSmith 中查看 Trace

此时切换到 [LangSmith](https://smith.langchain.com/) 界面，你可以看到：

- 每一轮对话的完整调用链路
- 每个节点的输入/输出
- 子 Agent 的执行详情
- Tool 调用的参数和返回值
- Token 用量统计

这就是模板默认开启 LangSmith Tracing 的价值——**开箱即用的全链路可观测性**，无需额外配置。


## 常用操作速查

```bash
# 查看所有可用模板
agentseek create --list-templates

# 创建指定模板（交互式）
agentseek create deepagents/research

# 创建指定模板（跳过交互，使用默认值）
agentseek create deepagents/research --no-input

# 安装依赖
uv sync
npm install --prefix frontend

# 启动后端（弹出 LangSmith Studio）
uv run langgraph dev --port 2024

# 启动后端（静默模式）
uv run langgraph dev --port 2024 --no-browser

# 启动前端
npm run --prefix frontend dev
```

## 小结

本章你学会了：

1. 安装 AgentSeek CLI（`uv tool install agentseek-cli`）
2. 查看可用模板（`agentseek create --list-templates`）
3. 一条命令创建模板应用（`agentseek create deepagents/research`）
4. 配置环境变量（模型 Key + 搜索 Key + LangSmith Key）
5. 前后端联调运行
6. 在 LangSmith 中查看完整的 Agent 执行链路

如果在使用过程中遇到问题，欢迎到 [GitHub Issues](https://github.com/ob-labs/agentseek/issues) 提交反馈。

下一章我们将学习 AgentSeek CLI 的另一个核心功能——**`agentseek skills`**：当你基于模板开始定制开发时，如何通过安装开发技能来获得 AI 编码助手的专业指导。
