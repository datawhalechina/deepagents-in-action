<div align="center">

# Deep Agents 实战

<p>
  <a href="https://datawhalechina.github.io/deepagents-in-action/">
    <img src="public/imgs/hero.png" alt="Deep Agents 实战 — 基于 LangChain / LangGraph 的中文开源课程，感谢 2,000+ GitHub Stars" width="800" />
  </a>
</p>

[![在线阅读](https://img.shields.io/badge/在线阅读-B8860B?style=for-the-badge&logo=readthedocs&logoColor=white)](https://datawhalechina.github.io/deepagents-in-action/)
[![B 站视频](https://img.shields.io/badge/B站视频-00A1D6?style=for-the-badge&logo=bilibili&logoColor=white)](https://space.bilibili.com/28357052/lists/7757577?type=season)
[![小红书图文](https://img.shields.io/badge/小红书图文-FF2442?style=for-the-badge&logo=xiaohongshu&logoColor=white)](https://www.xiaohongshu.com/collection/item/69c4fd2a0072000000000001?xhsshare=&appuid=65032a0300000000120065e8&apptime=1778152909&share_id=2abb593f301a4e60a6e71fbbee3c8967)

[![Deep Agents](https://img.shields.io/badge/Deep%20Agents-0.5%20%E2%86%92%200.7-1C3C3C?logo=langchain&logoColor=white)](https://docs.langchain.com/oss/python/deepagents/overview)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/内容协议-CC%20BY--NC--SA%204.0-lightgrey)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

作者：**[沧海九粟](https://space.bilibili.com/28357052)** · LangChain 官方认证大使 · [LCAE 认证](https://certs.langchain.com/93ab2ac4-e237-4415-bcc8-46b27741f75a)

</div>

基于 LangChain / LangGraph 的中文开源课程，配套 **16 章图文、视频与实验模板**。从第一个 Agent 开始，逐步掌握任务规划、文件系统、子 Agent 协作与上下文管理。

**从这里开始：** [环境准备](https://datawhalechina.github.io/deepagents-in-action/chapters/pre01-agentseek-create/) → [5 分钟上手](https://datawhalechina.github.io/deepagents-in-action/chapters/ch02-quickstart/) → [课程大纲](#课程大纲)

> [!NOTE]
> 课程从 0.5 起步，当前推荐使用最新的 **Deep Agents 0.7.x**。从 0.5 / 0.6 升级的读者，请先阅读 [v0.7 版本更新与迁移指南](https://datawhalechina.github.io/deepagents-in-action/chapters/release-v0-7/)。

<details>
<summary>版本要求与模型配置</summary>

旧章节和图片保留了当时的默认行为，紧邻它们的“v0.7 提醒”代表当前用法。进阶与 Beta 功能的依赖要求以各章说明为准。

| 功能 | 版本要求 |
| --- | --- |
| `FilesystemPermission` 基础权限 / `interrupt` 模式 | 分别需要 `deepagents>=0.5.2` / `deepagents>=0.6.8` |
| 第 13 章：`RubricMiddleware`（Beta） | 章节以 `deepagents==0.7.1` 验证 |
| 第 14 章：Event Streaming v3 | `deepagents>=0.6` |
| 第 15 章：Interpreters（Beta） | Python 3.11+、`langchain-quickjs>=0.2.0` |

示例默认通过 [硅基流动](https://cloud.siliconflow.cn/i/Fq9zUwPf) 接入支持工具调用的模型，使用 `MODEL_NAME` 环境变量配置模型名。小模型可用于简单试跑；任务规划、上下文总结和多 Agent 编排需要更强的模型能力。

模型可用性、价格与免费额度会调整，使用前请查阅 [模型广场](https://cloud.siliconflow.cn/models)、[价格页](https://siliconflow.cn/pricing)和[更新公告](https://api-docs.siliconflow.cn/docs/release-notes/overview)。框架说明见 [Deep Agents 官方文档](https://docs.langchain.com/oss/python/deepagents/overview)。

</details>

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

### 版本更新 — 理解变化，再决定如何升级

版本更新不按功能逐条抄录，而是解释默认行为为什么改变、哪些应用会受影响，以及如何用评测和 Trace 验证迁移结果：

- [Deep Agents v0.7：更轻、更透明、更可配置的 Harness](https://datawhalechina.github.io/deepagents-in-action/chapters/release-v0-7/)：正确理解 65% 基础输入 Token 降幅，判断是否恢复 Todo，掌握 Middleware 原位覆盖、文件工具语义变化与 v0.6→v0.7 迁移路径。

如果你从 0.5 或 0.6 一路学到这里，建议先读更新章，再升级依赖和重跑原有实验。v0.7 的默认 Harness 更轻，通用提示词不再重复占用每轮输入；Todo 从固定成本变成按任务选择；Middleware 可以在原位置换；文件工具新增删除能力，并明确覆盖、分页和截断语义。官方给出的 65% 是简单回合的基础输入降幅，不代表每个应用的总成本都会下降 65%。

### 按章节开始实验

每章下方列出实验目标和模板。第 6、8、9、11 章需按正文补充能力；第 15、16 章共用的 `deepagents/subagents-dynamic` 已合并至 `main`，可直接创建。

<details>
<summary>创建与启动模板（所有章节通用）</summary>

安装 AgentSeek，将下面的 `deepagents/default` 替换为对应章节的模板名：

```bash
uv tool install --upgrade agentseek
agentseek create deepagents/default --checkout main --no-input
```

进入生成目录，查看可用任务，按项目 README 安装依赖并配置 `.env`，然后检查环境、启动应用：

```bash
agentseek task --list
# 完成依赖安装与 .env 配置后
agentseek doctor
agentseek dev
```

用 `agentseek create --list-templates --checkout main` 查看全部模板。需要固定实验环境时，将 `main` 换为完整提交 SHA。

</details>

### 认知篇

#### 第 1 章：[从 Agent Framework 到 Agent Harness — Deep Agents 的诞生逻辑](https://datawhalechina.github.io/deepagents-in-action/chapters/ch01-agent-harness/)

辨清 Runtime、Framework 与 Harness。模板：[`deepagents/default`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/default)

#### 第 2 章：[快速上手 — 5 分钟构建你的第一个 Deep Agent](https://datawhalechina.github.io/deepagents-in-action/chapters/ch02-quickstart/)

修改提示词和工具，跑通第一个 Agent。模板：[`deepagents/default`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/default)

### 核心篇

#### 第 3 章：[虚拟文件系统 — Deep Agents 的 Context Engineering 核心](https://datawhalechina.github.io/deepagents-in-action/chapters/ch03-virtual-filesystem/)

观察文件系统如何保存内容与中间结果。模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)

#### 第 4 章：[任务规划与分解 — 让 Agent 学会拆解复杂任务](https://datawhalechina.github.io/deepagents-in-action/chapters/ch04-task-planning/)

显式启用 Todo，观察任务计划与状态变化。模板：[`deepagents/research`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)

#### 第 5 章：[子 Agent 与上下文隔离 — 让 Agent 学会委派](https://datawhalechina.github.io/deepagents-in-action/chapters/ch05-subagents/)

观察子任务委派与上下文隔离。模板：[`deepagents/research`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)

#### 第 6 章：[异步子 Agent — 让主 Agent 同时驱动多个子任务](https://datawhalechina.github.io/deepagents-in-action/chapters/ch06-async-subagents/)

按正文接入 `AsyncSubAgent`，运行异步子任务。模板：[`deepagents/research`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)

### 进阶篇

#### 第 7 章：[Skills — 可复用的 Agent 能力包](https://datawhalechina.github.io/deepagents-in-action/chapters/ch07-skills/)

运行内置 Skills，观察匹配与渐进式加载。模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)

#### 第 8 章：[长期记忆 — 让 Agent 拥有跨对话的记忆](https://datawhalechina.github.io/deepagents-in-action/chapters/ch08-long-term-memory/)

按正文接入 `StoreBackend`，验证跨会话记忆。模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)

#### 第 9 章：[Human-in-the-Loop — 构建安全的人机协作流程](https://datawhalechina.github.io/deepagents-in-action/chapters/ch09-human-in-the-loop/)

按正文为 MCP 工具配置人工审批。模板：[`deepagents/mcp`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/mcp)

#### 第 10 章：[沙箱执行 — 让 Agent 安全地运行代码](https://datawhalechina.github.io/deepagents-in-action/chapters/ch10-sandboxes/)

在沙箱中验证隔离执行与文件读写。模板：[`deepagents/sandbox`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/sandbox)

#### 第 11 章：[文件系统权限 — 用声明式规则控制 Agent 的读写边界](https://datawhalechina.github.io/deepagents-in-action/chapters/ch11-filesystem-permissions/)

按正文配置 `FilesystemPermission`，划分访问边界。模板：[`deepagents/content-builder`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/content-builder)

#### 第 12 章：[MCP — 用标准协议扩展 Deep Agents 工具生态](https://datawhalechina.github.io/deepagents-in-action/chapters/ch12-mcp/)

验证 MCP 工具发现与名称冲突处理。模板：[`deepagents/mcp`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/mcp)

### 前沿预览

#### 第 13 章：[Grading Rubrics（评分量规）— 让 Agent 按验收标准自我迭代](https://datawhalechina.github.io/deepagents-in-action/chapters/ch13-grading-rubrics/)

运行 Guided Demo，观察证据与验收闭环。模板：[`langchain/rubric`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/langchain/rubric)

#### 第 14 章：[Streaming — 实时观察主 Agent、子 Agent 与工具调用](https://datawhalechina.github.io/deepagents-in-action/chapters/ch14-streaming/)

观察 Event Streaming v3 的 Agent 与工具事件流。模板：[`deepagents/streaming`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/streaming)

#### 第 15 章：[Interpreters — 让 Agent 用代码编排工具与数据](https://datawhalechina.github.io/deepagents-in-action/chapters/ch15-interpreters/)

观察 QuickJS `eval` 与 `task()` 动态调度。模板：[`deepagents/subagents-dynamic`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/subagents-dynamic)

#### 第 16 章：[Dynamic Subagents — 用代码编排多个 Agent](https://datawhalechina.github.io/deepagents-in-action/chapters/ch16-dynamic-subagents/)

运行六种编排模式，观察真实调用事件。模板：[`deepagents/subagents-dynamic`](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/subagents-dynamic)

后续课程内容将根据 Deep Agents 的官方能力演进持续更新。

---

## 关于作者

**[沧海九粟](https://space.bilibili.com/28357052)** · LangChain 官方认证大使 · 《LangChain 实战》《LangGraph 实战》作者 · B 站万粉 UP 主。

**专业认证：** [LangChain Certified Agent Engineer（LCAE）](https://certs.langchain.com/93ab2ac4-e237-4415-bcc8-46b27741f75a)

<a href="https://trendshift.io/developers/10200?utm_source=developer-badge&utm_medium=badge&utm_campaign=badge-developer-10200" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/developers/10200" alt="webup | Trendshift" width="250" height="55"/></a>

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
