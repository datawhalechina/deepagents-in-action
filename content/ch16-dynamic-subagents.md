# 第 16 章：Dynamic Subagents — 用代码编排多个 Agent

> 一个代码仓库里有 24 个路由文件。主 Agent 可以把第一个文件交给代码审查 Agent，等结果回来，再决定是否检查第二个；也可以先列出全部文件，用 JavaScript 一次组织 24 次审查，再把可疑发现交给另一个 Agent 复核。两种方式都用了子 Agent，差别在于谁控制任务的拆分、并发和下一阶段。

直接调用子 Agent 适合一次明确委派。任务覆盖许多独立对象，或者需要分类、并行、交叉验证和反复收敛时，让模型逐次选择下一次委派会带来漏项、额外模型轮次和不稳定的控制流。Dynamic Subagents（动态子 Agent）沿用上一章的 QuickJS Interpreter：模型先生成编排代码，再由代码调用内置的 `task()`，启动多个完整的子 Agent 循环并汇总结果。

本章用 `reviewer` 和 `verifier` 两个角色贯穿示例。除了分清 `task()` 和普通 `task` Tool，还要能根据任务形状选择分类路由、并行扇出或迭代收敛，并知道如何把输入范围、调度约束和停止条件说清楚。

Dynamic Subagents 依赖仍处于 Beta 的 Interpreter Runtime，接口和生命周期可能继续变化。运行环境需要 Python 3.11+ 与 `langchain-quickjs>=0.2.0`；本章在 `deepagents==0.7.8`、`langchain-quickjs==0.3.5` 中核对接口和运行时限制。

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

代码保证的是控制流和覆盖范围，不是子 Agent 判断必然正确。每次 `task()` 都会启动完整的 Agent 推理循环，结果仍受模型、Prompt、工具和输入影响。

## 2. 先看运行过程：AI 编写 JavaScript，`task()` 执行调度

先配置可用的子 Agent 和 Interpreter 中间件。`reviewer` 负责提出候选问题，`verifier` 负责重新检查证据并反驳误报。

```python
from deepagents import create_deep_agent
from langchain_quickjs import CodeInterpreterMiddleware

subagents = [
    {
        "name": "reviewer",
        "description": "检查代码中的安全问题并给出文件、行号和证据",
        "system_prompt": "你是代码安全审查员。只报告有代码证据的问题。",
    },
    {
        "name": "verifier",
        "description": "独立复核候选安全问题，优先识别误报",
        "system_prompt": "你是审慎的复核员。重新读取代码后再确认或反驳。",
    },
]

agent = create_deep_agent(
    model=model,
    subagents=subagents,
    middleware=[CodeInterpreterMiddleware(mode="turn")],
)
```

这里有两个不同层次的模型调用。`langchain-quickjs` 负责把 Python 侧的 Interpreter 中间件、QuickJS 运行时与异步能力桥接起来：

1. 主 LLM 读取用户请求，决定是否调用 `eval`，并为当前任务编写 JavaScript。
2. 这段 JavaScript 在 QuickJS 中运行，遇到 `task()` 时启动指定的子 Agent。
3. 每个子 Agent 再运行自己的完整推理循环，可以使用分配给它的工具。
4. JavaScript 收集、筛选和合并结果，最后只把需要的信息交回主 LLM。

因此，`task()` 不是开发者在 Python 中手写的固定工作流函数。它是 Interpreter 注入到 JavaScript 环境里的全局函数，而调用它的 JavaScript 通常由主 LLM 根据当前请求现场生成。

这对主模型提出了更高要求。模型既要稳定调用工具，也要写出可运行的异步 JavaScript，正确使用 `await`、数组方法、循环、分支和 Schema，还要选中真实存在的 `subagentType`。模型能力不足时，常见问题不是“子 Agent 不够聪明”，而是编排代码先出现语法错误、角色名漂移、遗漏输入或循环失控。上线前要用真实任务验证模型的代码生成和工具调用能力，而不是只看一次演示是否成功。

### “workflow” 是提示信号，不是开关

用户请求里出现 “workflow”，会提示主 LLM 优先考虑用 `eval` 组织一段动态编排：

```python
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "运行一个 workflow：审查 src/routes/ 下的文件，并复核高风险发现。",
    }]
})
```

这个词不是 API 参数。真正决定能力是否存在的是 `subagents` 配置和 `CodeInterpreterMiddleware`。只有一次明确委派时，普通 `task` Tool 往往更直接。

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

## 3. 六种动态编排场景

下面六段代码描述的是控制流形状，不是框架预先生成的固定脚本。真正运行时，主 LLM 会根据用户请求、可用子 Agent 和中间结果重新组织 JavaScript。它可能使用不同的循环、并发方式和变量名，只要调度语义一致即可。

### 3.1 分类并处理（Classify and act）

工单、日志或反馈混在一起时，先分类，再把每一类交给对应角色。下面的片段假设主 LLM 已经为每条工单生成受控的 `ticket.category`；JavaScript 只负责校验映射并执行调度，不是凭空得出分类。

```typescript
const specialist = {
  bug: "bug-fixer",
  feature: "feature-analyst",
  question: "support-agent",
};

const handled = await Promise.all(tickets.map((ticket) => {
  const subagentType = specialist[ticket.category];
  if (!subagentType) throw new Error(`未知类别: ${ticket.category}`);
  return task({
    description: `处理这条 ${ticket.category} 工单：${ticket.text}`,
    subagentType,
  });
}));
```

不要直接把任意文本放进 `subagentType`。分类结果必须先校验，无法识别的类别应进入兜底路径。

### 3.2 扇出并汇总（Fan-out and synthesize）

当多个对象可以独立处理时，同一种角色可以并行工作。例如先用 PTC 的 `tools.glob(...)` 找到文件，再让 reviewer 分别审查：

```typescript
const files = (await tools.glob({ pattern: "src/routes/**/*.ts" }))
  .split("\n")
  .filter(Boolean);

const reviews = await Promise.all(files.map((file) =>
  task({
    description: `审查 ${file} 的认证问题，并引用行号。`,
    subagentType: "reviewer",
    responseSchema: findingsSchema,
  })
));

const findings = reviews.flatMap((item) => item.findings);
```

`tools.glob` 负责发现输入，`task()` 负责需要语义判断的审查。PTC 默认关闭，只有加入 `ptc` 白名单后，JavaScript 才能使用 `tools.*`。

### 3.3 对抗复核（Adversarial verification）

先让 reviewer 提出候选，再把每条候选交给 verifier 独立确认。第二个角色的目标不是润色结论，而是主动寻找反证。

```typescript
const { findings } = await task({
  description: "审查 payments 模块，列出候选漏洞。",
  subagentType: "reviewer",
  responseSchema: findingsSchema,
});

const verdicts = await Promise.all(findings.map((finding) =>
  task({
    description: `复核 ${finding.file}:${finding.line}，确认或反驳：${finding.evidence}`,
    subagentType: "verifier",
    responseSchema: verdictSchema,
  })
));

const confirmed = findings.filter((_, index) => verdicts[index]?.confirmed);
```

同一个角色重复确认自己的输出，独立性很弱。对抗复核需要不同的系统提示词，必要时还要使用不同模型或工具集合。

### 3.4 生成并筛选（Generate and filter）

需要比较多种设计方案时，可以并行生成候选，再按明确条件过滤。下面的例子让 architect 提出三个数据库方案，然后丢弃迁移风险过高的结果：

```typescript
const proposals = await Promise.all([1, 2, 3].map((number) =>
  task({
    description: `方案 ${number}：重新设计 orders 表，并说明取舍。`,
    subagentType: "architect",
    responseSchema: designSchema,
  })
));

const acceptable = proposals.filter((item) => item.migrationRisk !== "high");
const best = acceptable.sort((a, b) => b.coverage - a.coverage)[0];
```

过滤条件应能从 Schema 中稳定读取。若“哪个更好”本身需要语义判断，可以再交给 judge，而不是在 JavaScript 里伪造一个没有依据的分数。

### 3.5 锦标赛（Tournament）

候选较多时，可以两两比较，让胜者进入下一轮。这个形状适合代码改写、文案版本或方案选择。

```typescript
let bracket = await Promise.all([1, 2, 3, 4].map((number) =>
  task({
    description: `生成 processOrder 的可读性改写，版本 ${number}。`,
    subagentType: "writer",
  })
));

while (bracket.length > 1) {
  const winners = [];
  for (let index = 0; index < bracket.length; index += 2) {
    const pair = bracket.slice(index, index + 2);
    if (pair.length === 1) { winners.push(pair[0]); continue; }
    const result = await task({
      description: `比较 A 和 B 的可读性，返回胜者。\nA:\n${pair[0]}\nB:\n${pair[1]}`,
      subagentType: "judge",
      responseSchema: pickSchema,
    });
    winners.push(result.winner === "A" ? pair[0] : pair[1]);
  }
  bracket = winners;
}
```

每一轮都会增加模型调用。候选数、比较轮数和单次输入长度都应有上限。

### 3.6 循环直到完成（Loop until done）

范围事先未知时，可以让 analyzer 分轮发现候选，对稳定 ID 去重，直到本轮没有新增项。

```typescript
const seen = new Set();
const found = [];

for (let round = 0; round < 5; round += 1) {
  const { items } = await task({
    description: `继续寻找死代码。已发现：${[...seen].join(", ") || "无"}`,
    subagentType: "analyzer",
    responseSchema: itemsSchema,
  });
  const fresh = items.filter((item) => !seen.has(item.id));
  if (fresh.length === 0) break;
  for (const item of fresh) { seen.add(item.id); found.push(item); }
}
```

“没有新结果”是业务停止条件，`round < 5` 是资源上限，两者缺一不可。只靠自然语言判断“差不多完成了”，容易让循环继续消耗模型调用。

六种场景仍可以从控制流上归纳为三类：分类并处理属于路由；扇出、复核和生成筛选强调并发与合并；锦标赛和循环直到完成强调迭代收敛。下图用于快速选型，不代表运行时只有三种固定实现。

![动态子 Agent 的三类编排形状：分类路由按类别选择角色；并行扇出后由 verifier 交叉验证；迭代收敛通过去重、停止条件和最大轮数逐步缩小工作集](../public/imgs/54-framework-three-orchestration-patterns.png)

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

## 5. 让主 LLM 写出可检查的编排代码

前面的 JavaScript 都是为了讲清控制流而整理的片段。真正运行时，主 LLM 根据当前请求现场写代码。只说“批量审查这些文件”，模型就要自己猜角色、批次、失败处理和返回结构，生成的 JavaScript 很容易漂移。

一个可执行的请求至少要说清下面五件事：

| 信息 | 需要写明的内容 |
|---|---|
| 输入范围 | 哪些对象可以处理，哪些必须排除；没有 PTC 时直接给出文件列表 |
| 可用角色 | 列出真实的 `subagentType` 及分工，并禁止自创角色名 |
| 调度规则 | 批次大小、复核范围、最多轮数，以及单项失败后是继续还是停止 |
| 返回契约 | 哪些 `task()` 需要 `responseSchema`，最终结果保留哪些字段 |
| 停止条件 | 什么状态算完成，达到调度上限或输入不足时怎么返回 |

以“批量代码审查 + 交叉验证”为例，可以这样向主 LLM 下达任务。使用时把 `[files]` 换成实际路径列表：

```text
运行一个 Dynamic Subagents workflow，使用 eval 编写并执行 JavaScript。

输入范围：只处理我列出的文件：[files]，不扩展到其他目录。
可用角色：reviewer 提出候选问题；verifier 独立确认或反驳。不得自创角色名。

编排要求：
1. task() 只使用 description、subagentType 和可选的 responseSchema。
2. reviewer 每批最多处理 4 个文件；单个文件失败时记录错误，继续处理其余文件。
3. 分别定义 JSON Schema：reviewer 返回 ID、文件、行号和证据；verifier 返回 ID、是否确认和理由。
4. 候选按稳定 ID 去重后再交给 verifier，最多复核 20 条；超出部分记入未处理数量。
5. 最后只返回已确认问题、被反驳数、失败清单和未处理数。

如果输入列表缺失、角色不存在或无法满足上述约束，停止并说明原因，不要自行补全。
```

这段提示词也不会让模型突然变得可靠。它只是把原本隐藏的决策变成可检查条件。调试时，可以先要求模型“只输出 JavaScript 草案，不执行 `eval`”，确认下面几项后再运行：

- `task()` 没有多余字段，`subagentType` 都来自已配置角色。
- 输入集合没有漏项或越界，批次、复核数和循环都有上限。
- 单项失败有独立分支，不会把“无发现”误当成“执行失败”。
- 使用 `responseSchema` 后直接读取对象，没有多做一次 `JSON.parse`。
- 最终返回值保留来源、证据和未处理项，可以回到输入复核。

如果不想分两步，可以对 `eval` 本身设置审批，在执行前查看模型生成的代码。`task()` 发生在已经开始的 `eval` 内部，父 Agent 针对普通 `task` Tool 的 `interrupt_on` 不会在每次动态调度前重复触发。

![可用作提示词和生成后检查清单的 Dynamic Subagents 边界：限制输入与批次，区分成功、失败和结构化结果，同时检查调度规模、Interpreter 状态、子 Agent 权限和审批位置](../public/imgs/55-flow-dynamic-subagents-guardrails.png)

提示词能减少漂移，不能代替模型选型和真实任务测试。如果模型多次生成语法错误、自创角色或漏掉输入，换一个代码生成和工具调用更稳定的模型，比继续堆叠提示词更有效。

## 本章小结

- Dynamic Subagents 使用 Interpreter 中的 JavaScript 编排已配置子 Agent。普通 `task` Tool 适合单次委派，`task()` 适合批量路由和多阶段组合。
- `task()` 只有 `description`、`subagentType` 和可选的 `responseSchema` 三个字段；设置 Schema 后直接读取 JavaScript 对象。
- 每次 `task()` 都运行完整的子 Agent 循环。`description` 要自包含，并优先传文件路径等定位信息。
- “workflow” 是帮助模型选择动态编排的提示信号，不是 API 开关。常见形状包括分类、扇出、复核、筛选、锦标赛和迭代收敛。
- 动态 JavaScript 由主 LLM 按请求生成，模型需要同时具备稳定的工具调用和代码生成能力。
- `CodeInterpreterMiddleware` 的内存、超时、输出、PTC、状态和 `subagents` 配置会继续约束动态编排。
- 提示词要给出输入范围、可用角色、调度规则、返回契约和停止条件。上线前还要检查模型生成的 JavaScript。

## 参考资料

- [Deep Agents Dynamic Subagents](https://docs.langchain.com/oss/python/deepagents/dynamic-subagents)
- [Deep Agents Interpreters](https://docs.langchain.com/oss/python/deepagents/interpreters)
- [Deep Agents Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)
- [Deep Agents Human-in-the-Loop](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop)
- [Deep Agents Event Streaming](https://docs.langchain.com/oss/python/deepagents/streaming)
