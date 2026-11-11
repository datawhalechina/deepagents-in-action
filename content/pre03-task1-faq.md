# 叶静的常见问题与排障（FAQ）

本章 FAQ 内容由 **叶静（yejing8011）** 贡献。

> 汇总课程学习与实践中的常见问题，覆盖环境安装、网络代理、模型配置、运行排障、Trace 追踪与成本。首次运行部分以 `deepagents/research` 为例，帮助你先完成一个小任务，再判断结果是否可靠。
>
> 完整安装步骤见 [AgentSeek 准备篇（上）](../pre01-agentseek-create/)，编码助手技能与 Trace 调试工具见 [准备篇（下）](../pre02-agentseek-skills/)。本章按问题查阅，不需要从头重装一遍。

**快速定位：**不知道从哪开始，先读“一、首次运行”；装不上或连不通，读“二、环境与网络”；Key、模型或 Trace 有问题，读“三、配置与追踪”；报告已生成但不确定是否健康，读“四、结果与成本”。

**版本边界：**以下命令以 Bash 为例，适用于 macOS、Linux 和 Windows 的 WSL2 Ubuntu；原生 PowerShell 请使用准备篇中的对应写法。AgentSeek、模板和模型服务会更新，以当前项目的 README、`.env.example`、锁文件、`agentseek info` 和 `agentseek task --list` 为准。不要把个案修复当作所有环境的固定命令。

## 一、首次运行

### Q1：Task1 到底要完成什么，怎样算跑通？

在本机启动 `deepagents/research`，用一个公开问题完成真实搜索，得到有来源链接的 Markdown 报告。建议分五层验收：

| 检查点 | 应该留下的证据 |
| --- | --- |
| 工具可用 | Python、uv、Node.js、npm 和 AgentSeek 能输出版本 |
| 准备完成 | 依赖与必填配置齐全，`agentseek doctor` 通过 |
| 服务可达 | 启动后运行 `agentseek doctor --live`，声明的本地服务可访问 |
| 任务完成 | 真实模型与搜索调用成功，最终报告完整，来源可打开 |
| 运行可解释 | 能说明模型、调用过程、错误和大致用量 |

静态检查、服务检查和真实任务提供不同证据，不能互相替代。网页打开了，只能说明走到了其中一层。

### Q2：AgentSeek、后端、前端和 API 分别负责什么？

| 组件 | 职责 |
| --- | --- |
| AgentSeek | 创建项目、查看要求、运行准备任务、检查和启动服务 |
| Deep Agents 后端 | 执行模型与工具调用；具体服务命令由模板声明 |
| React 前端 | 输入任务、查看进度和报告 |
| 模型 API | 提供模型推理与工具调用能力 |
| Tavily | 提供联网搜索，需要独立的搜索 Key |
| LangSmith | 可选的运行追踪，用来观察调用、错误、耗时和用量 |

课程研究模板常用后端端口 `2024`、前端端口 `5174`，但端口和运行方式都可以变化。实际入口看 `agentseek info`，不要凭旧截图猜地址。参见 [AgentSeek 项目说明](https://github.com/ob-labs/agentseek)与[研究模板说明](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)。

### Q3：第一次运行应按什么顺序？

完整安装见准备篇。已经装好 Python、uv、Node.js/npm 和 Git 时，下面是新项目的最小流程；**已有项目直接进入原目录，不要重新生成覆盖。**

先检查当前终端中的工具：

```bash
python3 --version
uv --version
node --version
npm --version
git --version
```

再创建项目并查看它声明的任务：

```bash
uv tool install agentseek
agentseek version
mkdir -p ~/projects
cd ~/projects
agentseek create deepagents/research --no-input
cd research_deepagent
agentseek info
agentseek task --list
```

`research_deepagent` 是默认目录名；自定义名称后以创建输出为准。不加 `--checkout` 时沿用 CLI 锁定的模板目录；本期课程明确要求 `--checkout main` 或某个提交号时，按课程要求创建并记录完整版本。`main` 会变化，不能当作可复现的版本号。

在项目根目录保留已有配置，只补缺少的文件：

```bash
test -f .env || cp .env.example .env
test -f frontend/.env || cp frontend/.env.example frontend/.env
```

用编辑器按 `.env.example` 填写所选模型服务和 Tavily 的 Key。示例文件不存在时先读该版本 README，不要新建空文件冒充配置完成。若任务列表包含 `sync` 与 `frontend`，继续：

```bash
agentseek task sync
agentseek task frontend
agentseek doctor
agentseek dev --dry-run
agentseek dev
```

任务名不同就使用列表里的对应任务；若课程还声明 `course-check` 等验证任务，也按 README 执行。`--dry-run` 只预览启动计划，不启动服务。保留运行 `dev` 的终端，另开终端进入同一项目目录，再运行：

```bash
agentseek doctor --live
```

每一步先确认结果再继续。出现错误先保存最早的完整错误，不要立即删锁文件、换包管理器或重装所有工具。命令细节见 [AgentSeek CLI 参考](https://ob-labs.github.io/agentseek/reference/cli/)。

### Q4：用什么任务做第一次验收最合适？

使用公开、范围小、容易核验的问题，例如：

> 查找 Python 官方文档，说明 list 与 tuple 的两个主要区别。请用中文回答，附上来源链接，并尽量把回答控制在 300 字以内。

先只提交一次，不要等待时反复点击或同时开启多个研究任务。回答长度只是提示，**不是调用次数或费用的硬限制**。

检查三件事：有搜索或工具调用的证据；最终报告完整；来源能够打开，并且实际支持结论。只有一段看起来流畅的文字，还不能证明研究任务完成。

### Q5：没有计划面板或子 Agent 卡片，是不是失败了？

不一定。Deep Agents v0.7 把 Todo 规划改为可选能力，应用需要显式启用 `TodoListMiddleware`；课程研究模板可以自行启用它。子 Agent 卡片还取决于模型是否真的选择委派。

先查当前模板配置和实际调用，再根据搜索、来源与最终结果判断。不要把“必须出现某个 UI 面板”作为所有版本通用的验收条件。参见 [v0.7 版本更新](../release-v0-7/)和[任务规划](../ch04-task-planning/)。

## 二、环境与网络

### Q6：Ubuntu 里提示找不到 wsl，需要重装吗？

先确认自己在哪个终端。进入 Ubuntu 的 `wsl` 命令通常在 Windows PowerShell 执行；你看到 Linux 提示符时，可能已经在 WSL 里。

Windows 学员建议把 WSL 项目放在 `~/projects/`，不要混用 Windows 与 Linux 的 Python、uv、Node.js、npm 或 Git。使用 Linux 工具时也尽量避免把项目放在 `/mnt/c/`。具体步骤见 [Windows 环境准备](../pre01-agentseek-create/)。

### Q7：curl 能联网，为什么 AgentSeek、Git 或 npm 下载失败？

一次 `curl` 成功，只证明那个进程能访问那个目标。不同工具可能访问不同域名，使用不同代理或证书配置。

先从完整错误里找出**失败的目标域名、具体命令和错误码**，再在同一终端核对 DNS、代理、证书、权限以及所用工具版本。包镜像只影响相应的包下载，不会顺带修复 GitHub 或模型 API 连接。

分享日志前脱敏。URL、代理地址和 `curl -v` 输出都可能含凭证，不要把它们原样贴到公开 Issue。

### Q8：开了代理以后，为什么本地前后端连不上？

外网可能需要代理，本机前后端通常不需要。检查启动应用的进程是否把 `127.0.0.1` 和 `localhost` 放进代理绕过名单，并注意变量大小写的支持差异。

在专用 Bash 终端里，可以保留已有名单并同步两种写法：

```bash
bypass="${NO_PROXY:+$NO_PROXY,}${no_proxy:+$no_proxy,}127.0.0.1,localhost"
export NO_PROXY="$bypass"
export no_proxy="$bypass"
unset bypass
```

从这个终端启动应用，再验证本地地址。此设置只作用于该终端及它启动的子进程；不同客户端对环境变量的支持仍需分别核对。`OPENAI_API_BASE` 是模型服务的 API 地址，不是 HTTP 代理地址。参见 [curl 环境变量说明](https://curl.se/docs/manpage.html#ENVIRONMENT)。

### Q9：WSL 的 mirrored 模式能自动修好代理吗？

不能保证。`networkingMode=mirrored` 和 `autoProxy` 是两项不同配置，效果还依赖 Windows/WSL 版本、代理软件和应用支持。当前方式已经可用时不必切换。

修改前保存工作，`wsl --shutdown` 会停止所有正在运行的 WSL 发行版。开启 Allow LAN、放宽防火墙或全局代理都不是课程必做步骤。先看 [Microsoft WSL 网络说明](https://learn.microsoft.com/windows/wsl/networking)，不要盲目扩大网络访问范围。

### Q10：npm 安装失败，要直接换成 Yarn 吗？

先看错误、Node/npm 版本、项目 `packageManager` 字段和锁文件。网络、权限、版本不兼容与依赖冲突需要不同处理；换工具不一定解决根因。

只有确认项目支持 Yarn 后再切换，避免同时生成多套锁文件影响复现。Yarn 的 TLS 错误也不一定是缺少代理，证书信任、系统时间或中间代理都可能影响连接。按所用主版本检查 [Yarn 配置](https://yarnpkg.com/configuration/yarnrc)，不要通过关闭证书验证来“修好”下载。

## 三、配置与追踪

### Q11：模型配置为什么要同时看 Provider、模型 ID、API Base 和 Key？

四项需要彼此匹配：

| 配置 | 需要确认的事情 |
| --- | --- |
| `AGENTSEEK_MODEL_PROVIDER` | 使用哪个模型适配器 |
| `AGENTSEEK_MODEL` | 该服务是否提供这个完整模型 ID |
| `OPENAI_API_BASE` | 请求实际发往哪个服务 |
| `OPENAI_API_KEY` | 是否为该服务的有效凭证 |

下面是**配置示意片段**：使用课程研究模板的 SiliconFlow OpenAI 兼容接口。尖括号内容必须替换，不能原样运行。

```dotenv
AGENTSEEK_MODEL_PROVIDER=openai
AGENTSEEK_MODEL=<CURRENT_TOOL_CAPABLE_MODEL_ID>
OPENAI_API_BASE=https://api.siliconflow.cn/v1
OPENAI_API_KEY=<YOUR_SILICONFLOW_KEY>
TAVILY_API_KEY=<YOUR_TAVILY_KEY>
LANGSMITH_TRACING=false
```

这里 `openai` 选择适配器，费用归属取决于实际调用的服务。字段叫 `OPENAI_API_KEY`，不表示必须填 OpenAI 的 Key。切回官方 OpenAI 时，需要同步选择对应模型、替换 Key，并按模板说明清除原有网关地址。

Tavily Key 从 [Tavily 控制台](https://app.tavily.com/)获取，与模型服务商的 Key 不通用。其他提供商使用各自的字段，以当前 `.env.example` 和读取配置的代码为准，不要自行把变量改成 `MODEL_NAME`、`GLM_API_KEY` 或 `SILICONFLOW_API_KEY`。参见[研究模板的配置说明](https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/deepagents/research)。

### Q12：模型能聊天，为什么研究任务仍然失败？

研究任务还依赖工具调用、输出格式、上下文容量和服务商兼容性。先确认完整模型 ID、账户访问权限、余额和工具调用支持，再看后端报错与 Trace。

不同模型不是改名关系。不要照抄旧截图里的模型名，也不要同时改模型、代理和依赖。用原来的已知可用配置复测，有助于区分环境问题和模型兼容问题。

如果模板提供 `AGENTSEEK_PARALLEL_TOOL_CALLS=false`，初次运行保留课程基线。这是请求模型顺序调用工具的兼容配置，不代表整个系统不能并发；更换网关后的支持情况按模板说明核对。

### Q13：doctor 通过了，为什么真实任务还是失败？

`agentseek doctor` 检查本地准备条件，例如文件、工具、依赖和必填配置。`doctor --live` 增加的是声明服务的健康检查。

它们不能代替真实模型与搜索调用：Key 可能失效、额度可能不足、模型可能不支持工具调用、远端服务也可能暂时异常。按“静态检查 → 本地服务 → 小任务 → 来源与用量”的顺序查证，不要反复修改已经通过的检查项。

### Q14：改了 .env 为什么不生效？

依次检查：文件是不是当前项目的；变量名是否正确；是否重复定义；终端、IDE 或启动配置里是否已有同名变量；修改后是否重启进程。

覆盖顺序取决于具体加载方式。例如 Python 的 `load_dotenv()` 默认不覆盖已有进程环境，不能把“最后一行永远生效”当作跨工具规则。参见 [python-dotenv 文档](https://bbc2.github.io/python-dotenv/)。

用编辑器核对值；求助时报告变量名及“已设置/为空”即可，不要公开整份 `.env`。

### Q15：LangSmith 没有 Trace，先查什么？

基础运行成功后再开启追踪。在同一份 `.env` 中编辑对应项，不要重复追加一组同名变量。以下为**配置示意片段**，占位符需替换：

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<YOUR_LANGSMITH_KEY>
LANGSMITH_PROJECT=deepagents-task1
LANGSMITH_ENDPOINT=<YOUR_ORGANIZATION_API_ENDPOINT>
```

按组织所在区域选择 API 端点。Key 关联多个工作区时，还要按 SDK 要求设置 `LANGSMITH_WORKSPACE_ID`，确认 Key 有效且具备追踪写入权限。不同工作区类型按当前官方说明调整。

按顺序核对：

1. 追踪开关是否开启，Key 是否为空或失效。
2. API 端点是否与组织区域匹配。
3. 是否选中了正确工作区和项目，有没有筛选掉本次运行。
4. 修改后是否重启，并且真的产生了新调用。
5. 后端日志是否出现追踪上传错误。

只用公开问题做追踪练习，因为 Trace 可能保存提示词、工具参数和输出。先找到根 Trace、模型调用和搜索调用即可，不必一次读懂所有内部节点。

参考 [LangSmith 区域与 API 端点](https://docs.langchain.com/langsmith/cloud#regions)、[API Key 与 SDK 配置](https://docs.langchain.com/langsmith/create-account-api-key#configure-the-sdk)。

### Q16：开发 Skill、运行时 Skill，以及 LangSmith CLI/SDK 是一回事吗？

分别看服务对象：

- `npx skills add ...` 安装的是给 Codex、Claude Code 等编码助手使用的开发技能。
- Deep Agents 运行时 Skill 是给你构建的 Agent 使用的能力包。安装开发技能，不等于应用已经加载运行时 Skill。
- LangSmith CLI 是命令行工具，Python SDK 是 Python 应用中的库。需要 CLI 时按官方 CLI 方式安装，不要把 `uv tool install langsmith` 当作等价安装。

基础首跑可以先不安装这些可选开发工具。具体步骤见[准备篇（下）](../pre02-agentseek-skills/)；运行时能力见 [Skills 章节](../ch07-skills/)。

## 四、结果与成本

### Q17：报告生成了，但 Token 用量很高，算成功吗？

它说明任务可能完成，仍需检查结果质量和运行成本。长上下文、多轮搜索、重试、子 Agent 或重复提交都可能抬高用量；高 Token 数既不能自动判定 bug，也不能证明没有 bug。

先停止重复试跑，保留 Trace，再检查每次模型调用的输入/输出 Token、失败重试和重复调用。父节点可能汇总子节点，不要把各层的总数再次相加。

LangSmith 成本估算依赖用量与价格配置，最终费用以服务商账单为准。开跑前看[模型服务商价格与用量说明](https://docs.siliconflow.cn/docs/userguide/quickstart)，追踪口径见 [LangSmith 成本追踪](https://docs.langchain.com/langsmith/cost-tracking)。

### Q18：怎样比较两个模型，而不是只比较两段回答？

先用一个已知可用模型建立基线。确认另一模型支持所需工具调用，并了解价格后，仅更换模型 ID，使用新会话、相同任务和相同提示词；其他必须改变的配置单独记录。

比较任务是否完成、来源是否可靠、工具调用错误、耗时、输入/输出 Token 和服务商成本。联网搜索与模型输出有随机性，一次试验只能发现线索，不能证明某模型整体更强。预算允许时再重复，不要为了凑次数继续高成本运行。

### Q19：怎么保护 Key，又怎么确认任务停下来了？

真实 Key 只放在本地受保护的配置中，不要写进前端公开变量、截图、聊天记录或 Git 提交。可以用以下命令检查忽略规则：

```bash
git check-ignore .env frontend/.env
```

这只检查忽略规则，不能证明历史提交没有泄露。如果 Key 曾经进入提交或公开日志，应撤销并更换泄露凭证，仅补 `.gitignore` 不够。

练习结束后在开发终端按 `Ctrl+C` 停止服务，再确认相关进程停止。关闭网页不等于停止后端任务；服务商已经处理的请求不一定能撤销或退款。发现异常用量时，先停止继续提交，再查 Trace 和服务商用量记录。

### Q20：怎样求助，才能让别人快速复现？

先记录第一处偏差，不要只贴最后一屏连锁报错。可以复制以下模板，**先脱敏再发送**：

```text
环境：操作系统 / 终端类型 / Python、uv、Node、AgentSeek 版本
项目：模板名 / 模板提交号（若有）/ 当前目录（隐藏用户名等个人路径）
卡点：创建、依赖、配置、启动，还是首次任务
命令：实际执行的命令（凭证替换为 [REDACTED]）
预期：本来应该看到什么
实际：最早的完整错误与相关日志（已脱敏）
已试：只改了哪一项；结果如何
```

保留六个习惯：每一步留证据；先确认终端与目录；一次只改一个因素；记录模板与依赖版本；先用小任务建立基线；分享可复现且不含凭证的错误。

## 完成后的自查

- 我能说明 `create`、`info`、`task`、`doctor`、`dev` 的区别。
- 我用真实小任务验证了模型和搜索，打开来源核对了结论。
- 我知道配置从哪里读取，保留了版本和成功证据。
- 我没有泄露 Key，知道怎样停止运行并核对费用。

如果都能做到，可以回到[快速上手](../ch02-quickstart/)理解 Agent 的代码结构，再按课程目录继续学习。遇到安装问题时优先核对 [Python](https://www.python.org/downloads/)、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和 [Node.js](https://nodejs.org/en/download) 的官方说明。
