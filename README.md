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
> 部分进阶功能有更高最低版本要求，章节正文会单独标注；例如 `FilesystemPermission` 基础权限需要 `deepagents>=0.5.2`，`FilesystemBackend` 的 `virtual_mode` 参数需要 `deepagents>=0.5.0`，`interrupt` 权限模式需要 `deepagents>=0.6.8`。
> 官方文档：[Deep Agents Overview](https://docs.langchain.com/oss/python/deepagents/overview)

> [!NOTE]
> **🤖 模型选择**：示例默认通过 [硅基流动](https://cloud.siliconflow.cn/i/Fq9zUwPf) 接入模型。建议用 `MODEL_NAME` 环境变量管理模型名，而非写死在代码里；平台模型会不定期上下线，最新可用模型见 [模型广场](https://cloud.siliconflow.cn/models)。
>
> - **入门 / 简单任务** — 免费的 `Qwen/Qwen2.5-7B-Instruct` 即可跑通；如果想用更强一点、同时控制成本，`deepseek-ai/DeepSeek-V4-Flash` 也适合作为快速试跑的选择。
> - **复杂场景**（任务规划、上下文总结、多子 Agent 编排）— 小模型往往**无法稳定跑通**，需改用 SOTA 模型：
>   - `Pro/zai-org/GLM-5.1` — 智谱旗舰，Agent 任务同类最佳

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

- [`agentseek create` 搭建模板应用](https://datawhalechina.github.io/deepagents-in-action/chapters/pre01-agentseek-create/)：拉取预制模板并前后端联调运行
- [`agentseek skills` 安装开发技能](https://datawhalechina.github.io/deepagents-in-action/chapters/pre02-agentseek-skills/)：为 AI 编码助手加载 LangChain 工程经验

### 认知篇

| 章节 | 标题 |
|------|------|
| 第 1 章 | [从 Agent Framework 到 Agent Harness — Deep Agents 的诞生逻辑](https://datawhalechina.github.io/deepagents-in-action/chapters/ch01-agent-harness/) |
| 第 2 章 | [快速上手 — 5 分钟构建你的第一个 Deep Agent](https://datawhalechina.github.io/deepagents-in-action/chapters/ch02-quickstart/) |

### 核心篇

| 章节 | 标题 |
|------|------|
| 第 3 章 | [虚拟文件系统 — Deep Agents 的 Context Engineering 核心](https://datawhalechina.github.io/deepagents-in-action/chapters/ch03-virtual-filesystem/) |
| 第 4 章 | [任务规划与分解 — 让 Agent 学会拆解复杂任务](https://datawhalechina.github.io/deepagents-in-action/chapters/ch04-task-planning/) |
| 第 5 章 | [子 Agent 与上下文隔离 — 让 Agent 学会委派](https://datawhalechina.github.io/deepagents-in-action/chapters/ch05-subagents/) |
| 第 6 章 | [异步子 Agent — 让主 Agent 同时驱动多个子任务](https://datawhalechina.github.io/deepagents-in-action/chapters/ch06-async-subagents/) |

### 进阶篇

| 章节 | 标题 |
|------|------|
| 第 7 章 | [Skills — 可复用的 Agent 能力包](https://datawhalechina.github.io/deepagents-in-action/chapters/ch07-skills/) |
| 第 8 章 | [长期记忆 — 让 Agent 拥有跨对话的记忆](https://datawhalechina.github.io/deepagents-in-action/chapters/ch08-long-term-memory/) |
| 第 9 章 | [Human-in-the-Loop — 构建安全的人机协作流程](https://datawhalechina.github.io/deepagents-in-action/chapters/ch09-human-in-the-loop/) |

后续还有沙箱执行等进阶内容，以及实战篇（流式前端、数据分析 Agent、生产部署）正在规划中，持续更新。

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
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=datawhalechina/deepagents-in-action&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=datawhalechina/deepagents-in-action&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=datawhalechina/deepagents-in-action&type=date&legend=top-left" />
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
