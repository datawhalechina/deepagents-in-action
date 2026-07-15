# AgentSeek 准备篇（下）：为 AI 编码助手安装开发技能

> 完成本章后，Codex、Claude Code 或其他兼容工具可以在当前项目中使用 `langchain-dev-guide` 和 `langsmith-trace`。
>
> 本文命令于 2026-07-15 验证。Skills CLI 会继续更新；请以 `npx skills --help` 的输出为准。

## 两类 Skill 的区别

本章安装的是编码助手开发技能。它们帮助 Codex、Claude Code、Cursor 等工具修改和调试项目。

课程第 7 章介绍的是 DeepAgents 运行时 Skill。运行时 Skill 通过 `create_deep_agent(skills=[...])` 提供给你的 Agent。两者都使用 `SKILL.md`，但服务对象不同：

| 类型 | 使用者 | 安装或加载方式 | 本章是否涉及 |
|------|--------|----------------|--------------|
| 编码助手开发技能 | Codex、Claude Code、Cursor 等 | `npx skills add ...` | 是 |
| DeepAgents 运行时 Skill | 你构建的 Deep Agent | `create_deep_agent(skills=[...])` | 否，见第 7 章 |

## 1. 查看 AgentSeek 开发技能

Skills CLI 通过 npm 运行。先确认 Node.js 和 npm 已安装：

```bash
node --version
npm --version
```

进入上一章生成的项目：

```bash
cd research_deepagent
```

查看 AgentSeek 仓库提供的技能：

```bash
npx skills add ob-labs/agentseek --list
```

仓库里的技能会继续增加，实际清单以命令输出为准。本课程重点使用其中两个：

| Skill | 用途 |
|------|------|
| `langchain-dev-guide` | LangChain、LangGraph 和 DeepAgents 开发指南 |
| `langsmith-trace` | LangSmith Trace 查询与调试流程 |

输出中出现的其他技能与本课程准备流程无关，可以暂时忽略。

## 2. 安装到当前项目

运行以下命令：

```bash
npx skills add ob-labs/agentseek --skill langchain-dev-guide --skill langsmith-trace
```

Skills CLI 会检测本机已有的编码助手。按提示选择 Codex、Claude Code 或你正在使用的工具，并确认安装。

你也可以直接指定工具。安装到 Codex：

```bash
npx skills add ob-labs/agentseek --skill langchain-dev-guide --skill langsmith-trace --agent codex --yes
```

安装到 Claude Code：

```bash
npx skills add ob-labs/agentseek --skill langchain-dev-guide --skill langsmith-trace --agent claude-code --yes
```

本章使用项目级安装，不加 `--global`。技能只作用于当前项目，也更方便你在安装后先检查内容，再决定是否把它们纳入版本管理。

## 3. 检查安装位置

列出当前项目和用户目录中的已安装技能：

```bash
npx skills list
```

不同编码助手读取不同目录：

| 编码助手 | 项目级目录 | 全局目录 |
|----------|------------|----------|
| Codex | `.agents/skills/` | `~/.agents/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.agents/skills/` | `~/.agents/skills/` |

项目级安装是默认行为。`--global` 会写入用户级目录，不会写入当前项目的 `.agents/skills/`。

如果你选择了 Codex，可以检查技能入口：

```bash
ls .agents/skills/langchain-dev-guide/SKILL.md
ls .agents/skills/langsmith-trace/SKILL.md
```

如果你选择了 Claude Code，请把路径替换为 `.claude/skills/`。

## 4. 使用 langchain-dev-guide

`langchain-dev-guide` 汇总了 LangChain 生态开发中容易出现的配置和运行问题，主要覆盖：

- DeepAgents 模型、文件系统、子 Agent 和长期记忆
- OpenAI 兼容接口与国产模型接入
- Middleware、流式输出和多 Agent 编排
- 结构化输出、Tool Call 和运行时上下文问题

在编码助手中输入一个具体任务，并明确提到技能名称：

```text
请使用 langchain-dev-guide 检查这个 deepagents/research 项目的模型配置。
本课程默认通过 SiliconFlow 的 OpenAI 兼容接口使用 GLM。
请核对环境变量，并说明 Tool Call、reasoning_content 等能力的兼容性边界。
```

编码助手应该先读取 `langchain-dev-guide/SKILL.md`，再按需读取它引用的资料。你可以要求助手说明它使用了哪个参考文件，以确认技能已经生效。

另一个示例：

```text
请使用 langchain-dev-guide，为这个研究 Agent 添加自定义 Middleware。
先检查 Middleware 执行顺序和 state_schema 合并规则，再给出修改方案。
```

## 5. 实操：用 langsmith-trace 定位一次慢调用（5–10 分钟）

本节使用上一章 `deepagents/research` 生成的 Trace。完成后，你应该能指出研究过程慢在哪里、判断依据是什么，以及下一步如何优化。

开始前确认：

- 上一章已经启用 `LANGSMITH_TRACING=true`
- `.env` 中已经设置 `LANGSMITH_API_KEY` 和 `LANGSMITH_PROJECT=deepagents-course`
- `deepagents-course` 或 `default` 中至少有一条已完成的 `research` Trace
- 当前项目已经安装 `langsmith-trace`

### 5.1 检查 CLI 和认证

先确认 LangSmith CLI 是否可用：

```bash
command -v langsmith
langsmith --version
```

如果命令不存在，请让编码助手使用 `langsmith-trace` 中的安装步骤，不要自行猜测安装命令。

LangSmith CLI 从环境变量读取凭证。请在项目根目录加载 `.env`：

```bash
set -a
source .env
set +a
```

确认凭证有效，并找到最近有运行记录的项目：

```bash
langsmith --format pretty project list
```

你应该能在列表中找到 `deepagents-course`。如果最近的 `research` Trace 已经进入 `default`，可以把后续命令中的项目名换成 `default`，直接分析已有 Trace。`LANGSMITH_PROJECT` 只影响未来运行；只有两个项目中都没有已完成的 `research` Trace 时，才需要修正配置并重新运行研究问题。

不要把真实 Key 写进 Shell 命令，也不要使用 `--api-key`。命令可能进入 Shell 历史、进程列表或编码助手日志。

### 5.2 找到完整 Trace

先列出最近的根 Trace：

```bash
langsmith trace list --project deepagents-course --name research --include-metadata --limit 5
```

复制最新、状态已完成的 `research` 根节点 `trace_id`，再查看完整运行树：

```bash
langsmith trace get <trace-id> --project deepagents-course --include-metadata
```

`<trace-id>` 是占位符，请替换为上一步返回的真实 ID。你会看到根 `research`、`research-agent` 子 Agent、`ChatOpenAI` 模型调用、`tavily_search` 工具调用，以及多层 middleware 包装。

### 5.3 让编码助手分析瓶颈

在 Codex、Claude Code 或其他已安装技能的编码助手中输入：

```text
请使用 langsmith-trace 分析刚才确认的 LangSmith 项目中最近一次已完成的 research Trace。
优先使用 deepagents-course；如果该 Trace 在 default，就使用 default。

请先确认项目和 trace_id，再区分：
1. 根 research 流程；
2. research-agent 子 Agent；
3. run_type=llm 的实际模型调用；
4. tavily_search 等实际工具调用。

分别找出最慢的叶子模型调用和最慢的实际工具调用。
不要把根 Trace、task 子 Agent 包装或 middleware 包装层直接当成瓶颈。
对候选 Run 使用 run get --include-io 检查输入、输出和错误。

最后输出表格：调用、类型、耗时、判断证据、可能原因、下一步建议。
不要输出 API Key 或其他凭证。
```

技能应该先按类型缩小范围，不要一次输出所有 Run 的输入输出：

```bash
langsmith run list --trace-ids <trace-id> --project deepagents-course --run-type llm --include-metadata --limit 100
langsmith run list --trace-ids <trace-id> --project deepagents-course --run-type tool --include-metadata --limit 100
```

LangSmith API 当前允许的单次 `run list` 上限是 100。复杂研究 Trace 可能超过这个数量；先用 `--run-type` 过滤，必要时再用 `--name` 缩小范围，避免截断结果或向终端输出大量 IO。工具结果中的 `task` 是子 Agent 包装，不要把它当成实际工具瓶颈。完整层级仍以 `trace get` 为准。

找到候选 `run_id` 后，明确使用 `--include-io` 查看单次调用：

```bash
langsmith run get <run-id> --include-io --include-metadata
```

不要用 `run get --full` 代替。部分 CLI 版本中，`--full` 可能返回空的输入输出；显式使用 `--include-io` 更稳定。

### 5.4 检查分析结果

一次合格的分析至少包含：

| 检查项 | 完成标准 |
|--------|----------|
| Trace 选择 | 使用最近一次已完成的 `research` Trace |
| 层级区分 | 能区分根流程、子 Agent、模型和工具 |
| 模型瓶颈 | 找到最慢的 `run_type=llm` 叶子 Run |
| 工具瓶颈 | 找到最慢的实际工具 Run，例如 `tavily_search` |
| 证据 | 给出 `run_id`、耗时、状态以及输入输出检查结果 |
| 建议 | 建议与证据对应，而不是只说“换更快模型” |

本文实测的研究 Trace 包含 162 个 Run，0 个错误，总耗时约 472.9 秒。按类型查询全部 22 个模型 Run 后，最慢的叶子 `ChatOpenAI` 调用约 85.9 秒；查询全部 17 个工具 Run 并排除 `task` 包装后，最慢的实际工具是约 25.1 秒的 `tavily_search`。你的结果会随模型、网络、问题和模板版本变化，不要把这些数字写成固定预期。

Trace 可能保存提示词、工具参数和模型输出。如果你处理敏感数据，可以设置 `LANGSMITH_HIDE_INPUTS=true` 和 `LANGSMITH_HIDE_OUTPUTS=true`；启用后，本节用于分析内容的 Run 输入输出会被隐藏。

## 6. 更新技能

只更新当前项目中的技能：

```bash
npx skills update -p
```

如果你以后使用了全局安装，只更新全局技能：

```bash
npx skills update -g
```

更新后再次运行：

```bash
npx skills list
```

## 7. 可选：安装到用户目录

如果你希望在所有项目中使用这两个技能，可以执行：

```bash
npx skills add ob-labs/agentseek --skill langchain-dev-guide --skill langsmith-trace --global
```

全局安装适合个人长期使用。团队项目仍建议保留项目级安装，让项目需要的技能可以被其他成员发现。

## 移除技能

不再需要这些项目级技能时，可以移除：

```bash
npx skills remove langchain-dev-guide langsmith-trace --yes
```

## 本章完成结果

你现在拥有：

- 安装在当前项目中的 `langchain-dev-guide` 和 `langsmith-trace`
- 一套检查、更新和移除开发技能的命令
- 区分编码助手技能与 DeepAgents 运行时 Skill 的清晰边界

接下来，你可以让编码助手使用这两个技能修改上一章生成的研究应用，或继续学习第 7 章的 DeepAgents 运行时 Skills。

参考来源：[AgentSeek Skills](https://github.com/ob-labs/agentseek/tree/main/skills)、[Skills CLI](https://github.com/vercel-labs/skills)、[langchain-dev-guide](https://github.com/ob-labs/agentseek/tree/main/skills/langchain-dev-guide)、[langsmith-trace](https://github.com/ob-labs/agentseek/tree/main/skills/langsmith-trace)、[LangSmith CLI](https://docs.langchain.com/langsmith/langsmith-cli)、[LangSmith 数据脱敏](https://docs.langchain.com/langsmith/mask-inputs-outputs)。
