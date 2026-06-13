# 首页章节速览侧栏（Chapter Overview Rail）设计

- 日期：2026-06-13
- 状态：已与用户确认，待评审
- 涉及页面：首页 `src/pages/index.astro`

## 1. 背景与目标

社区读者反馈：当前首页把 5 个篇章（共 15 章，已发布 10 章）堆叠成两列高卡片，
需要长距离滚动才能看完所有章节，缺少“一眼纵览 + 快速跳转”的入口。

**核心目标：快速导航 / jump-to。** 让读者在任意滚动位置都能看到课程整体结构，
并一键跳转到任意已发布章节，而不必逐张卡片滚动。

非目标（本次不做）：
- 不重构现有 ChapterCard 卡片网格（卡片内容与样式保持不变）。
- 不引入暗色模式、不新增配色体系。
- 不展示未发布章节（见 §3）。

## 2. 总体方案

在首页内容区左侧新增一条**常驻、安静（low-emphasis）的目录侧栏**，桌面端 sticky 固定、
随滚动高亮当前章节（scrollspy）、点击平滑滚动到对应卡片；移动/平板端折叠为顶部
“课程目录”条 + 点击展开的下拉面板。

采用**两列 grid 包裹**（用户已选方案 A）：
- Hero 与 Footer 保持全宽，位于 grid 之外。
- 章节列表区域用 `lg:grid lg:grid-cols-[210px_minmax(0,1fr)] lg:gap-10` 包裹。
- 第 1 列：侧栏 `<nav>`（`hidden lg:block`，sticky）。
- 第 2 列：现有 `grouped.map(...)` 渲染逻辑，基本不变。
- 容器宽度由 `max-w-5xl` 调整为 `max-w-6xl`，保证内容列不比现在更窄。

## 3. 数据与同步规则

侧栏数据与下方内容列**完全同源、保持一致**：

- 只列出**已发布章节**（`published === true`）。不显示未发布章节，不显示 `⋯` 占位。
- 某篇章**至少有 1 章已发布**时才出现在侧栏（与内容列 `hasPublished ? render : null` 一致）。
  - 因此当前 **实战篇（0 章已发布）不会出现在侧栏**。
- 当前侧栏内容快照：准备篇(2) · 认知篇(2) · 核心篇(4) · 进阶篇(07、08)，共 4 篇 10 项。
- 排序沿用 `order` 字段升序。

锚点：
- 每个篇章标题（SectionHeading / 准备篇 skills-promo 块）包裹一个锚点容器，
  id 形如 `sec-认知篇`。
- 每张章节卡片所在位置可定位到 id 形如 `ch-<chapterId>`（如 `ch-ch01-agent-harness`）。
  侧栏“章节项”滚动目标为该卡片锚点。
- 准备篇两项（AgentSeek 上/下）的卡片在 skills-promo 块中，侧栏项滚动到该块对应锚点，
  使侧栏成为完整的课程地图。

## 4. 桌面端侧栏视觉（≥ lg）—— 安静（low-emphasis）

设计意图：**默认极弱存在感，只在“需要看它”时才清晰**。侧栏在左侧留白处，
不带边框、不带背景、不成卡片，整体读起来是左侧一列浅灰文字。gold 仅保留给 Hero/卡片。

结构与文字层级：
- 头部标签：`目录`，`text-[10px] font-mono uppercase tracking-[0.15em] text-ink-muted/35`。
- 篇章标签：常规字重，`text-[11px] text-ink-muted/55`，字距略宽；**不使用** ◆ 等图标。
- 章节项：`text-[13px] text-ink-muted/55`，标题过长 `truncate`；
  **不显示序号徽标、不显示 ├ 树线、不显示背景填充**，标题左对齐齐头。

三种状态：

| 状态 | 样式 |
|---|---|
| Idle（已发布） | `text-ink-muted/55`，无背景 |
| Hover | 文字加深为 `text-ink`，`cursor-pointer`；**无背景框、无高亮块** |
| Active（scrollspy 命中） | 文字 `text-ink`（**非 gold**）+ 一条 1px `gold-light` 左侧细标记（tick）。这是整条侧栏唯一的颜色点缀。 |

（已移除早期设计中的 gold 文字、`bg-gold-pale/30` 填充、2px 粗条、序号前缀、树线、◆ 图标。）

## 5. Scrollspy 与交互

- 使用 `IntersectionObserver` 观察各章节卡片锚点；最靠近视口顶部的卡片对应的侧栏项置为 active。
- 点击侧栏项 → 平滑滚动（CSS `scroll-behavior: smooth`）到对应卡片。
- 卡片/篇章锚点设置 `scroll-margin-top`，避免被移动端 sticky 顶栏遮挡（桌面端 Header 非 sticky，
  偏移可较小；移动端需为顶栏高度预留）。
- 当侧栏自身过长发生滚动时，active 项自动 `scrollIntoView` 到侧栏可视区内。
- 渐进增强：JS 关闭时，侧栏项仍是可用的普通锚点链接（点击即跳转）；仅高亮/active 依赖 JS。

## 6. 移动 / 平板端（< lg）

- 桌面侧栏 `hidden lg:block`；< lg 时改为**顶部 sticky “课程目录”条**。
- sticky 条：`lg:hidden`，`position: sticky; top: 3.5rem`（贴在 Header 下方）；
  滚过 Hero 后再显现，避免拥挤 Hero。左侧 `☰ 课程目录`，右侧显示当前篇章名（同一 scrollspy 驱动）。
- 点击条 → 就地展开下拉面板（disclosure / 轻量 toggled panel），列出与桌面侧栏相同的
  已发布篇章 + 章节。点击某章 → 关闭面板并平滑滚动。
- 关闭方式：点 ✕、点选某项、或点击面板外区域。
- **不使用全屏 modal、不锁定 body 滚动**，避免滚动位置 bug。
- 复用与桌面侧栏完全相同的数据与 active 逻辑（单一数据源），仅渲染容器不同；
  面板内沿用同样的安静文字样式。

## 7. 组件与文件改动

新增：
- `src/components/ChapterRail.astro` —— 拥有侧栏 + 移动端顶栏/下拉的全部标记，
  以及 scrollspy / 平滑滚动 / 展开收起的脚本。
  - Props：`sections`（已分组、已过滤为“含已发布章节”的篇章 → 其已发布章节列表）。
  - 发布过滤逻辑不在组件内重复计算，统一由 `index.astro` 传入，保证与内容列同源。

修改：
- `src/pages/index.astro`
  - 容器宽度 `max-w-5xl` → `max-w-6xl`。
  - 在 Hero 之后、Footer 之前，用两列 grid 包裹“侧栏 + 章节列表”。
  - 渲染 `<ChapterRail sections={...} />`（桌面列 1）。
  - 为篇章标题与每张卡片位置补充锚点 id（`sec-*` / `ch-*`）及 `scroll-margin-top`。
    - 可能需要给 `SectionHeading` 包一层带 id 的容器，或给其根节点加 id（择一，优先包裹层以免改动组件签名）。
- `src/styles/global.css`
  - 新增侧栏相关的少量类（active tick、sticky 偏移、`scroll-margin-top` 等）。
    优先用 Tailwind 原子类，仅在原子类难表达处落到 global.css。

不改动：`ChapterCard.astro`、`Footer.astro`、`Header.astro`、`chapters.json` 数据结构。

## 8. 可访问性（a11y）

- 侧栏根元素 `<nav aria-label="课程目录">`。
- 侧栏项为真实 `<a href="#ch-...">`，键盘可聚焦、可回车跳转。
- active 项加 `aria-current="true"`。
- 移动端展开按钮 `aria-expanded` / `aria-controls` 关联面板；面板可 Esc 关闭。
- 颜色对比：idle 文字虽弱（`/55`），但 hover/focus 会加深到 `text-ink`，
  且可聚焦元素有可见 focus 态；确保 focus 态满足对比要求。
- 尊重 `prefers-reduced-motion`：减少/禁用平滑滚动动画。

## 9. 验收标准

1. 桌面（≥ lg）：Hero 全宽不被压缩；其下出现左侧安静目录 + 右侧原卡片网格；
   内容列不窄于改动前。
2. 侧栏随滚动高亮当前章节（仅文字加深 + 1px gold 左标记），无背景块、无 gold 文字。
3. 点击侧栏项平滑滚动到对应卡片，且卡片不被遮挡。
4. 侧栏只含已发布章节；实战篇不出现；项与下方卡片一一对应、无死锚点。
5. 移动/平板：左栏隐藏，顶部出现 sticky “课程目录”条，点击展开面板可跳转。
6. JS 关闭时侧栏链接仍可点击跳转。
7. `npm run build` 通过；现有图片路径检查、assets 检查不受影响。
8. 不引入新配色；gold 仅出现在既有位置 + 侧栏 active 的 1px 标记。

## 10. 风险与权衡

- **加宽到 max-w-6xl**：需目测确认卡片两列网格在更宽容器下比例仍协调；如偏宽可回退为
  仅在 `2xl` 进一步放宽、`lg` 维持较紧。
- **scrollspy 边界**：相邻篇章交界处 active 抖动 —— 用 `rootMargin` 调参（如顶部偏移
  约视口 30%）稳定判定。
- **准备篇锚点特殊性**：其卡片在 skills-promo 块内，需单独确认锚点位置正确。
- **安静配色的可发现性**：默认很弱可能让部分用户注意不到侧栏；通过 hover 加深 +
  active 跟随滚动来弥补；如反馈“太隐形”，可小幅提升 idle 透明度（`/55` → `/65`）。
