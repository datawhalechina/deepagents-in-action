# 第 16 章：Dynamic Subagents — 用代码编排多个 Agent

> 一个代码仓库里有 24 个路由文件。主 Agent 可以把第一个文件交给代码审查 Agent，等结果回来，再决定是否检查第二个；也可以先列出全部文件，用 JavaScript 一次组织 24 次审查，再把可疑发现交给另一个 Agent 复核。两种方式都用了子 Agent，差别在于谁控制任务的拆分、并发和下一阶段。

直接调用子 Agent 适合一次明确委派。任务覆盖许多独立对象，或者需要分类、并行、交叉验证和反复收敛时，让模型逐次选择下一次委派会带来漏项、额外模型轮次和不稳定的控制流。Dynamic Subagents（动态子 Agent）沿用上一章的 QuickJS Interpreter：模型先生成编排代码，再由代码调用内置的 `task()`，启动多个完整的子 Agent 循环并汇总结果。

本章先说明如何准备子 Agent 并触发 `workflow`，再用工单分流、代码审查和死代码排查三个例子展示主 LLM 可能生成的编排代码。除了分清 `task()` 和普通 `task` Tool，还要知道怎样定义可用角色、描述处理流程，并检查输入范围、调度约束和停止条件。

Dynamic Subagents 依赖的 Interpreter Runtime 仍处于 Beta 阶段，接口和生命周期可能继续变化。运行环境需要 Python 3.11+ 与 `langchain-quickjs>=0.2.0`；本章在 `deepagents==0.7.8`、`langchain-quickjs==0.3.5` 中核对接口和运行时限制。

## 1. 从单次委派到动态编排

Deep Agents 已经可以通过普通 `task` Tool 把工作交给子 Agent。主 Agent 每次决定一个 `description` 和一个 `subagent_type`，等待该子 Agent 完成，再继续自己的推理循环。

这种方式没有问题，只是控制粒度不同：

| 任务形状 | 优先方式 | 原因 |
|---|---|---|
| 把一个明确问题交给一个专家 | 普通 `task` Tool | 路径短，容易观察和逐次审批 |
| 对一批独立对象执行同类分析 | Dynamic Subagents | JavaScript 可以完整覆盖输入并并行扇出 |
| 输入混杂，需要先分类再分发 | Dynamic Subagents | 分类结果可以直接决定下一批 `subagentType` |
| 同一发现需要独立复核 | Dynamic Subagents | 第一阶段输出可以在代码中进入第二阶段 |
| 范围未知，需要反复搜索直到没有新结果 | Dynamic Subagents | 循环和停止条件由代码明确表达 |
| 子任务要在后台持续运行并由主 Agent 随后查询 | Async Subagents | 生命周期目标不同，不应混为并行扇出 |

Dynamic Subagents 不是新的子 Agent 类型。它改变的是编排位置：普通委派由主模型逐次调用 `task` Tool；动态编排则由一次 `eval` 中的 JavaScript 多次调用 `task()`。

![普通委派由主 Agent 逐次选择并等待一个子 Agent；Dynamic Subagents 由 QuickJS 代码对完整输入集合进行分类、并行分发和结果汇总](../public/imgs/52-comparison-direct-vs-dynamic-subagents.png)

### 为什么代码编排更稳定

假设要审查 24 个文件。模型逐次委派时，每次返回都可能改变后续决策；如果上下文变长，模型还可能提前总结，留下没有处理的文件。把文件列表放进 JavaScript 后，可以明确表达：

1. 每个输入都进入一次审查。
2. 独立任务按批次并行运行。
3. 第一阶段的发现统一去重和筛选。
4. 只有高风险发现进入复核。
5. 最终只把已确认的结果交还主模型。

生成的代码通过检查后，可以把控制流和覆盖规则明确下来，但不能保证每个子任务都成功，也不能保证子 Agent 的判断正确。每次 `task()` 都会启动完整的 Agent 推理循环，结果仍受模型、Prompt、工具和输入影响。

## 2. 先看运行过程：AI 编写 JavaScript，`task()` 执行调度

当 Agent 同时配置了子 Agent 和 Interpreter 中间件，JavaScript 环境会出现全局函数 `task()`。具体的 `subagents` 定义放在下一节，这里先看运行链路。`langchain-quickjs` 负责把 Python 侧的 Interpreter 中间件、QuickJS 运行时与异步能力桥接起来：

1. 主 LLM 读取用户请求，决定是否调用 `eval`，并为当前任务编写 JavaScript。
2. 这段 JavaScript 在 QuickJS 中运行，遇到 `task()` 时启动指定的子 Agent。
3. 每个子 Agent 再运行自己的完整推理循环，可以使用分配给它的工具。
4. JavaScript 收集、筛选和合并结果，最后只把需要的信息交回主 LLM。

因此，`task()` 不是开发者在 Python 中手写的固定工作流函数。它是 Interpreter 注入到 JavaScript 环境里的全局函数，而调用它的 JavaScript 通常由主 LLM 根据当前请求现场生成。

这对主模型提出了更高要求。模型既要稳定调用工具，也要写出可运行的异步 JavaScript，正确使用 `await`、数组方法、循环、分支和 Schema，还要选中真实存在的 `subagentType`。模型能力不足时，编排代码容易出现语法错误、角色名漂移、遗漏输入或循环失控。

提示词里的 `workflow` 会提醒主 LLM 优先考虑代码编排。它不是 API 参数；真正提供能力的是 `subagents` 配置和 `CodeInterpreterMiddleware`。下一节的提示词只写业务目标与约束，不需要加入底层函数和工具名。只有一次明确委派时，普通 `task` Tool 往往更直接。

![Dynamic Subagents 的运行结构：主 Agent 通过 eval 进入 QuickJS，tools.* 可发现或筛选输入，task() 启动多个完整子 Agent 循环，结果在 JavaScript 中合并后返回](../public/imgs/53-framework-quickjs-task-orchestration.png)

### `task()` 只有三个字段

把三个字段放在一起看，调用契约会清楚很多：

| 字段 | 是否必填 | 作用 |
|---|---|---|
| `description` | 是 | 发送给子 Agent 的任务说明，应包含目标、范围、约束和输出要求 |
| `subagentType` | 是 | 选择哪个已配置的子 Agent，值必须匹配 `subagents` 中的 `name` |
| `responseSchema` | 否 | 用 JSON Schema 约束返回值；设置后得到的已经是 JavaScript 对象 |

下面的调用同时用到了三个字段：

```typescript
const review = await task({
  description: "读取 src/auth/login.ts，检查认证绕过；引用行号。",
  subagentType: "reviewer",
  responseSchema: {
    type: "object",
    properties: {
      issues: {
        type: "array",
        items: {
          type: "object",
          properties: {
            line: { type: "number" },
            severity: { type: "string" },
            evidence: { type: "string" },
          },
          required: ["line", "severity", "evidence"],
        },
      },
    },
    required: ["issues"],
  },
});

const highRisk = review.issues.filter((item) => item.severity === "high");
```

设置 `responseSchema` 后，`review` 已经是对象，不需要再调用 `JSON.parse`。一次 `task()` 返回的是本次子 Agent 运行的结果，不是可继续对话的会话；下一次调度仍要提供自包含的 `description`。

上面的 JavaScript 只是便于解释接口的代表性写法。实际运行时，主 LLM 可能改用 `for...of`、`Promise.all`、辅助函数或不同变量名。判断是否正确，应看输入有没有完整覆盖、角色是否选对、停止条件是否生效，以及结果是否满足 Schema，不要要求生成代码逐字一致。

## 3. 先准备角色，再触发 workflow

使用 Dynamic Subagents 时，开发者和用户负责不同层面的输入。开发者预先定义主 LLM 可以选择哪些子 Agent，以及每个角色的工作边界；用户在请求中写出 `workflow`，并说明这些角色要按什么顺序处理哪些输入。主 LLM 再根据两部分信息现场生成 JavaScript。

### 3.1 准备：配置角色，写清流程

`name` 是 JavaScript 中 `subagentType` 的可用值，`description` 帮助主 LLM 选角色，`system_prompt` 则约束该角色怎样完成任务。下面七个角色覆盖三个详细示例：

```python
subagents = [
    {
        "name": "classifier",
        "description": "将工单归为 bug、feature、question 或 unknown",
        "system_prompt": "只负责分类；信息不足时返回 unknown，不处理工单。",
    },
    {
        "name": "bug-fixer",
        "description": "调查缺陷工单并给出复现步骤",
        "system_prompt": "核对现象与上下文，返回复现步骤和影响。",
    },
    {
        "name": "feature-analyst",
        "description": "评估功能请求的可行性和成本",
        "system_prompt": "说明用户价值、实现条件和主要取舍。",
    },
    {
        "name": "support-agent",
        "description": "根据已有材料回答使用问题",
        "system_prompt": "只根据可用材料回答；缺少依据时明确说明。",
    },
    {
        "name": "reviewer",
        "description": "审查代码并给出文件、行号和证据",
        "system_prompt": "只报告有代码证据的候选问题；稳定 ID 使用‘文件:行号:问题类型’。",
    },
    {
        "name": "verifier",
        "description": "独立复核候选问题并优先识别误报",
        "system_prompt": "重新读取代码，寻找反证后再确认或反驳。",
    },
    {
        "name": "analyzer",
        "description": "在给定范围内分轮查找死代码",
        "system_prompt": "用文件和符号组成稳定 ID，不要重复已发现项。",
    },
]
```

把角色表和 Interpreter 中间件一起交给主 Agent：

```python
agent = create_deep_agent(
    model=model,
    subagents=subagents,
    middleware=[CodeInterpreterMiddleware(mode="turn")],
)
```

第 4 节会统一回顾中间件参数。完成这一步后，主 LLM 才能看到可用角色，并在 JavaScript 中选择它们。

接下来在用户请求中写明流程。一个可检查的流程提示通常包含四部分：

1. 用 `workflow` 明确提示主 LLM 采用工作流式编排。
2. 给出明确的输入范围和可用角色。
3. 说明先做什么、后做什么，以及哪些步骤可以并行处理。
4. 写清去重、数量上限、停止条件和最终返回内容。

可以先用下面的骨架组织请求，再把方括号替换成当前任务的信息：

```text title="流程提示骨架"
运行一个 workflow，处理以下范围：[明确的输入范围]。
先让 [角色 A] 完成 [第一步]，再让 [角色 B] 根据第一步结果完成 [第二步]。
每个输入都要 [覆盖、去重或限制数量]；遇到 [异常或停止条件] 时 [处理方式]。
最后返回 [结果字段和未处理信息]。
```

这个骨架描述的是业务流程，不规定底层函数和代码写法。主 LLM 可能选择并发、循环、分支或结构化返回；能否生成正确代码，仍取决于模型的代码生成和工具调用能力。

### 3.2 三个示例：从流程提示到可能的 JavaScript

下面三个例子分别展示分类路由、并行复核和迭代收敛。它们不是内置模式，也不是必须照抄的固定脚本；重点是观察流程提示如何约束主 LLM 可能生成的代码。

**示例一：分类后分流**

工单类型混在一起时，先确定受控类别，再把每条交给对应角色：

```text title="建议提示词"
运行一个 workflow，处理下面三条工单：
- T-101：点击登录后返回 500。
- T-102：希望订单页可以导出 CSV。
- T-103：如何重置密码？

先让 classifier 把每条归为 bug、feature、question 或 unknown，再分别交给 bug-fixer、feature-analyst 或 support-agent。
每条工单只能进入一个处理分支，不得遗漏或重复。无法确定时保留 unknown，不要猜。
最后按工单 ID 返回类别、处理结果和未处理原因。
```

主 LLM 可能先调用 classifier，再根据受控类别选择处理角色：

```typescript title="可能生成的 JavaScript"
const tickets = [
  { id: "T-101", text: "点击登录后返回 500" },
  { id: "T-102", text: "订单页导出 CSV" },
  { id: "T-103", text: "如何重置密码" },
];
const categorySchema = {
  type: "object",
  properties: {
    category: { type: "string", enum: ["bug", "feature", "question", "unknown"] },
  },
  required: ["category"],
};
const handler = {
  bug: "bug-fixer",
  feature: "feature-analyst",
  question: "support-agent",
};
const results = await Promise.all(tickets.map(async (ticket) => {
  const { category } = await task({
    description: `只对工单分类：${ticket.id}\n${ticket.text}`,
    subagentType: "classifier",
    responseSchema: categorySchema,
  });
  if (!handler[category]) {
    return { id: ticket.id, category, unhandledReason: "分类为 unknown" };
  }
  const result = await task({
    description: `处理工单 ${ticket.id}：${ticket.text}`,
    subagentType: handler[category],
  });
  return { id: ticket.id, category, result };
}));
results;
```

检查时看三点：类别是否受 Schema 限制，unknown 是否没有被强行路由，三个工单 ID 是否都出现在结果中。

**示例二：并行审查后复核**

这个例子把“扇出并汇总”和“对抗复核”连成两个阶段。文件列表直接写进提示词，不需要让主 LLM 猜搜索范围：

```text title="建议提示词"
运行一个 workflow，审查下面三个文件：
- src/routes/login.ts
- src/routes/session.ts
- src/routes/reset-password.ts

让 reviewer 分别检查每个文件的认证问题，候选结果必须包含稳定 ID、文件、行号和证据。
按稳定 ID 去重，再让 verifier 独立确认或反驳，最多复核 20 条。
最后只返回已确认问题，并说明被反驳和未复核的数量。
```

下面只展示两阶段调度。`findingsSchema` 和 `verdictSchema` 不是内置变量；实际生成的完整代码必须先定义它们，字段分别对应上面的候选结果和复核结论：

```typescript title="可能生成的 JavaScript 核心片段"
const files = [
  "src/routes/login.ts",
  "src/routes/session.ts",
  "src/routes/reset-password.ts",
];
const reviews = await Promise.all(files.map((file) => task({
  description: `审查 ${file} 的认证问题；每条候选返回稳定 ID、文件、行号和证据，稳定 ID 使用“文件:行号:问题类型”。`,
  subagentType: "reviewer",
  responseSchema: findingsSchema,
})));
const findings = reviews.flatMap((review) => review.findings);
const unique = [...new Map(findings.map((item) => [item.id, item])).values()];
const candidates = unique.slice(0, 20);
const verdicts = await Promise.all(candidates.map((finding) => task({
  description: `复核 ${finding.file}:${finding.line}，确认或反驳：${finding.evidence}`,
  subagentType: "verifier",
  responseSchema: verdictSchema,
})));
const confirmed = candidates.filter((_, index) => verdicts[index].confirmed);
({
  confirmed,
  rejected: candidates.length - confirmed.length,
  unreviewed: unique.length - candidates.length,
});
```

主 LLM 可能使用循环或分批处理，不一定使用 `Promise.all`。验收时检查三个文件是否全部进入 reviewer、每条进入复核的候选是否都得到 verifier 的独立结论，以及超出 20 条的部分是否计入未复核数。

**示例三：分轮搜索直到停止**

范围事先不知道有多大时，提示词要同时给出业务停止条件和资源上限：

```text title="建议提示词"
运行一个 workflow，在 src/legacy/ 范围内分轮查找死代码。
每轮都让 analyzer 继续查找，并把已发现项的稳定 ID 传给它，避免重复。
如果某一轮没有新增项就停止；无论如何最多运行 5 轮，每轮最多保留 20 项。
最后返回已发现并保留的去重结果、实际轮数和停止原因。
```

这里的 `itemsSchema` 同样不是内置变量；完整代码应用它约束 ID、文件、位置和证据：

```typescript title="可能生成的 JavaScript 核心片段"
const seen = new Set();
const found = [];
let rounds = 0;
let stopReason = "达到 5 轮上限";
for (let round = 0; round < 5; round += 1) {
  rounds = round + 1;
  const { items } = await task({
    description: `在 src/legacy/ 中继续查找死代码，每轮最多返回 20 项。已发现：${[...seen].join(", ") || "无"}`,
    subagentType: "analyzer",
    responseSchema: itemsSchema,
  });
  const fresh = items.filter((item) => !seen.has(item.id)).slice(0, 20);
  if (fresh.length === 0) {
    stopReason = "本轮没有新增项";
    break;
  }
  for (const item of fresh) { seen.add(item.id); found.push(item); }
}
({ rounds, stopReason, found });
```

这段代码里，“没有新结果”是业务停止条件，“最多 5 轮”是资源上限。两者都应能从生成的 JavaScript 中直接看到。

把三个例子放在一起，可以看到流程提示分别约束了路由、并行复核和迭代停止：

![动态子 Agent 的三类编排形状：分类路由按类别选择角色；并行扇出后由 verifier 交叉验证；迭代收敛通过去重、停止条件和最大轮数逐步缩小工作集](../public/imgs/54-framework-three-orchestration-patterns.png)

三个示例的 JavaScript 都只是可能结果。变量名、循环和并发写法可以不同，但输入覆盖、角色名、结果结构和停止条件必须与提示词一致。如果需要在运行前看到代码，可以先要求只输出草案，或对 `eval` 本身设置审批。

![可用作生成后检查清单的 Dynamic Subagents 边界：限制输入与批次，区分成功、失败和结构化结果，同时检查调度规模、Interpreter 状态、子 Agent 权限和审批位置](../public/imgs/55-flow-dynamic-subagents-guardrails.png)

## 4. 回到 Interpreter：同一组中间件参数继续生效

Dynamic Subagents 没有另起一套执行环境。主 LLM 生成的 JavaScript 仍由 `CodeInterpreterMiddleware` 提供的 `eval` 执行，所以第 15 章介绍的内存、超时、输出、状态、PTC 和子 Agent 开关都会继续约束本章的动态编排。

下面是一组偏保守的起点。数值要根据模型延迟、文件规模和预算调整：

```python
middleware = CodeInterpreterMiddleware(
    mode="turn",
    subagents=True,
    memory_limit=64 * 1024 * 1024,
    timeout=30.0,
    capture_console=True,
    max_result_chars=8000,
    ptc=["glob"],
    max_ptc_calls=64,
    max_snapshot_bytes=64 * 1024 * 1024,
)
```

| 参数 | 默认值 | 对 Dynamic Subagents 的影响 |
|---|---|---|
| `memory_limit` | 64 MB | 限制每个 Interpreter thread 的 QuickJS 堆内存；文件列表、候选结果和汇总变量都在这里占用空间 |
| `timeout` | 5 秒 | 限制每次 `eval`；动态调度、等待结果和合并逻辑都发生在这次调用里 |
| `tool_name` | `"eval"` | 决定主 LLM 看到的 Interpreter Tool 名称；修改后，提示词和审批配置也要使用新名称 |
| `capture_console` | `True` | 决定是否把 `console.log`、`warn`、`error` 返回给主 LLM；调试调度代码时很有用 |
| `max_result_chars` | 4000 | 截断返回给主 LLM 的结果、错误和控制台文本；汇总过长时会直接影响后续判断 |
| `ptc` | `None` | 控制哪些工具能以 `tools.*` 进入 JavaScript；省略时不能从代码调用工具 |
| `max_ptc_calls` | 256 | 限制一次 `eval` 中的 `tools.*` 调用数，只约束 PTC，不是 `task()` 调度上限 |
| `subagents` | `True` | 有子 Agent 时暴露 `task()`；设为 `False` 后只能走普通 `task` Tool |
| `mode` | `"thread"` | 决定 JavaScript 状态保留到 call、turn 还是 thread；不改变子 Agent 本身的会话语义 |
| `max_snapshot_bytes` | `None` | 限制快照大小；未设置时使用 `memory_limit`，超限快照不会继续保留 |

这里最容易混淆的是 `max_ptc_calls`。它限制 `tools.glob(...)`、`tools.webSearch(...)` 这类 PTC 调用，不限制 `task()` 数量。当前配置表里没有单独的 `max_task_calls` 参数；动态调度数量需要通过输入批次、循环上限、Prompt 约束和业务预算控制。

`responseSchema` 也不是中间件参数，它属于每次 `task()` 的调用契约。Schema 只保证返回形状可组合，不保证结论正确。汇总时仍要保留来源文件、行号、证据、复核状态和稳定 ID，方便去重与回查。

## 本章小结

- Dynamic Subagents 使用 Interpreter 中的 JavaScript 编排已配置子 Agent。普通 `task` Tool 适合单次委派，`task()` 适合批量路由和多阶段组合。
- `task()` 只有 `description`、`subagentType` 和可选的 `responseSchema` 三个字段；设置 Schema 后直接读取 JavaScript 对象。
- `subagents` 中的 `name`、`description` 和 `system_prompt` 分别定义角色标识、选择依据和工作边界；它们决定生成代码可以调度谁。
- 每次 `task()` 都运行完整的子 Agent 循环。`description` 要自包含，并优先传文件路径等定位信息。
- `workflow` 是帮助模型选择代码编排的提示信号，不是 API 开关。请求还要写清输入范围、角色分工、处理顺序、结果要求和停止条件。
- 编排用的 JavaScript 由主 LLM 按请求生成，模型需要同时具备稳定的工具调用和代码生成能力。
- `CodeInterpreterMiddleware` 的内存、超时、输出、PTC、状态和 `subagents` 配置会继续约束动态编排。
- 面向用户的提示词写清输入范围、角色分工、返回结果和停止条件即可，不需要指定 `eval`、`task()` 等底层实现。运行前仍要检查模型生成的 JavaScript。

## 参考资料

- [Deep Agents Dynamic Subagents](https://docs.langchain.com/oss/python/deepagents/dynamic-subagents)
- [Deep Agents Interpreters](https://docs.langchain.com/oss/python/deepagents/interpreters)
- [Deep Agents Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)
- [Deep Agents Human-in-the-Loop](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop)
- [Deep Agents Event Streaming](https://docs.langchain.com/oss/python/deepagents/event-streaming)
