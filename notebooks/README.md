# Deep Agents 实战：Notebook 实验

正文解释概念，Notebook 用小实验观察机制，AgentSeek 模板提供完整应用。每份 Notebook 从第一格独立运行，不依赖另一章留下的内核状态。

这里默认你会 Python 的变量、函数、列表、字典和循环，不要求先学过 LangChain / LangGraph。先保持默认的 **offline** 模式：不需要模型 Key，也不会请求付费模型；实验中的 Python 工具仍真实运行。

## 实验索引

<!-- course-notebook-index:start -->
| 实验 | 阅读与运行 | 学习证据 | 模型与服务 |
|---|---|---|---|
| 作者模板 | [Notebook](_template/01-minimal-tool.ipynb) · [Markdown](_template/01-minimal-tool.md) · [HTML](_template/01-minimal-tool.html) | 实际 echo 工具、调用与返回关联 | 默认脚本模型；可选真实模型 |
| 第 1 章：Agent Harness | [Notebook](ch01/01-agent-harness.ipynb) · [Markdown](ch01/01-agent-harness.md) · [HTML](ch01/01-agent-harness.html) | echo 成功、消息循环、默认工具差异 | 默认脚本模型；可选真实模型 |
| 第 2 章：快速上手与自定义工具 | [Notebook](ch02/01-quickstart.ipynb) · [Markdown](ch02/01-quickstart.md) · [HTML](ch02/01-quickstart.html) | 工具 Schema 三要素、换算与计算的调用链、两类工具错误 | 默认脚本模型；可选真实模型 |
| 第 2 章：研究助手 | [Notebook](ch02/02-research-assistant.ipynb) · [Markdown](ch02/02-research-assistant.md) · [HTML](ch02/02-research-assistant.html) | 搜索结果、Todo 状态与虚拟文件 | 默认脚本模型与本地搜索样例；live 需 Tavily Key 与 search 依赖组 |
| 第 5 章：同步子 Agent | [Notebook](ch05/01-subagent-delegation.ipynb) · [Markdown](ch05/01-subagent-delegation.md) · [HTML](ch05/01-subagent-delegation.html) | 消息隔离、文件共享与显式读取 | 默认脚本模型；可选真实模型 |
| 第 6 章：异步子 Agent | [Notebook](ch06/01-async-subagent-lifecycle.ipynb) · [Markdown](ch06/01-async-subagent-lifecycle.md) · [HTML](ch06/01-async-subagent-lifecycle.html) | 五个异步工具、服务状态与失败清理 | 默认脚本模型；真实本地 Agent Server；server 依赖组 |
| 第 7 章：Skills | [Notebook](ch07/01-skills-progressive-disclosure.ipynb) · [Markdown](ch07/01-skills-progressive-disclosure.md) · [HTML](ch07/01-skills-progressive-disclosure.html) | 元数据注入、分阶段文件读取与缺失资源 | 默认脚本模型；可选真实模型 |
| 第 8 章：长期记忆 | [Notebook](ch08/01-long-term-memory.ipynb) · [Markdown](ch08/01-long-term-memory.md) · [HTML](ch08/01-long-term-memory.html) | 跨线程 Store 共享、State 隔离、用户 namespace 与实际模型请求 | 默认脚本模型；可选真实模型 |
| 第 9 章：Human-in-the-Loop | [Notebook](ch09/01-tool-approval-and-resume.ipynb) · [Markdown](ch09/01-tool-approval-and-resume.md) · [HTML](ch09/01-tool-approval-and-resume.html) | 四种决策、审批前零执行、参数修改与批量校验 | 默认脚本模型；可选真实模型；无需外部服务 |
| 第 10 章：沙箱执行 | [Notebook](ch10/01-sandbox-execution-and-files.ipynb) · [Markdown](ch10/01-sandbox-execution-and-files.md) · [HTML](ch10/01-sandbox-execution-and-files.html) | 真实容器执行、文件传输、退出码与资源回收 | 默认脚本模型；可选真实模型；Docker Engine；首次下载镜像需网络 |
| 第 11 章：文件系统权限 | [Notebook](ch11/01-filesystem-permissions.ipynb) · [Markdown](ch11/01-filesystem-permissions.md) · [HTML](ch11/01-filesystem-permissions.html) | 规则顺序、默认允许、拒绝与人工审批 | 默认脚本模型；可选真实模型；自动清理的教学临时目录 |
| 第 14 章：Streaming | [Notebook](ch14/01-streaming-projections.ipynb) · [Markdown](ch14/01-streaming-projections.md) · [HTML](ch14/01-streaming-projections.html) | 主、子投影与工具结果；custom、raw 顺序和晚订阅 | 默认脚本模型；可选真实模型 |
<!-- course-notebook-index:end -->

每份实验同时提供三种格式：Notebook 用于逐格运行，Markdown 可直接在 GitHub 阅读，HTML 在克隆或下载仓库后用浏览器打开（GitHub 文件页显示的是 HTML 源码）。三份文件位于同一目录，包含同一次执行的结果；当前提交的示例使用 offline 模式。

## 第一次学习，从哪里开始？

建议按 **最小工具实验（作者模板）→ 第 1 章 → 第 2 章 → 第 5 章 → 第 6 章** 的顺序。先理解“模型请求、工具执行、结果返回”，再看默认工具、自定义工具与研究助手、同步委派，最后看后台任务。章节编号沿用课程正文，不表示中间章节已经有 Notebook。

| 你现在想做什么 | 入口 |
|---|---|
| 先看看实验讲什么 | 点上表的 Markdown，阅读代码、已保存的输出和解释，无需安装环境 |
| 自己逐格实验 | 完成下面的环境准备，在 VS Code / Jupyter 打开 `.ipynb`，选择项目内核 |
| 一次验证整个实验能否运行 | 在终端运行下方 `python -m course_notebooks.run ...` 命令 |

Notebook 中，**Markdown 格**用于说明，**代码格**会执行 Python。**内核**（kernel）是运行这些代码的 Python 进程，保存前面定义的变量；重启内核会清空变量。`assert` 是检查条件的语句，失败时停止并解释哪项预期没有满足；练习中的预期失败也是学习结果。

## 准备环境，完成第一次运行

下载或克隆仓库后，在终端进入仓库根目录，也就是同时包含 `notebooks/`、`content/`、`scripts/` 的文件夹。下方标为 `bash` 的命令都在**终端**运行，不要粘贴进 Python 代码格。

使用 Python 3.12 和独立的 Python 子项目。先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)；它会准备项目的 Python 环境与依赖。下面第一条命令安装锁定的依赖，第二条完整执行最小实验：

```bash
uv sync --project notebooks --locked
uv run --project notebooks --locked python -m course_notebooks.run template
```

成功时，终端最后会显示 `template: passed (offline)`。打开 `artifacts/notebooks/template.html`，应看到实际工具返回 `echo: hello course`，以及“已验证：调用请求 → Python 工具执行 → 工具结果 → 最终回复”。仅看到模型回复“完成”还不够。

`uv.lock` 锁定实际依赖；基础版本是 deepagents 0.7.22、langchain 1.4.3、langchain-core 1.6.6、langgraph 1.2.13、langchain-openai 1.6.7（2026-10-06 核对 PyPI 最新稳定版）。服务类实验另外安装：

```bash
uv sync --project notebooks --locked --extra server
uv run --project notebooks --locked --extra server python -m course_notebooks.run
```

直接依赖已核对最新稳定版，传递依赖按上游兼容约束升级。最新的 `langgraph-api` 仍限制 gRPC、Protobuf、OpenTelemetry、`jsonschema-rs` 和 `structlog` 的版本；Pydantic 固定配套的 `pydantic-core`，LangChain 和模型 SDK 也限制 `uuid-utils`、`websockets`。因此锁文件中的部分传递依赖低于 PyPI 的全局最新版，不应通过忽略约束强行替换。

执行器为每份实验创建临时工作目录，并直接使用项目 Python 创建专用内核；已有的用户 `python3` 内核不会改变执行环境。默认从第一格执行所有已登记实验，也可以在命令末尾指定一个或多个实验 ID，例如 `template`。

结果写入 `artifacts/notebooks/`：执行后的 `.ipynb`、可直接阅读的 HTML/Markdown 和 `report.json`。报告记录源码提交、单份实验源码指纹、依赖锁指纹、模式与状态；live 还记录模型配置，字段说明见下文。失败返回非零退出码，后续未执行项标为 `not_run`。导出链接指向对应源码提交；未提交的新文件需提交后重新导出。

在 VS Code/Jupyter 中逐格学习时，选择 `notebooks/.venv/bin/python`（Windows 为 `notebooks/.venv/Scripts/python.exe`）对应的内核。也可显式注册：

```bash
uv run --project notebooks --locked python -m ipykernel install --user --name deepagents-course --display-name "Deep Agents course"
```

安装并选择内核后：

1. 在 VS Code（需 Python / Jupyter 扩展）或已有的 Jupyter 界面打开一份 `.ipynb`。
2. 从第一格依次运行；通常可用 `Shift+Enter`。定义函数或变量的代码格没有打印内容也可能正常完成。
3. 对照每节的预期输出，再做结尾的单变量练习。不要同时修改模型、数据和工具，否则难以知道变化来自哪里。
4. 需要恢复时，先撤销练习修改，再选择“重启内核并运行全部”。这一操作会重新建立所有变量，避免跳格执行留下旧状态。

`course_notebooks` 是本仓库的辅助包，安装时一并提供。Notebook 中常见的 `show_runtime` 打印模式、版本及 live 模型配置，`show_text` 整理输出换行，`create_model` 选择运行模式；真正的工具定义、Agent 组装与关键检查仍在各章代码格中。

### 常见卡点

| 现象 | 下一步 |
|---|---|
| 找不到 `uv` | 先完成上方 uv 安装，再打开终端 |
| 找不到 `langchain` / `course_notebooks` | 重新确认安装已完成，并选择本仓库 `notebooks/.venv` 的内核 |
| 提示从课程仓库目录运行 | 回到包含 `scripts/chapters.json` 的仓库目录，重新打开/执行 Notebook |
| `NameError`，变量未定义 | 从第一格依次运行，不要只执行后面的结果检查格 |
| 没改代码却与保存输出不同 | 先核对开头的 offline/live 模式；任务 ID 和部分平台信息本就会变化 |
| 实验中的断言失败 | 读断言说明并检查前面的实际工具结果；如果正在做失败练习，按该节的恢复步骤重跑 |

## 脚本模型与真实模型

默认 `offline`：不读取 `.env` 里的模型配置，不向模型供应商发送请求。脚本模型按公开规则产生工具调用，框架、工具函数、状态变化仍真实执行。这个模式验证机制，不证明真实模型会正确选工具；服务类实验仍需要本机启动真实服务。

公共 `ScriptedChatModel` 是 LangChain 官方 `FakeMessagesListChatModel` 的薄适配器，只补充 `bind_tools()` 和可选的消息回调。模板与第 1、2 章使用官方响应列表；第 5、6 章通过回调读取当前消息、当前工具集合或运行时任务 ID。响应列表会循环，独立实验应创建新实例；回调不依赖共享调用次数。预设的结束消息不是成功证据，仍须核对真实工具结果。

需要真实模型时，先看下面的[硅流模型验证表](#live-models)。把 [`.env.example`](../.env.example) 复制为仓库根目录未提交的 `.env`，填写 `SILICONFLOW_API_KEY` 和本章要使用的完整 `MODEL_NAME`，再明确选择 `live`。例如第 7 章已有整本通过记录，可以填写 `MODEL_NAME=Qwen/Qwen3-Coder-30B-A3B-Instruct` 后运行：

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch07-skills \
  --mode live --output-dir artifacts/notebooks-live
```

第 2 章研究助手在 live 模式下还会真实调用 Tavily 搜索：需要在 `.env` 中设置 `TAVILY_API_KEY`，安装和运行命令都加上 `--extra search`（完整命令见该 Notebook 开头）。offline 模式使用本地搜索样例，不需要这些。

默认提供商使用 `SILICONFLOW_API_KEY`，`MODEL_NAME` 必填；`SILICONFLOW_BASE_URL` 默认 `https://api.siliconflow.cn/v1`。其他 OpenAI 兼容提供商必须同时设置 `MODEL_API_KEY`、`MODEL_BASE_URL`、`MODEL_NAME`。已有进程环境变量优先于 `.env`，切换模型后请检查开头打印的模型名。模型必须支持工具调用；实际网络请求可能收费。复杂实验需要更可靠的工具调用能力，不能由入门实验的结果推断所有模型均适用。

交互式内核可在创建模型前设置 `os.environ["COURSE_MODE"] = "live"`；重跑时重新选择模式。仅仅存在 Key 或 `.env` 不会启用真实模型。明确选择 live 后缺配置、认证失败或调用失败都会报错，不自动退回脚本模型。LangSmith 追踪为可选项，本地 in-memory Agent Server 不要求 LangSmith Key。

维护者验证 SiliconFlow 时，设置 `SILICONFLOW_API_KEY` 和实际的 `MODEL_NAME`，单独保存 live 产物，保留默认 offline 示例输出：

```bash
uv run --project notebooks --locked python -m course_notebooks.run ch14-streaming \
  --mode live --output-dir artifacts/notebooks-live
```

更换模型后重新执行，并记录模型名与执行报告；某个模型通过不能代表所有模型都通过。普通 fork CI 继续使用 offline，不提供供应商凭证。

<a id="live-models"></a>

### 硅流模型验证表

核对日期：2026-10-06。下表只收录**整本从第一格执行、原有断言全部通过**的 live 记录；“待验证”表示尚无当前实验版本的完整通过记录。已通过是所列模型的一次执行结果，不保证以后每次都成功。当前提交的 Notebook / Markdown / HTML 输出仍为 offline。

| 实验 | 已验证的完整 `MODEL_NAME` / 状态 | 日期与验证版本 | live 范围与服务要求 |
|---|---|---|---|
| 作者模板 | 待验证 | 2026-10-06 核对 | 模型选择 echo；本地工具，无额外服务 |
| 第 1 章 | 待验证 | 2026-10-06 核对 | 普通 Agent 与 Deep Agent 的工具选择；无额外服务 |
| 第 2 章：快速上手 | 待验证 | 2026-10-06 核对 | 正常场景用真实模型；故意制造工具错误的场景仍用脚本模型 |
| 第 2 章：研究助手 | 待验证 | 2026-10-06 核对 | 真实模型与 Tavily 搜索；另需 `TAVILY_API_KEY`、`search` 依赖组 |
| 第 5 章 | 待验证 | 2026-10-06 核对 | 主、子 Agent 用真实模型；资料是本地固定样例，无搜索服务 |
| 第 6 章 | 待验证 | 2026-10-06 核对 | 主 Agent 用真实模型；researcher 为固定回显图；需真实本地 Agent Server、`server` 依赖组 |
| 第 7 章 | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 2026-10-06；[`ae27a77`](https://github.com/datawhalechina/deepagents-in-action/commit/ae27a77f0e9fe66d0ce81ff6a8d384075fbefb77)，[#133 评审](https://github.com/datawhalechina/deepagents-in-action/pull/133#pullrequestreview-5429855673) | 模型读取 Skill 与参考文件；缺失资源场景，无额外服务 |
| 第 8 章 | 待验证 | 2026-10-06 核对 | 模型读取与编辑偏好、写草稿；工具与 Store/Checkpointer 真实执行；内存教学数据，无额外服务 |
| 第 9 章 | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 2026-10-06；[`0052010`](https://github.com/datawhalechina/deepagents-in-action/commit/0052010b95ea9088c27546209bda1e4b94f2bf1d)，[#135 评审](https://github.com/datawhalechina/deepagents-in-action/pull/135#pullrequestreview-5429856799) | 模型提出工具请求，审批与恢复；教学工具只记录参数，不发送邮件 |
| 第 10 章 | `Qwen/Qwen3-Coder-30B-A3B-Instruct` | 2026-10-06；[`b46217f`](https://github.com/datawhalechina/deepagents-in-action/commit/b46217faf2ae217131e4ccc1c33c4a406c06b659)，[#136 评审](https://github.com/datawhalechina/deepagents-in-action/pull/136#pullrequestreview-5429857769) | 模型选择 execute/read_file；分析程序预先提供；需真实 Docker，首次拉取镜像需网络 |
| 第 11 章 | 待验证 | 2026-10-06 核对 | 模型提出读写与审批请求；文件权限中间件真实执行；教学临时目录，无额外服务 |
| 第 14 章 | `Qwen/Qwen3-Coder-30B-A3B-Instruct`；`deepseek-ai/DeepSeek-V3.2` | 2026-10-06；[#140 修复说明](https://github.com/datawhalechina/deepagents-in-action/pull/140#issuecomment-6013556021)，最终版本 [`8fcd9d5`](https://github.com/datawhalechina/deepagents-in-action/commit/8fcd9d596b98a0c10f1729e8d2fd60741e0d2d9b) | 主、子 Agent 用真实模型；typed、raw、晚订阅三个场景，无额外服务 |

第 7、9、10 章的验证版本已合入 main，合并时仅解决目录注册冲突，章节执行代码保留。第 14 章在修复工作区实测后同步 main；最终版本的流式适配器、实验代码与实测一致，模型调用依赖未变。本次模型说明更新沿用这些记录，没有把新一轮 offline 执行标成 live。

`Qwen/Qwen2.5-7B-Instruct` 是入门正文使用的配置示例，尚无上述实验当前版本的完整 live 通过记录。公共入口不再隐含选择它。待验证章节先用 offline 学习；补验时明确填写所尝试的型号，不能仅凭平台标注支持工具调用就写“已验证”。`Pro/` 前缀也是模型 ID 的一部分，第 14 章的普通 DeepSeek 路由记录不涵盖 Pro 路由。

<a id="live-records"></a>

### 模型参数与运行记录

上述实测使用 Python 3.12、当前核心模型调用依赖及公共流式适配器；完整版本以对应版本的 `uv.lock` 为准。公共入口固定 `temperature=0`、单次请求 `timeout=60` 秒、`max_retries=1`；执行器的 `--timeout` 是每个代码格的时限，另行记录。第 7、9、10 章实测的锁文件 SHA-256 为 `423f83c8720c1ea068719cf8e31eef78ecfa2a6f5e599cf63ff151121ee0d97c`。

live 的 `show_runtime()` 显示所选型号、提供商及 API 主机。`report.json` 中每项结果和执行后 Notebook 的 `metadata.course_run` 同时保存 `model_configuration`：`model_name`、`provider`、`api_host`、`temperature`、`timeout_seconds`、`max_retries`。阅读导出的开头也显示型号。这里记录传给客户端的配置，不声称识别了供应商内部部署版本，也不能单独证明模型或工具被调用；仍需核对章节断言与消息、文件、服务结果。offline 的该字段为 `null`。

配置记录不包含 Key、完整 API URL、URL 用户信息或查询参数；执行输出或配置记录若包含环境中的 Key / Token，执行器会扣留产物并返回失败。维护者保存 live 报告时记录源码提交、源码指纹、依赖锁、实际模型及服务范围；修改执行代码或模型调用依赖后，应补验再更新“已验证”状态。

模型 ID 与可用能力可以在[硅流模型广场](https://www.siliconflow.cn/models)及[官方工具调用说明](https://docs.siliconflow.cn/docs/userguide/guides/function-calling)核对；实际适用性以本章完整执行为准。429、服务繁忙或超时应记为“运行未完成”，保留失败报告后重试，不能据此写成代码验证通过或模型不兼容。[限流说明](https://docs.siliconflow.cn/docs/userguide/faqs/rate-limit-and-upgradation)解释了按账户、模型计算的 RPM / TPM。

第 14 章的 v3 流式调用经过公共 `create_model` 中的 `StreamingChatOpenAI` 适配器：部分 OpenAI 兼容服务在后续工具参数分块中返回空工具名，`langchain-core 1.6.6` 会用它覆盖首块的名称。适配器只把这类空字符串转为“未提供名称”的 `None`，保留参数、调用 ID、文本和元数据；同步与异步路径都适用。升级上游后，应先运行 `tests/test_streaming_model.py`，确认移除适配器仍能通过，再删除这层兼容处理。

## 维护者与贡献者：验证并更新三种格式

章节共建进度见 [#105](https://github.com/datawhalechina/deepagents-in-action/issues/105)，目录元数据在 [catalog.json](catalog.json)。下面的命令用于验证和提交实验；初次学习不需要先理解这些维护步骤。

```bash
uv run --project notebooks --locked --extra server pytest notebooks/tests
uv run --project notebooks --locked --extra server python -m course_notebooks.run --check-only
uv run --project notebooks --locked --extra server python -m course_notebooks.run --write-back
uv run --project notebooks --locked --extra server python -m course_notebooks.run --check-reading
```

`--write-back` 将成功执行的本次输出写回源 Notebook，同时在旁边生成同名 `.html` 和 `.md`；失败不会覆盖这三份文件。阅读副本保留章节内的相对链接，随源码一起提交，不分别手工编辑。`--check-reading` 不调用模型，检查保存的 Notebook 已成功执行、源码指纹一致，以及 HTML/Markdown 和相关图片是否与该 Notebook 的导出内容一致；CI 同样执行此检查。默认运行只写入 `artifacts/notebooks/`。

保存输出时同时记录模式，真实模型输出与无 Key 结果分别报告。贡献步骤和教学标准见 [CONTRIBUTING.md](CONTRIBUTING.md)。
