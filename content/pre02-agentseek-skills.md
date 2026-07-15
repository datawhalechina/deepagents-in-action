# AgentSeek 准备篇（下）：为 AI 编码助手安装开发技能

> 完成本章后，Codex、Claude Code 或其他兼容工具可以在当前项目中使用 `langchain-dev-guide` 和 `langsmith-trace`。
>
> 本文命令于 2026-07-15 验证。Skills CLI 会继续更新；请以 `npx skills --help` 的输出为准。
>
> **视频说明**：页面中的视频录制于旧版 `agentseek skills` 命令。新版安装流程以本文为准，视频将在重新录制后更新。

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

仓库里的技能会继续增加，实际清单以命令输出为准。本课程只需要其中两个：

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
我准备接入一个 OpenAI 兼容服务，请指出需要修改的环境变量和常见错误。
```

编码助手应该先读取 `langchain-dev-guide/SKILL.md`，再按需读取它引用的资料。你可以要求助手说明它使用了哪个参考文件，以确认技能已经生效。

另一个示例：

```text
请使用 langchain-dev-guide，为这个研究 Agent 添加自定义 Middleware。
先检查 Middleware 执行顺序和 state_schema 合并规则，再给出修改方案。
```

## 5. 使用 langsmith-trace

`langsmith-trace` 教编码助手安装 LangSmith CLI、查询项目和 Trace，并检查每个 Run 的输入、输出和耗时。

在上一章成功运行并开启 LangSmith Trace 后，可以输入：

```text
请使用 langsmith-trace 分析 deepagents-course 项目最近一次 Trace。
找出耗时最长的模型或工具调用，并说明判断依据。
```

技能会引导编码助手完成以下流程：

1. 使用 `langsmith project list` 确认项目名称
2. 使用 `langsmith trace list` 找到最近的 Trace
3. 使用 `langsmith trace get` 查看完整运行树
4. 使用 `langsmith run list` 或 `langsmith run get` 检查输入、输出和耗时

LangSmith CLI 从环境变量读取凭证。先把 Key 写入上一章创建、且不会提交到 Git 的 `.env`：

```dotenv
LANGSMITH_API_KEY=replace-with-your-langsmith-api-key
```

再从项目根目录加载这个文件：

```bash
set -a
source .env
set +a
```

不要把真实 Key 直接写进 Shell 命令，也不要使用 `--api-key`。命令内容可能进入 Shell 历史、进程列表或编码助手日志。

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

参考来源：[AgentSeek Skills](https://github.com/ob-labs/agentseek/tree/main/skills)、[Skills CLI](https://github.com/vercel-labs/skills)、[langchain-dev-guide](https://github.com/ob-labs/agentseek/tree/main/skills/langchain-dev-guide)、[langsmith-trace](https://github.com/ob-labs/agentseek/tree/main/skills/langsmith-trace)。
