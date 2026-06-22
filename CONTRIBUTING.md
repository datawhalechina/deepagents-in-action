# 贡献指南

感谢你对《Deep Agents 实战》课程网站的关注！  
无论是修正一个错别字，还是改善一段表述，每一份贡献都很有价值。

---

## 欢迎的贡献类型

- **错别字 / 标点修正**：直接提 PR，无需提前开 Issue
- **表述改善**：措辞不清晰、语句不通顺、逻辑跳跃，欢迎优化
- **排版修复**：代码块格式、列表缩进、图片说明等
- **事实性勘误**：技术描述有误，请附上参考链接
- **问题反馈**：通过 Issue 提问或讨论，欢迎讲解某个知识点不清楚

暂不接受：
- 大幅改写已发布章节的内容结构（请先开 Issue 讨论）
- 添加全新章节（内容由作者统一规划）

---

## 快速上手

### 1. Fork 并克隆仓库

```bash
git clone https://github.com/<your-username>/deepagents-in-action.git
cd deepagents-in-action
```

### 2. 安装依赖并启动开发服务器

```bash
npm install
npm run dev
```

开发服务器默认运行在 `http://localhost:4321`。

### 3. 找到要修改的文件

**章节正文** 在 `content/` 目录下，每章对应一个 Markdown 文件：

```
content/
├── pre01-agentseek-create.md
├── pre02-agentseek-skills.md
├── ch01-agent-harness.md
├── ch02-quickstart.md
├── ...
└── ch08-long-term-memory.md
```

**章节元数据**（标题、发布日期、视频链接）在 `scripts/chapters.json`。

> 注意：`src/content/chapters/` 是自动生成的，**不要直接编辑**这里的文件。

### 4. 修改并预览

编辑 `content/` 下的 `.md` 文件后，开发服务器会自动热重载。  
请在浏览器中确认修改效果正常。

### 5. 提交 PR

```bash
git checkout -b fix/typo-ch01
git add content/ch01-agent-harness.md
git commit -m "fix: 修正第 1 章若干错别字"
git push origin fix/typo-ch01
```

然后在 GitHub 上提交 Pull Request，PR 标题格式：

```
fix: 修正第 X 章 <简要说明>
docs: 改善第 X 章 <简要说明>
```

---

## Markdown 写作规范

- 中文与英文、数字之间加空格：`LangChain 是一个框架` ✓，`LangChain是一个框架` ✗
- 代码、命令、变量名使用反引号包裹：`` `create_deep_agent()` ``
- 专有名词保持原文大小写：`LangGraph`、`LangSmith`、`GitHub`
- 图片路径使用相对路径：`![说明](../public/imgs/xx.png)`（构建脚本会自动转换为正确的站点路径）

---

## 本地开发说明

### 内容预处理

运行 `npm run dev` 时会自动执行 `scripts/prep-content.mjs`，  
它读取 `scripts/chapters.json` 中的元数据，为 `content/` 下的 Markdown 注入 frontmatter，  
生成到 `src/content/chapters/`（已加入 `.gitignore`，无需提交）。

### 文件不要提交

以下目录已在 `.gitignore` 中，请勿手动提交：

- `src/content/chapters/`（自动生成）
- `dist/`（构建产物）
- `node_modules/`

---

## 提问与讨论

- **课程内容问题**：请在 GitHub Issues 中提问，或在对应 B 站视频评论区留言
- **网站 Bug**：请开 Issue 描述复现步骤

## 贡献者致谢

所有合并的 PR 贡献者将会：

- 出现在课程网站的**特别感谢**中
- 收到来自 **LangChain 官方社区（中国）** 的实体礼品一份

再次感谢你的贡献！🙏
