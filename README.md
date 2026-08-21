<div align="center">

# 《Deep Agents 实战》

**基于 LangChain / LangGraph 生态，系统构建生产级 AI Agent**

[![Bilibili](https://img.shields.io/badge/视频合集-B站-00A1D6?logo=bilibili&logoColor=white)](https://space.bilibili.com/28357052/lists/7757577?type=season)
[![小红书](https://img.shields.io/badge/图文合集-小红书-FF2442?logo=xiaohongshu&logoColor=white)](https://www.xiaohongshu.com/collection/item/69c4fd2a0072000000000001?xhsshare=&appuid=65032a0300000000120065e8&apptime=1778152909&share_id=2abb593f301a4e60a6e71fbbee3c8967)
[![Deep Agents](https://img.shields.io/badge/Deep%20Agents-≥%200.5-1C3C3C?logo=langchain&logoColor=white)](https://docs.langchain.com/oss/python/deepagents/overview)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/内容协议-CC%20BY--NC--SA%204.0-lightgrey)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

<a href="https://trendshift.io/developers/10200?utm_source=developer-badge&utm_medium=badge&utm_campaign=badge-developer-10200" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/developers/10200" alt="webup | Trendshift" width="250" height="55"/></a>

<br/>

由 **[沧海九粟](https://space.bilibili.com/28357052)** 出品 &nbsp;·&nbsp; LangChain 官方认证大使 &nbsp;·&nbsp; 《LangChain 实战》《LangGraph 实战》作者 &nbsp;·&nbsp; B 站万粉 UP 主

<a href="https://datawhalechina.github.io/deepagents-in-action/">
  <img src="public/imgs/hero.png" alt="《Deep Agents 实战》课程网站" width="800" />
</a>

</div>

---

> [!WARNING]
> 本课程讲授的 Deep Agents 版本为 **≥ 0.5**。
> 部分进阶功能有更高最低版本要求，章节正文会单独标注；例如 `FilesystemPermission` 基础权限需要 `deepagents>=0.5.2`，`FilesystemBackend` 的 `virtual_mode` 参数需要 `deepagents>=0.5.0`，`interrupt` 权限模式需要 `deepagents>=0.6.8`。`RubricMiddleware` 仍为 Beta，需要 `deepagents>=0.6.5`，第 13 章以 `deepagents==0.7.1` 验证版本化行为；第 14 章以 `deepagents>=0.6` 引入的 Event Streaming v3 为主线。第 15 章的 Interpreters 仍为 Beta，需要 Python 3.11+ 与 `langchain-quickjs>=0.2.0`。
> 官方文档：[Deep Agents Overview](https://docs.langchain.com/oss/python/deepagents/overview)

> [!NOTE]
> **🤖 模型选择**：示例默认通过 [硅基流动](https://cloud.siliconflow.cn/i/Fq9zUwPf) 接入模型。建议用 `MODEL_NAME` 环境变量管理模型名，而非写死在代码里；平台模型、价格和免费范围会调整，使用前请查看 [模型广场](https://cloud.siliconflow.cn/models)、[价格页](https://siliconflow.cn/pricing)与[更新公告](https://api-docs.siliconflow.cn/docs/release-notes/overview)。
>
> - **入门 / 简单任务** — 当前免费版 `Qwen/Qwen2.5-7B-Instruct` 可用于跑通示例；如果想用更强一点、同时控制成本，`deepseek-ai/DeepSeek-V4-Flash` 也适合作为快速试跑的选择。
> - **复杂场景**（任务规划、上下文总结、多子 Agent 编排）— 小模型往往**无法稳定跑通**，建议改用能力更强、支持工具调用的模型：
>   - `zai-org/GLM-5.2` — 面向长程 Agent 任务，支持 1M 上下文

---

## 课程大纲

### 推荐技能

配合课程学习，推荐安装以下两个 AI 编码助手技能，在开发过程中获得框架级的专业指导：

```bash
# LangChain 开发指南 — 工程陷阱与验证修复
npx skills add ob-labs/agentseek --skill langchain-dev-guide

# LangSmith Trace 调试 — 追踪与性能分析
npx skills add ob-labs/agentseek --skill langsmith-trace
```

> 技能源码：[langchain-dev-guide](https://github.com/ob-labs/agentseek/tree/main/skills/langchain-dev-guide) · [langsmith-trace](https://github.com/ob-labs/agentseek/tree/main/skills/langsmith-trace)

### 准备篇 — 动手实操前的环境搭建与工具安装

基于 [AgentSeek](https://github.com/ob-labs/agentseek) 工程化套件，帮助学员快速搭建开发环境：

- [AgentSeek 生命周期工作流](https://datawhalechina.github.io/deepagents-in-action/chapters/pre01-agentseek-create/)：创建 DeepAgents 模板，检查环境并启动前后端
- [`npx skills` 安装开发技能](https://datawhalechina.github.io/deepagents-in-action/chapters/pre02-agentseek-skills/)：为 AI 编码助手加载 LangChain 工程经验

### 按章节开始实验

已有适配模板的章节卡片会标出 AgentSeek 模板和适配理由；README 也按同样的章节分区列出。第 6、8、9、11 章需要在模板基础上按正文补充本章能力，具体步骤以章节内容为准；第 14 章已经有可直接运行的专用模板。

先升级 AgentSeek，并确认 `main` 分支当前有哪些模板：

```bash
uv tool install --upgrade agentseek
agentseek create --list-templates --checkout main
```

进入生成目录后，所有模板遵循同一套生命周期入口：

```bash
cd <生成的项目目录>
agentseek info
agentseek task --list

# 按 task --list 的输出完成依赖安装，并按项目 README 配置 .env
agentseek doctor
agentseek dev
```

`--checkout main` 用于获取最新批次模板，适合跟课实验；如果需要冻结作业环境，请将 `main` 换成记录下来的完整提交 SHA。

### 认知篇

#### 第 1 章：[从 Agent Framework 到 Agent Harness — Deep Agents 的诞生逻辑](https://datawhalechina.github.io/deepagents-in-action/chapters/ch01-agent-harness/)

- 模板：[`deepagents/default`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/default)
- 实验：从最小 `create_deep_agent` 项目识别 Runtime、Framework 与 Harness 的边界。

```bash
agentseek create deepagents/default --checkout main --no-input
```

#### 第 2 章：[快速上手 — 5 分钟构建你的第一个 Deep Agent](https://datawhalechina.github.io/deepagents-in-action/chapters/ch02-quickstart/)

- 模板：[`deepagents/default`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/default)
- 实验：修改系统提示词和自定义工具，跑通第一个可工作的 Deep Agent。

```bash
agentseek create deepagents/default --checkout main --no-input
```

### 核心篇

#### 第 3 章：[虚拟文件系统 — Deep Agents 的 Context Engineering 核心](https://datawhalechina.github.io/deepagents-in-action/chapters/ch03-virtual-filesystem/)

- 模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)
- 实验：利用现成 `FilesystemBackend` 观察内容、中间结果和 Skills 如何落盘。

```bash
agentseek create deepagents/content-builder --checkout main --no-input
```

#### 第 4 章：[任务规划与分解 — 让 Agent 学会拆解复杂任务](https://datawhalechina.github.io/deepagents-in-action/chapters/ch04-task-planning/)

- 模板：[`deepagents/research`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)
- 实验：通过 Todo 面板观察 `write_todos` 的计划生成与状态变化。

```bash
agentseek create deepagents/research --checkout main --no-input
```

#### 第 5 章：[子 Agent 与上下文隔离 — 让 Agent 学会委派](https://datawhalechina.github.io/deepagents-in-action/chapters/ch05-subagents/)

- 模板：[`deepagents/research`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)
- 实验：观察主 Agent 将搜索委派给 research-agent，并比较两侧上下文。

```bash
agentseek create deepagents/research --checkout main --no-input
```

#### 第 6 章：[异步子 Agent — 让主 Agent 同时驱动多个子任务](https://datawhalechina.github.io/deepagents-in-action/chapters/ch06-async-subagents/)

- 模板：[`deepagents/research`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)
- 实验：从同步研究应用开始，按本章将 researcher 拆成独立 graph 并接入 `AsyncSubAgent`。

```bash
agentseek create deepagents/research --checkout main --no-input
```

### 进阶篇

#### 第 7 章：[Skills — 可复用的 Agent 能力包](https://datawhalechina.github.io/deepagents-in-action/chapters/ch07-skills/)

- 模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)
- 实验：使用内置 blog-post 与 social-media Skills 观察匹配和渐进式加载。

```bash
agentseek create deepagents/content-builder --checkout main --no-input
```

#### 第 8 章：[长期记忆 — 让 Agent 拥有跨对话的记忆](https://datawhalechina.github.io/deepagents-in-action/chapters/ch08-long-term-memory/)

- 模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)
- 实验：从内容应用开始，按本章加入 `CompositeBackend`、`StoreBackend` 和运行时 namespace。

```bash
agentseek create deepagents/content-builder --checkout main --no-input
```

#### 第 9 章：[Human-in-the-Loop — 构建安全的人机协作流程](https://datawhalechina.github.io/deepagents-in-action/chapters/ch09-human-in-the-loop/)

- 模板：[`deepagents/mcp`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/mcp)
- 实验：从 MCP 应用开始，按本章为有副作用的工具配置 `interrupt_on`。

```bash
agentseek create deepagents/mcp --checkout main --no-input
```

#### 第 10 章：[沙箱执行 — 让 Agent 安全地运行代码](https://datawhalechina.github.io/deepagents-in-action/chapters/ch10-sandboxes/)

- 模板：[`deepagents/sandbox`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/sandbox)
- 实验：选择 Daytona 或 LangSmith Sandbox，观察隔离执行、文件读写与清理。

```bash
agentseek create deepagents/sandbox --checkout main --no-input
```

#### 第 11 章：[文件系统权限 — 用声明式规则控制 Agent 的读写边界](https://datawhalechina.github.io/deepagents-in-action/chapters/ch11-filesystem-permissions/)

- 模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)
- 实验：从真实内容目录开始，按本章加入 `FilesystemPermission` 并划分访问边界。

```bash
agentseek create deepagents/content-builder --checkout main --no-input
```

#### 第 12 章：[MCP — 用标准协议扩展 Deep Agents 工具生态](https://datawhalechina.github.io/deepagents-in-action/chapters/ch12-mcp/)

- 模板：[`deepagents/mcp`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/mcp)
- 实验：验证 stdio/HTTP Server、工具发现、稳定前缀与名称冲突。

```bash
agentseek create deepagents/mcp --checkout main --no-input
```

### 前沿预览

#### 第 13 章：[Grading Rubrics（评分量规）— 让 Agent 按验收标准自我迭代](https://datawhalechina.github.io/deepagents-in-action/chapters/ch13-grading-rubrics/)

- 模板：[`langchain/rubric`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/langchain/rubric)
- 实验：先运行无需模型密钥的 Guided Demo，再观察 Evidence 与 Acceptance Gate。

```bash
agentseek create langchain/rubric --checkout main --no-input
```

#### 第 14 章：[Streaming — 实时观察主 Agent、子 Agent 与工具调用](https://datawhalechina.github.io/deepagents-in-action/chapters/ch14-streaming/)

- 模板：[`deepagents/streaming`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/streaming)（由 [agentseek-templates PR #20](https://github.com/agentseek-ai/agentseek-templates/pull/20) 引入）
- 实验：直接运行 Event Streaming v3 应用，观察 coordinator/subagent messages、工具生命周期、状态快照、最终输出和 raw protocol，并核对哪些字段来自官方协议、哪些由模板 adapter 生成。

```bash
agentseek create deepagents/streaming --checkout main --no-input
```

#### 第 15 章：[Interpreters — 让 Agent 用代码编排工具与数据](https://datawhalechina.github.io/deepagents-in-action/chapters/ch15-interpreters/)

- 内容：从纯内存 JavaScript 开始，再通过 PTC 批量读取和筛选订单，理解状态范围、资源预算与安全边界。

后续课程内容将根据 Deep Agents 的官方能力演进持续更新。

---

## 配套资源

- **视频合集**：[B 站 — 《Deep Agents 实战》合集](https://space.bilibili.com/28357052/lists/7757577?type=season)
- **图文合集**：[小红书 — 《Deep Agents 实战》合集](https://www.xiaohongshu.com/collection/item/69c4fd2a0072000000000001?xhsshare=&appuid=65032a0300000000120065e8&apptime=1778152909&share_id=2abb593f301a4e60a6e71fbbee3c8967)
- **课程网站**：部署在 GitHub Pages

---

## 友情链接
由 **[沧海九粟](https://space.bilibili.com/28357052)** 在 DataWhale 上开源的另一门课程，是面向所有 AI 爱好者的 Data 与 AI 基础入门教程 —— [《Easy Data x AI》](https://github.com/datawhalechina/easy-data-x-ai)。目前已经进入了内测阶段，欢迎大家来学习和积极参与共建。

---

## 模型算力支持

<table>
<tr>
<td width="180" align="center" valign="middle">
<a href="https://cloud.siliconflow.cn/i/Fq9zUwPf" target="_blank" rel="noopener">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="public/imgs/siliconflow-dark.svg" />
    <img src="public/imgs/siliconflow.svg" alt="SiliconFlow 硅基流动" width="150" />
  </picture>
</a>
</td>
<td valign="middle">
本课程的模型算力由 <strong><a href="https://cloud.siliconflow.cn/i/Fq9zUwPf">硅基流动（SiliconFlow）</a></strong> 支持。硅基流动是一站式大模型云服务平台，基于自研推理引擎实现大模型高效推理加速，提供高效能、低成本的多品类 AI 模型服务，让开发者和企业聚焦产品创新，无须担心大规模推广带来的高昂算力成本。
</td>
</tr>
</table>

- 🎁 **新用户福利**：通过 [课程专属注册链接](https://cloud.siliconflow.cn/i/Fq9zUwPf) 注册并完成实名认证，即可获得 **16 元全平台通用代金券**，可用于平台上百余种模型的调用，足够跑通本课程的全部示例。
- 🧪 **实验配额补贴池**：用上面的链接注册时，作者也会获得平台返利。这部分返利会**全额回馈给学员**——汇集成一个「实验配额补贴池」：跟着课程做实验、复现示例时如果额度不够用，可以[联系作者](https://space.bilibili.com/28357052)申请额外的算力配额补贴，把福利转回给真正在动手的同学。

---

## ❤️ 特别感谢

- 感谢 [@Sm1les](https://github.com/Sm1les) 对本项目的帮助与支持。
- 感谢每一位为本项目提交代码、修正文档、提出建议的开发者，所有贡献都让这门课程变得更好。❤️

<div align="left">

<a href="https://github.com/datawhalechina/deepagents-in-action/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=datawhalechina/deepagents-in-action" alt="Deep Agents 实战贡献者" />
</a>

</div>

---

## Star History

<a href="https://www.star-history.com/?repos=datawhalechina%2Fdeepagents-in-action&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=datawhalechina/deepagents-in-action&type=date&theme=dark&legend=top-left&sealed_token=mtwEZqXnyl4dS7dntbunJS6paWzuY4nYHRakXExwwhUfgmgAhGfSne4zD1pbE3xskKASHP6zESCxqlrl9SkOYnwu5XnyLmszazov5JUJYDSUMQqJmnZYBw" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=datawhalechina/deepagents-in-action&type=date&legend=top-left&sealed_token=mtwEZqXnyl4dS7dntbunJS6paWzuY4nYHRakXExwwhUfgmgAhGfSne4zD1pbE3xskKASHP6zESCxqlrl9SkOYnwu5XnyLmszazov5JUJYDSUMQqJmnZYBw" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=datawhalechina/deepagents-in-action&type=date&legend=top-left&sealed_token=mtwEZqXnyl4dS7dntbunJS6paWzuY4nYHRakXExwwhUfgmgAhGfSne4zD1pbE3xskKASHP6zESCxqlrl9SkOYnwu5XnyLmszazov5JUJYDSUMQqJmnZYBw" />
 </picture>
</a>

---

## 本地开发

### 环境要求

- Node.js ≥ 22.12.0

### 安装与启动

```bash
# 安装依赖
npm install

# 启动开发服务器（含内容预处理）
npm run dev

# 构建生产版本
npm run build

# 预览构建产物
npm run preview
```

### 项目结构

```
deepagents-in-action/
├── content/          # 章节正文（Markdown，每章一个文件）
│   ├── ch01-agent-harness.md
│   ├── ch02-quickstart.md
│   └── ...
├── public/
│   ├── imgs/         # 正文插图
│   └── pdfs/         # 章节 PDF
├── scripts/
│   ├── chapters.json # 章节元数据（标题、发布状态、视频链接等）
│   └── prep-content.mjs  # 内容预处理脚本（注入 frontmatter）
└── src/
    ├── components/   # Astro 组件
    ├── layouts/      # 页面布局
    └── pages/        # 路由页面
```

### 内容流水线

`content/` 目录中的 Markdown 文件是**源文件**，不含 frontmatter。  
`scripts/prep-content.mjs` 在 `dev` / `build` 前自动运行，从 `scripts/chapters.json` 读取元数据，生成带 frontmatter 的文件到 `src/content/chapters/`。

正文图片统一写成 `../public/imgs/<文件名>`。内容预处理会将它转换为带站点 base 的 `/deepagents-in-action/imgs/<文件名>`；资产校验会同时检查 Markdown 中引用的图片是否真实存在于 `public/imgs/`。

> 注意：`content/` 下 `.md` 文件的首行 H1 标题在生成时会被自动移除，
> 页面标题统一取自 `scripts/chapters.json`。

**添加或修改章节内容，只需编辑 `content/` 目录下对应的 `.md` 文件。**  
**修改标题、发布状态、视频链接等元数据，编辑 `scripts/chapters.json`。**

---

## 技术栈

- [Astro 6](https://astro.build/) — 静态站点框架
- [Tailwind CSS 4](https://tailwindcss.com/) — 样式
- TypeScript

---

## 开源协议

课程文字内容采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh) 协议。  
网站源代码采用 [MIT](https://opensource.org/license/mit) 协议。

---

欢迎提交 PR 修正错别字、改善排版，或参与内容讨论。所有贡献者都会出现在**特别感谢**中，并获赠 LangChain 官方社区（中国）礼品。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。
