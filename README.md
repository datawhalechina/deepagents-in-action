<div align="center">

# 《Deep Agents 实战》

**基于 LangChain / LangGraph 生态，系统构建生产级 AI Agent**

[![Bilibili](https://img.shields.io/badge/视频合集-B站-00A1D6?logo=bilibili&logoColor=white)](https://space.bilibili.com/28357052/lists/7757577?type=season)
[![小红书](https://img.shields.io/badge/图文合集-小红书-FF2442?logo=xiaohongshu&logoColor=white)](https://www.xiaohongshu.com/collection/item/69c4fd2a0072000000000001?xhsshare=&appuid=65032a0300000000120065e8&apptime=1778152909&share_id=2abb593f301a4e60a6e71fbbee3c8967)
[![Deep Agents](https://img.shields.io/badge/Deep%20Agents-≥%200.5-1C3C3C?logo=langchain&logoColor=white)](https://docs.langchain.com/oss/python/deepagents/overview)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/内容协议-CC%20BY--NC--SA%204.0-lightgrey)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

<br/>

由 **[沧海九粟](https://space.bilibili.com/28357052)** 出品 &nbsp;·&nbsp; LangChain 官方认证大使 &nbsp;·&nbsp; 《LangChain 实战》《LangGraph 实战》作者 &nbsp;·&nbsp; B 站万粉 UP 主

</div>

---

> [!NOTE]
> 本课程讲授的 Deep Agents 版本为 **≥ 0.5**。
> 官方文档：[Deep Agents Overview](https://docs.langchain.com/oss/python/deepagents/overview)

---

## 课程大纲

已发布章节：

| 章节 | 标题 |
|------|------|
| 第 1 章 | 从 Agent Framework 到 Agent Harness — Deep Agents 的诞生逻辑 |
| 第 2 章 | 快速上手 — 5 分钟构建你的第一个 Deep Agent |
| 第 3 章 | 虚拟文件系统 — Deep Agents 的 Context Engineering 核心 |
| 第 4 章 | 任务规划与分解 — 让 Agent 学会拆解复杂任务 |
| 第 5 章 | 子 Agent 与上下文隔离 — 让 Agent 学会委派 |
| 第 6 章 | 异步子 Agent — 让主 Agent 同时驱动多个子任务 |

后续还有更多主题正在规划中，涵盖长期记忆、Human-in-the-Loop、Skills、沙箱执行、流式前端、实战项目与生产部署，持续更新中。

---

## 配套资源

- **视频合集**：[B 站 — 《Deep Agents 实战》合集](https://space.bilibili.com/28357052/lists/7757577?type=season)
- **图文合集**：[小红书 — 《Deep Agents 实战》合集](https://www.xiaohongshu.com/collection/item/69c4fd2a0072000000000001?xhsshare=&appuid=65032a0300000000120065e8&apptime=1778152909&share_id=2abb593f301a4e60a6e71fbbee3c8967)
- **课程网站**：部署在 GitHub Pages

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
deepagents-site/
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
网站源代码采用 [MIT](LICENSE) 协议。

---

## 贡献者墙

<!-- contributors:start -->
<table>
<tr>
<td align="center" valign="top" width="120">
  <a href="https://github.com/webup">
    <img src="https://avatars.githubusercontent.com/u/2936504?v=4&s=144" width="72" height="72" alt="webup" style="border-radius:50%;" /><br />
    <sub><strong>webup</strong></sub>
  </a><br />
  <sub>16 commits</sub>
</td>
<td align="center" valign="top" width="120">
  <a href="https://github.com/codeMonkeyWang">
    <img src="https://avatars.githubusercontent.com/u/3906539?v=4&s=144" width="72" height="72" alt="codeMonkeyWang" style="border-radius:50%;" /><br />
    <sub><strong>codeMonkeyWang</strong></sub>
  </a><br />
  <sub>1 commit</sub>
</td>
</tr>
</table>
<!-- contributors:end -->

---

欢迎提交 PR 修正错别字、改善排版，或参与内容讨论。所有贡献者将登上**贡献者墙**，并获赠 LangChain 官方社区（中国）礼品。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。
