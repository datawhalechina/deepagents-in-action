---
article: content/ch14-streaming.md
type: mixed
density: balanced
style: sketch-notes
palette: macaron
language: zh
image_count: 4
---

# 第 14 章 Streaming 插图设计

## Illustration 1

**Position**: 第 1 节，在 `invoke()` 黑盒问题与四个产品问题之后
**Purpose**: 用同一请求的前后对比，直观解释为什么最终值不足以支撑实时产品体验。
**Visual Content**: 左侧为 `invoke()` 把运行过程压成“正在生成……”和最终答案；右侧为 Streaming 展开 coordinator、researcher、search 和消息状态。
**Filename**: 44-comparison-invoke-vs-streaming.png

## Illustration 2

**Position**: 第 3.3 节，在父级 projection 范围表之后
**Purpose**: 解释 v3 Typed Projection 的层级、作用域以及按需打开关系，帮助读者建立字段地图。
**Visual Content**: 顶层 `stream` 分出 messages、tool_calls、values、subagents、output；subagent handle 再分出自己的 projections，并突出 `path` 用于路由、`name` 用于显示。
**Filename**: 45-framework-typed-projections.png

## Illustration 3

**Position**: 第 6 节，在异步并发与同步 `interleave` 两种修复方法之后
**Purpose**: 说明事件实际交错到达，串行消费为何重排顺序，以及并发消费如何保留实时感。
**Visual Content**: coordinator 与 researcher 两条泳道并行输出，中间工具调用；串行队列产生错误 UI 顺序，并发 adapter 按到达顺序推送到页面。
**Filename**: 46-sequence-concurrent-streaming.png

## Illustration 4

**Position**: 第 8 节，在 v2 `StreamPart` 字段表之后
**Purpose**: 明确 v3 是面向产品角色的 typed projections，v2 是面向图执行的 protocol chunks，避免把两套字段放进同一个循环。
**Visual Content**: 左右对比 v3 的 `message.text`、`subagent.name/path/status`、`tool_call.*` 与 v2 的 `type/ns/data`，底部强调统一进入应用 adapter。
**Filename**: 47-comparison-v3-v2-streaming.png
