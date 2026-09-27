> 本次执行模式：**offline**。源码指纹：`e3d0c0ffb48c`。

# 第 6 章｜异步子 Agent 的完整生命周期

对应 [第 6 章正文](../../content/ch06-async-subagents.md)。第 5 章的主 Agent 要等子 Agent 返回，这一章观察另一种方式：先拿到任务编号，工作继续在后台运行，随后查询、更新或取消它。

建议先理解 [第 5 章的同步委派](../ch05/01-subagent-delegation.ipynb)。本章会解释服务、图和 `await`，不要求你预先掌握异步框架；但内容比前面的 echo 实验复杂。所有状态都从本章第一格创建，不依赖其他 Notebook 的内核。

**预期现象**：主 Agent 返回启动结果时子任务尚未完成；更新后 task ID 不变而 run ID 改变；取消后主 Agent 与服务端分别给出跟踪状态和执行终态。我们会读取两边的真实数据验证这些现象。

## 1. 环境与阅读顺序

本例会启动一个只在本机访问的 **Agent Server**：它是独立运行的服务进程，负责保存任务状态、调度后台执行。Notebook 通过 **SDK**（封装服务请求的 Python 客户端）与它交互。

先按 [统一安装说明](../README.md) 准备 Python 3.12，再在终端安装 `server` 可选依赖组并运行：

```bash
uv sync --project notebooks --locked --extra server
uv run --project notebooks --locked --extra server python -m course_notebooks.run ch06-async-subagents
```

逐格学习时，先运行各个定义格，最后在第 7 节一起执行三个阶段。**定义 `async def` 函数不会启动任务**，直到后面 `await` 调用它才执行。第 3 节的检查函数第一次可先理解输入输出，核心观察在第 4～7 节。

默认 offline 仅替换模型选择工具的方式，服务、SDK 和后台任务都真实运行。无需模型 Key、远程部署或 LangSmith Key；live 才请求真实模型，可能产生费用。

下一格定位仓库目录，并把本章目录加入 Python 模块搜索路径，以便导入章内辅助类 `LocalAgentServer`。它负责启动和清理进程，不是需要另行安装的第三方包。


```python
import asyncio
import json
import sys
import time

from course_notebooks.model_config import repository_root
from course_notebooks.nbtools import show_runtime, show_text

ROOT = repository_root()
CHAPTER_DIR = ROOT / "notebooks/ch06"
sys.path.insert(0, str(CHAPTER_DIR))
from local_server import LocalAgentServer

show_runtime()
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


## 2. Notebook、服务与两个图是什么关系？

**图**（graph）是一组执行步骤及其连接；**节点**（node）是其中一个步骤；**状态**（state）是步骤传递的数据，例如消息列表。我们在一个服务中注册两个图：

```text
Notebook：发送命令、读取状态
  └─ Agent Server：保存会话、安排执行
       ├─ supervisor：主 Agent 图，模型选择异步工具
       └─ researcher：子图，等待后返回输入文本
```

Notebook 通过 SDK 请求本机服务。`AsyncSubAgent` 把主图里的“researcher”名称连接到服务已注册的子图。内部使用同部署的 ASGI 调用路径；ASGI 是 Python 异步服务接口，此处无需手写接口或启动第二个服务。

| 名称 | 本例含义 | 更新任务时 |
|---|---|---|
| `graph_id` | 工作流程的名称，如 `researcher` | 使用同一个图 |
| `thread_id` | 保存消息与状态的一段会话 | 保留子会话 |
| `task_id` | 主 Agent 跟踪子任务的编号；本例等于子 thread_id | 保持不变 |
| `run_id` | 这段会话上的某一次执行编号 | 换成新的 run |

例如，任务 T1 可以先有执行 R1，追加要求后仍是 T1，但执行变成 R2。T1/R1 只是说明用的代号；真正运行时，代码会从返回状态中取出生成的 ID，不能硬编码上次输出的编号。

服务注册见 [langgraph.json](langgraph.json)。下一格展示 [supervisor.py](graphs/supervisor.py) 的真实构造：`model` 是主模型，`system_prompt` 解释命令，`subagents` 注册 `AsyncSubAgent`；其中 `name` 供主 Agent 选择，`graph_id` 定位服务中的子图。英文提示里的五种命令会在第 3 节用中文逐项说明。


```python
from IPython.display import Code, display

supervisor_source = (CHAPTER_DIR / "graphs/supervisor.py").read_text()
display(Code("graph = " + supervisor_source.split("graph = ", 1)[1], language="python"))
```


<style>pre { line-height: 125%; }
td.linenos .normal { color: inherit; background-color: transparent; padding-left: 5px; padding-right: 5px; }
span.linenos { color: inherit; background-color: transparent; padding-left: 5px; padding-right: 5px; }
td.linenos .special { color: #000000; background-color: #ffffc0; padding-left: 5px; padding-right: 5px; }
span.linenos.special { color: #000000; background-color: #ffffc0; padding-left: 5px; padding-right: 5px; }
.output_html .hll { background-color: #ffffcc }
.output_html { background: #f8f8f8; }
.output_html .c { color: #3D7B7B; font-style: italic } /* Comment */
.output_html .err { border: 1px solid #F00 } /* Error */
.output_html .k { color: #008000; font-weight: bold } /* Keyword */
.output_html .o { color: #666 } /* Operator */
.output_html .ch { color: #3D7B7B; font-style: italic } /* Comment.Hashbang */
.output_html .cm { color: #3D7B7B; font-style: italic } /* Comment.Multiline */
.output_html .cp { color: #9C6500 } /* Comment.Preproc */
.output_html .cpf { color: #3D7B7B; font-style: italic } /* Comment.PreprocFile */
.output_html .c1 { color: #3D7B7B; font-style: italic } /* Comment.Single */
.output_html .cs { color: #3D7B7B; font-style: italic } /* Comment.Special */
.output_html .gd { color: #A00000 } /* Generic.Deleted */
.output_html .ge { font-style: italic } /* Generic.Emph */
.output_html .ges { font-weight: bold; font-style: italic } /* Generic.EmphStrong */
.output_html .gr { color: #E40000 } /* Generic.Error */
.output_html .gh { color: #000080; font-weight: bold } /* Generic.Heading */
.output_html .gi { color: #008400 } /* Generic.Inserted */
.output_html .go { color: #717171 } /* Generic.Output */
.output_html .gp { color: #000080; font-weight: bold } /* Generic.Prompt */
.output_html .gs { font-weight: bold } /* Generic.Strong */
.output_html .gu { color: #800080; font-weight: bold } /* Generic.Subheading */
.output_html .gt { color: #04D } /* Generic.Traceback */
.output_html .kc { color: #008000; font-weight: bold } /* Keyword.Constant */
.output_html .kd { color: #008000; font-weight: bold } /* Keyword.Declaration */
.output_html .kn { color: #008000; font-weight: bold } /* Keyword.Namespace */
.output_html .kp { color: #008000 } /* Keyword.Pseudo */
.output_html .kr { color: #008000; font-weight: bold } /* Keyword.Reserved */
.output_html .kt { color: #B00040 } /* Keyword.Type */
.output_html .m { color: #666 } /* Literal.Number */
.output_html .s { color: #BA2121 } /* Literal.String */
.output_html .na { color: #687822 } /* Name.Attribute */
.output_html .nb { color: #008000 } /* Name.Builtin */
.output_html .nc { color: #00F; font-weight: bold } /* Name.Class */
.output_html .no { color: #800 } /* Name.Constant */
.output_html .nd { color: #A2F } /* Name.Decorator */
.output_html .ni { color: #717171; font-weight: bold } /* Name.Entity */
.output_html .ne { color: #CB3F38; font-weight: bold } /* Name.Exception */
.output_html .nf { color: #00F } /* Name.Function */
.output_html .nl { color: #767600 } /* Name.Label */
.output_html .nn { color: #00F; font-weight: bold } /* Name.Namespace */
.output_html .nt { color: #008000; font-weight: bold } /* Name.Tag */
.output_html .nv { color: #19177C } /* Name.Variable */
.output_html .ow { color: #A2F; font-weight: bold } /* Operator.Word */
.output_html .w { color: #BBB } /* Text.Whitespace */
.output_html .mb { color: #666 } /* Literal.Number.Bin */
.output_html .mf { color: #666 } /* Literal.Number.Float */
.output_html .mh { color: #666 } /* Literal.Number.Hex */
.output_html .mi { color: #666 } /* Literal.Number.Integer */
.output_html .mo { color: #666 } /* Literal.Number.Oct */
.output_html .sa { color: #BA2121 } /* Literal.String.Affix */
.output_html .sb { color: #BA2121 } /* Literal.String.Backtick */
.output_html .sc { color: #BA2121 } /* Literal.String.Char */
.output_html .dl { color: #BA2121 } /* Literal.String.Delimiter */
.output_html .sd { color: #BA2121; font-style: italic } /* Literal.String.Doc */
.output_html .s2 { color: #BA2121 } /* Literal.String.Double */
.output_html .se { color: #AA5D1F; font-weight: bold } /* Literal.String.Escape */
.output_html .sh { color: #BA2121 } /* Literal.String.Heredoc */
.output_html .si { color: #A45A77; font-weight: bold } /* Literal.String.Interpol */
.output_html .sx { color: #008000 } /* Literal.String.Other */
.output_html .sr { color: #A45A77 } /* Literal.String.Regex */
.output_html .s1 { color: #BA2121 } /* Literal.String.Single */
.output_html .ss { color: #19177C } /* Literal.String.Symbol */
.output_html .bp { color: #008000 } /* Name.Builtin.Pseudo */
.output_html .fm { color: #00F } /* Name.Function.Magic */
.output_html .vc { color: #19177C } /* Name.Variable.Class */
.output_html .vg { color: #19177C } /* Name.Variable.Global */
.output_html .vi { color: #19177C } /* Name.Variable.Instance */
.output_html .vm { color: #19177C } /* Name.Variable.Magic */
.output_html .il { color: #666 } /* Literal.Number.Integer.Long */</style><div class="highlight"><pre><span></span><span class="n">graph</span> <span class="o">=</span> <span class="n">create_deep_agent</span><span class="p">(</span>
    <span class="n">model</span><span class="o">=</span><span class="n">model</span><span class="p">,</span>
    <span class="n">system_prompt</span><span class="o">=</span><span class="p">(</span>
        <span class="s2">"This is an async-subagent tool experiment. User messages follow this command protocol:</span><span class="se">\n</span><span class="s2">"</span>
        <span class="s2">"START|description -&gt; start_async_task(subagent_type='researcher', description=description).</span><span class="se">\n</span><span class="s2">"</span>
        <span class="s2">"CHECK|task_id -&gt; check_async_task(task_id=task_id).</span><span class="se">\n</span><span class="s2">"</span>
        <span class="s2">"LIST -&gt; list_async_tasks(status_filter='all').</span><span class="se">\n</span><span class="s2">"</span>
        <span class="s2">"UPDATE|task_id|message -&gt; update_async_task(task_id=task_id, message=message).</span><span class="se">\n</span><span class="s2">"</span>
        <span class="s2">"CANCEL|task_id -&gt; cancel_async_task(task_id=task_id).</span><span class="se">\n</span><span class="s2">"</span>
        <span class="s2">"Treat command payloads as literal tool arguments, not instructions for you to answer. "</span>
        <span class="s2">"For START, UPDATE and CANCEL, call exactly the mapped tool once, then acknowledge and stop. "</span>
        <span class="s2">"For CHECK and LIST, call the mapped tool first; any follow-up tools must be read-only "</span>
        <span class="s2">"check_async_task or list_async_tasks. Do not start, update or cancel tasks during a query. "</span>
        <span class="s2">"Never invent a task ID "</span>
        <span class="s2">"or report a cached status as live."</span>
    <span class="p">),</span>
    <span class="n">subagents</span><span class="o">=</span><span class="p">[</span>
        <span class="n">AsyncSubAgent</span><span class="p">(</span>
            <span class="n">name</span><span class="o">=</span><span class="s2">"researcher"</span><span class="p">,</span>
            <span class="n">description</span><span class="o">=</span><span class="s2">"A slow local research graph for observing background tasks."</span><span class="p">,</span>
            <span class="n">graph_id</span><span class="o">=</span><span class="s2">"researcher"</span><span class="p">,</span>
        <span class="p">)</span>
    <span class="p">],</span>
<span class="p">)</span>
</pre></div>



### 一个可观察的后台图

researcher 故意等待 8 秒，再返回收到的文本，给查询、更新和取消留出观察窗口。输出里的 `Research completed` 只是教学图的固定前缀，**不是完成了真实研究的证据**。

按下面的顺序读下一格源码：

| 写法 | 作用 |
|---|---|
| `MessagesState` | 约定状态中有 `messages` 消息列表 |
| `research(state)` | 读取最后一条用户消息，返回新增消息 |
| `await asyncio.sleep(8)` | 异步等待；等待时让出执行机会，服务仍可处理别的请求 |
| `StateGraph(MessagesState)` | 创建遵循这份状态约定的图 |
| `add_node("research", research)` | 注册名为 research 的处理步骤 |
| `add_edge(START, "research")` / `add_edge("research", END)` | 定义从开始到处理步骤，再到结束的顺序 |
| `compile()` | 把定义变成可运行对象；此时尚未处理某个任务 |

`async def` 定义可等待的函数，`await` 等待这一次调用返回。后台任务能继续运行，是因为 Agent Server 在调度它，不是仅写一个 `await` 就自动创建了后台服务。


```python
display(Code((CHAPTER_DIR / "graphs/researcher.py").read_text(), language="python"))
```


<style>pre { line-height: 125%; }
td.linenos .normal { color: inherit; background-color: transparent; padding-left: 5px; padding-right: 5px; }
span.linenos { color: inherit; background-color: transparent; padding-left: 5px; padding-right: 5px; }
td.linenos .special { color: #000000; background-color: #ffffc0; padding-left: 5px; padding-right: 5px; }
span.linenos.special { color: #000000; background-color: #ffffc0; padding-left: 5px; padding-right: 5px; }
.output_html .hll { background-color: #ffffcc }
.output_html { background: #f8f8f8; }
.output_html .c { color: #3D7B7B; font-style: italic } /* Comment */
.output_html .err { border: 1px solid #F00 } /* Error */
.output_html .k { color: #008000; font-weight: bold } /* Keyword */
.output_html .o { color: #666 } /* Operator */
.output_html .ch { color: #3D7B7B; font-style: italic } /* Comment.Hashbang */
.output_html .cm { color: #3D7B7B; font-style: italic } /* Comment.Multiline */
.output_html .cp { color: #9C6500 } /* Comment.Preproc */
.output_html .cpf { color: #3D7B7B; font-style: italic } /* Comment.PreprocFile */
.output_html .c1 { color: #3D7B7B; font-style: italic } /* Comment.Single */
.output_html .cs { color: #3D7B7B; font-style: italic } /* Comment.Special */
.output_html .gd { color: #A00000 } /* Generic.Deleted */
.output_html .ge { font-style: italic } /* Generic.Emph */
.output_html .ges { font-weight: bold; font-style: italic } /* Generic.EmphStrong */
.output_html .gr { color: #E40000 } /* Generic.Error */
.output_html .gh { color: #000080; font-weight: bold } /* Generic.Heading */
.output_html .gi { color: #008400 } /* Generic.Inserted */
.output_html .go { color: #717171 } /* Generic.Output */
.output_html .gp { color: #000080; font-weight: bold } /* Generic.Prompt */
.output_html .gs { font-weight: bold } /* Generic.Strong */
.output_html .gu { color: #800080; font-weight: bold } /* Generic.Subheading */
.output_html .gt { color: #04D } /* Generic.Traceback */
.output_html .kc { color: #008000; font-weight: bold } /* Keyword.Constant */
.output_html .kd { color: #008000; font-weight: bold } /* Keyword.Declaration */
.output_html .kn { color: #008000; font-weight: bold } /* Keyword.Namespace */
.output_html .kp { color: #008000 } /* Keyword.Pseudo */
.output_html .kr { color: #008000; font-weight: bold } /* Keyword.Reserved */
.output_html .kt { color: #B00040 } /* Keyword.Type */
.output_html .m { color: #666 } /* Literal.Number */
.output_html .s { color: #BA2121 } /* Literal.String */
.output_html .na { color: #687822 } /* Name.Attribute */
.output_html .nb { color: #008000 } /* Name.Builtin */
.output_html .nc { color: #00F; font-weight: bold } /* Name.Class */
.output_html .no { color: #800 } /* Name.Constant */
.output_html .nd { color: #A2F } /* Name.Decorator */
.output_html .ni { color: #717171; font-weight: bold } /* Name.Entity */
.output_html .ne { color: #CB3F38; font-weight: bold } /* Name.Exception */
.output_html .nf { color: #00F } /* Name.Function */
.output_html .nl { color: #767600 } /* Name.Label */
.output_html .nn { color: #00F; font-weight: bold } /* Name.Namespace */
.output_html .nt { color: #008000; font-weight: bold } /* Name.Tag */
.output_html .nv { color: #19177C } /* Name.Variable */
.output_html .ow { color: #A2F; font-weight: bold } /* Operator.Word */
.output_html .w { color: #BBB } /* Text.Whitespace */
.output_html .mb { color: #666 } /* Literal.Number.Bin */
.output_html .mf { color: #666 } /* Literal.Number.Float */
.output_html .mh { color: #666 } /* Literal.Number.Hex */
.output_html .mi { color: #666 } /* Literal.Number.Integer */
.output_html .mo { color: #666 } /* Literal.Number.Oct */
.output_html .sa { color: #BA2121 } /* Literal.String.Affix */
.output_html .sb { color: #BA2121 } /* Literal.String.Backtick */
.output_html .sc { color: #BA2121 } /* Literal.String.Char */
.output_html .dl { color: #BA2121 } /* Literal.String.Delimiter */
.output_html .sd { color: #BA2121; font-style: italic } /* Literal.String.Doc */
.output_html .s2 { color: #BA2121 } /* Literal.String.Double */
.output_html .se { color: #AA5D1F; font-weight: bold } /* Literal.String.Escape */
.output_html .sh { color: #BA2121 } /* Literal.String.Heredoc */
.output_html .si { color: #A45A77; font-weight: bold } /* Literal.String.Interpol */
.output_html .sx { color: #008000 } /* Literal.String.Other */
.output_html .sr { color: #A45A77 } /* Literal.String.Regex */
.output_html .s1 { color: #BA2121 } /* Literal.String.Single */
.output_html .ss { color: #19177C } /* Literal.String.Symbol */
.output_html .bp { color: #008000 } /* Name.Builtin.Pseudo */
.output_html .fm { color: #00F } /* Name.Function.Magic */
.output_html .vc { color: #19177C } /* Name.Variable.Class */
.output_html .vg { color: #19177C } /* Name.Variable.Global */
.output_html .vi { color: #19177C } /* Name.Variable.Instance */
.output_html .vm { color: #19177C } /* Name.Variable.Magic */
.output_html .il { color: #666 } /* Literal.Number.Integer.Long */</style><div class="highlight"><pre><span></span><span class="sd">"""A deliberately slow graph so background execution is observable."""</span>

<span class="kn">import</span><span class="w"> </span><span class="nn">asyncio</span>

<span class="kn">from</span><span class="w"> </span><span class="nn">langgraph.graph</span><span class="w"> </span><span class="kn">import</span> <span class="n">END</span><span class="p">,</span> <span class="n">START</span><span class="p">,</span> <span class="n">MessagesState</span><span class="p">,</span> <span class="n">StateGraph</span>


<span class="k">async</span> <span class="k">def</span><span class="w"> </span><span class="nf">research</span><span class="p">(</span><span class="n">state</span><span class="p">:</span> <span class="n">MessagesState</span><span class="p">):</span>
    <span class="n">request</span> <span class="o">=</span> <span class="nb">next</span><span class="p">(</span>
        <span class="p">(</span><span class="n">message</span><span class="o">.</span><span class="n">content</span> <span class="k">for</span> <span class="n">message</span> <span class="ow">in</span> <span class="nb">reversed</span><span class="p">(</span><span class="n">state</span><span class="p">[</span><span class="s2">"messages"</span><span class="p">])</span> <span class="k">if</span> <span class="n">message</span><span class="o">.</span><span class="n">type</span> <span class="o">==</span> <span class="s2">"human"</span><span class="p">),</span>
        <span class="s2">""</span><span class="p">,</span>
    <span class="p">)</span>
    <span class="k">await</span> <span class="n">asyncio</span><span class="o">.</span><span class="n">sleep</span><span class="p">(</span><span class="mi">8</span><span class="p">)</span>
    <span class="k">return</span> <span class="p">{</span><span class="s2">"messages"</span><span class="p">:</span> <span class="p">[{</span><span class="s2">"role"</span><span class="p">:</span> <span class="s2">"ai"</span><span class="p">,</span> <span class="s2">"content"</span><span class="p">:</span> <span class="sa">f</span><span class="s2">"Research completed: </span><span class="si">{</span><span class="n">request</span><span class="si">}</span><span class="s2">"</span><span class="p">}]}</span>


<span class="n">builder</span> <span class="o">=</span> <span class="n">StateGraph</span><span class="p">(</span><span class="n">MessagesState</span><span class="p">)</span>
<span class="n">builder</span><span class="o">.</span><span class="n">add_node</span><span class="p">(</span><span class="s2">"research"</span><span class="p">,</span> <span class="n">research</span><span class="p">)</span>
<span class="n">builder</span><span class="o">.</span><span class="n">add_edge</span><span class="p">(</span><span class="n">START</span><span class="p">,</span> <span class="s2">"research"</span><span class="p">)</span>
<span class="n">builder</span><span class="o">.</span><span class="n">add_edge</span><span class="p">(</span><span class="s2">"research"</span><span class="p">,</span> <span class="n">END</span><span class="p">)</span>
<span class="n">graph</span> <span class="o">=</span> <span class="n">builder</span><span class="o">.</span><span class="n">compile</span><span class="p">()</span>
</pre></div>



## 3. 向主 Agent 发命令，再读取工具结果

下面这些 `START|...` 字符串是**课程定义的简短命令，不是 LangGraph 内置 API**。offline 回调把它们转成工具请求；live 的系统提示告诉真实模型使用相同映射。

| 命令 | 请求的工具 | 参数与用途 |
|---|---|---|
| `START|任务说明` | `start_async_task` | 给 researcher 一段说明，拿到 task ID |
| `LIST` | `list_async_tasks` | 列出主 Agent 已跟踪的任务 |
| `CHECK|task_id` | `check_async_task` | 查询某个任务，成功后读取结果 |
| `UPDATE|task_id|追加要求` | `update_async_task` | 在同一个子会话里追加要求，产生新 run |
| `CANCEL|task_id` | `cancel_async_task` | 请求取消该任务，再核实服务端状态 |

关键调用是 `server.client.runs.wait(server.parent_id, "supervisor", input=...)`：把消息发给**主图的这一次执行**，等待它返回状态。它不会自动等 researcher 完成；这就是后面还要查询子任务的原因。`asyncio.wait_for(..., timeout=30)` 给这次等待设置上限，避免一直挂着。

`ask(server, text, expected_tool)` 是本章的辅助函数，返回 `(state, output)`：前者是主图状态，后者是与本次请求对应的实际工具返回。代码按三个步骤阅读即可：发送消息；只取最后一条用户消息之后的调用；核对工具结果。JSON 是服务返回结构化数据的文本格式，`json.loads` 把它变回 Python 字典。

首次学习可先运行定义，带着这个接口去看第 4 节。想细读检查逻辑时，再看调用 `id` 与结果 `tool_call_id` 怎样配对：修改操作只允许一次，查询可追加只读操作，但不能夹带修改；返回结果还要匹配请求的任务或筛选条件。


```python
def show_tool_output(name, raw):
    if name == "check_async_task":
        raw = "\n".join(f"{key}: {value}" for key, value in json.loads(raw).items())
    show_text(name, raw)


async def ask(server, text, expected_tool, show=True):
    state = await asyncio.wait_for(server.client.runs.wait(
        server.parent_id, "supervisor", input={"messages": [{"role": "user", "content": text}]}
    ), timeout=30)
    last_user = max(i for i, msg in enumerate(state["messages"]) if msg["type"] == "human")
    recent = state["messages"][last_user:]
    calls = [call for msg in recent for call in msg.get("tool_calls", [])]
    names = [call["name"] for call in calls]
    outputs = [msg for msg in recent if msg["type"] == "tool"]
    read_tools = {"list_async_tasks", "check_async_task"}

    def matches_request(call):
        if call["name"] != expected_tool:
            return False
        args = call.get("args", {})
        if expected_tool == "check_async_task":
            return args.get("task_id") == text.partition("|")[2]
        if expected_tool == "list_async_tasks":
            return args.get("status_filter") in (None, "all")
        return True

    assert calls and matches_request(calls[0]), f"首个工具必须匹配请求及其参数：{text} → {names}"
    if expected_tool in read_tools:
        assert set(names) <= read_tools, f"查询中出现额外修改：{names}"
    else:
        assert names == [expected_tool], f"修改操作必须只执行一次：{names}"
    returned = {msg.get("tool_call_id"): msg for msg in outputs}
    assert len(outputs) == len(returned) == len(calls), "工具调用与结果数量不匹配。"
    for call in calls:
        assert call.get("id") and call["id"] in returned, "工具结果的调用 ID 不匹配。"
        result = returned[call["id"]]
        assert result.get("name") == call["name"], "工具结果名称不匹配。"
        assert result.get("status", "success") == "success", "工具调用失败。"
    server.task_ids.update(state.get("async_tasks", {}))
    # 追加查询可能指向其他任务或筛选条件，只读取本次请求的最新结果。
    primary = [call for call in calls if matches_request(call)][-1]
    output = returned[primary["id"]]["content"]
    if show:
        if len(calls) > 1:
            print("本轮工具序列（包含只读状态查询）：", names)
        show_tool_output(expected_tool, output)
    return state, output

```

### 3.1 轮询：隔一会儿再问一次

**轮询**就是反复 CHECK，直到任务成功、失败或超过截止时间。`wait_task` 默认最多等 40 秒，每轮查询后暂停 1 秒，只在状态变化时打印，避免刷屏。它等待的是子任务，与上一格等待主图本轮返回不同。

两处都出现“状态”，但来源不同：

| 字段来源 | 常见值 | 怎么理解 |
|---|---|---|
| 主图 `state["async_tasks"][task_id]["status"]` | `running`、`success`、`cancelled` | 主 Agent 对这项任务的跟踪记录 |
| 服务端 `runs.get(...)["status"]` | `pending`、`running`、`success`、`interrupted` | 具体某次 run 的执行状态 |

主 Agent 标为 running 时，服务端可能还在 pending（等待调度）；取消后，主记录可为 cancelled，服务端终态可为 interrupted。它们描述不同层次，不要求字符串完全相同。最终以本例的明确状态断言和结果内容共同判断。


```python
async def wait_task(server, task_id, timeout=40):
    deadline, last_status = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        state, output = await ask(server, f"CHECK|{task_id}", "check_async_task", show=False)
        status = state["async_tasks"][task_id]["status"]
        if status != last_status:
            show_tool_output("check_async_task", output)
            last_status = status
        if status == "success":
            return state, json.loads(output)
        if status in {"error", "cancelled", "interrupted", "timeout"}:
            raise RuntimeError(f"子任务异常结束：{status}")
        await asyncio.sleep(1)
    raise TimeoutError(f"任务未在 {timeout}s 内完成")
```

## 4. 启动、列举并等待完成

这一格**定义**第一个阶段，还不会打印运行结果。按顺序读四个动作：

1. START 返回后，从 `state["async_tasks"]` 找到新 task 和 run ID。
2. 用 SDK 直接查服务端，确认 run 仍是 pending 或 running。这是“主 Agent 已返回、子任务尚未完成”的证据。
3. LIST 应包含这个 task ID；随后 `wait_task` 轮询直到成功。
4. 核对返回文本和服务端 success，再把本阶段观察结果存进字典。

第 7 节执行时，应先看到后台尚未完成的状态，稍后看到 `Research completed: 总结异步任务的状态变化`。只拿到一个 task ID，还不能算研究任务完成。


```python
async def observe_completion(server):
    print("阶段一：启动 → 列举 → 完成")
    state, output = await ask(server, "START|总结异步任务的状态变化", "start_async_task")
    task_id = next(iter(state["async_tasks"]))
    task = state["async_tasks"][task_id]
    assert task_id in output and task["status"] == "running"
    run = await server.client.runs.get(task_id, task["run_id"])
    assert run["status"] in {"pending", "running"}, run["status"]
    print("主 Agent 已返回，后台 run 仍为：", run["status"])
    _, listing = await ask(server, "LIST", "list_async_tasks")
    assert task_id in listing
    state, result = await wait_task(server, task_id)
    assert "Research completed" in result["result"]
    run = await server.client.runs.get(task_id, state["async_tasks"][task_id]["run_id"])
    assert run["status"] == "success"
    return {"阶段": "完成", "task_id": task_id, "服务状态": run["status"]}
```

## 5. 更新：同一个 task，新的 run

第二个阶段另起一个任务，再追加要求。`previous` 保存已有任务 ID；对新旧 ID 集合做差，得到刚启动的任务，避免误操作上一阶段的任务。

我们记住 `old_run`，发送 UPDATE，再比较：task ID 应保持不变，run ID 应改变。最后从主图的实际工具调用中取出 `message` 参数，并确认它出现在子图返回文本里。这样验证的是追加指令真的传到了后台，不只是一句“已更新”。

本例的 researcher 只回显最近的用户文本，不会真正生成三条摘要。offline 预期返回 `Research completed: 追加要求：使用三条要点`；真实模型若调整了工具参数的措辞，则与实际发出的参数核对。


```python
async def observe_update(server):
    print("\n阶段二：更新 → 新 run → 读取新结果")
    previous = set(server.task_ids)
    state, _ = await ask(server, "START|撰写一份简短摘要", "start_async_task")
    task_id = (set(state["async_tasks"]) - previous).pop()
    old_run = state["async_tasks"][task_id]["run_id"]
    state, output = await ask(server, f"UPDATE|{task_id}|追加要求：使用三条要点", "update_async_task")
    updated = state["async_tasks"][task_id]
    assert task_id in output and updated["run_id"] != old_run
    instructions = [call["args"]["message"] for msg in state["messages"]
                    for call in msg.get("tool_calls", []) if call["name"] == "update_async_task"]
    assert instructions and instructions[-1].strip()
    state, result = await wait_task(server, task_id)
    assert instructions[-1] in result["result"], "追加指令没有进入子图结果。"
    run = await server.client.runs.get(task_id, updated["run_id"])
    assert run["status"] == "success"
    print("已验证：task ID 不变、run ID 更新、追加指令传递成功。")
    return {"阶段": "更新", "task_id": task_id, "服务状态": run["status"]}
```

## 6. 取消：核对主 Agent 和服务端两侧

第三个阶段启动新任务，然后 CANCEL。先确认主 Agent 将任务记为 `cancelled`，再每隔 0.25 秒查询服务端，最多等 10 秒，直到对应 run 进入 `interrupted` 或 `cancelled`。

为什么要查两边？“已发出取消请求”与“服务端已经停止执行”之间可能有时间差。最后再 LIST 一次，确认三个任务都在本次跟踪记录中。真正执行这些步骤仍在第 7 节。


```python
async def observe_cancellation(server):
    print("\n阶段三：取消 → 服务端确认")
    previous = set(server.task_ids)
    state, _ = await ask(server, "START|准备一个将被取消的任务", "start_async_task")
    task_id = (set(state["async_tasks"]) - previous).pop()
    state, output = await ask(server, f"CANCEL|{task_id}", "cancel_async_task")
    task = state["async_tasks"][task_id]
    assert task_id in output and task["status"] == "cancelled"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        run = await server.client.runs.get(task_id, task["run_id"])
        if run["status"] in {"interrupted", "cancelled"}:
            break
        await asyncio.sleep(0.25)
    else:
        raise TimeoutError("服务端未确认取消")
    _, listing = await ask(server, "LIST", "list_async_tasks")
    assert all(task_id in listing for task_id in server.task_ids)
    return {"阶段": "取消", "task_id": task_id, "服务状态": run["status"]}
```

## 7. 在一个受保护的生命周期内运行

前面只定义了函数，现在才依次执行三个阶段。`await observe_...` 表示等待这个阶段的观察完成，再进入下一阶段。

`async with LocalAgentServer(...)` 是异步上下文管理器：进入时启动服务并创建主会话，正常结束或抛出 Python 异常时退出并清理资源。不要把三个阶段挪到 `async with` 外面执行，退出后服务已关闭。进程和会话管理细节见 [local_server.py](local_server.py)。

预期最后有清理提示和三行汇总：完成 → success、更新 → success、取消 → interrupted（服务也可能返回 cancelled）。中间还应看到 task ID、run 状态和实际结果，不能只凭这三行文字判断成功。服务只绑定本机地址，临时服务状态不会写入仓库。


```python
async with LocalAgentServer(CHAPTER_DIR, ROOT) as server:
    observations = []
    observations.append(await observe_completion(server))
    # 练习可在这里插入 raise，观察异常退出时的清理。
    observations.append(await observe_update(server))
    observations.append(await observe_cancellation(server))

print("\n生命周期验证结果：")
for observation in observations:
    print(observation["阶段"], "→", observation["服务状态"])
```

    Agent Server 已就绪（仅本机访问）；已创建本次主 thread。
    阶段一：启动 → 列举 → 完成


    
    start_async_task
    Launched async subagent. task_id: 01a0e2b5-184f-7390-ac75-da1660cd1b24
    主 Agent 已返回，后台 run 仍为： pending


    
    list_async_tasks
    1 tracked task(s):
    - task_id: 01a0e2b5-184f-7390-ac75-da1660cd1b24  agent: researcher  status:
      running


    
    check_async_task
    status: running
    thread_id: 01a0e2b5-184f-7390-ac75-da1660cd1b24


    
    check_async_task
    status: success
    thread_id: 01a0e2b5-184f-7390-ac75-da1660cd1b24
    result: Research completed: 总结异步任务的状态变化
    
    阶段二：更新 → 新 run → 读取新结果


    
    start_async_task
    Launched async subagent. task_id: 01a0e2b5-4354-7980-9457-c126340a0816


    
    update_async_task
    Updated async subagent. task_id: 01a0e2b5-4354-7980-9457-c126340a0816


    
    check_async_task
    status: running
    thread_id: 01a0e2b5-4354-7980-9457-c126340a0816


    
    check_async_task
    status: success
    thread_id: 01a0e2b5-4354-7980-9457-c126340a0816
    result: Research completed: 追加要求：使用三条要点
    已验证：task ID 不变、run ID 更新、追加指令传递成功。
    
    阶段三：取消 → 服务端确认


    
    start_async_task
    Launched async subagent. task_id: 01a0e2b5-6e63-7f11-b774-3495f850286e


    
    cancel_async_task
    Cancelled async subagent task: 01a0e2b5-6e63-7f11-b774-3495f850286e


    
    list_async_tasks
    3 tracked task(s):
    - task_id: 01a0e2b5-184f-7390-ac75-da1660cd1b24  agent: researcher  status:
      success
    - task_id: 01a0e2b5-4354-7980-9457-c126340a0816  agent: researcher  status:
      success
    - task_id: 01a0e2b5-6e63-7f11-b774-3495f850286e  agent: researcher  status:
      cancelled
    本次创建的任务、thread、服务进程与临时状态已清理。
    
    生命周期验证结果：
    完成 → success
    更新 → success
    取消 → interrupted


## 回顾：本次到底验证了什么？

启动时拿到 task ID 不等于后台完成；更新保留任务但新建 run；取消需要确认实际执行已停止。五个工具通过真实 supervisor 调用，服务状态和结果来自实际本地 Agent Server。

脚本模型不证明真实模型会选对工具，固定 researcher 不证明研究质量，本机服务实验也不代表远程部署性能。

### 练习：任务还在后台时发生异常

先预测：如果 Notebook 在子任务尚未完成时抛出异常，服务和会话是否还会被清理？保持 offline，在**新的代码格**运行以下练习；前面的函数定义应已执行。

```python
async with LocalAgentServer(CHAPTER_DIR, ROOT) as server:
    state, _ = await ask(server, "START|清理练习", "start_async_task")
    task_id, task = next(iter(state["async_tasks"].items()))
    run = await server.client.runs.get(task_id, task["run_id"])
    assert run["status"] in {"pending", "running"}
    raise ValueError("练习：后台任务未完成就退出")
```

这次红色 `ValueError` 是预期现象，不是安装失败。观察清理提示和“失败诊断日志”的临时路径：异常会触发退出清理，同时保留日志供排查。不要删除后台状态断言来强行通过练习。恢复时删除这格练习，重启内核并全部运行原始 Notebook；新的正常运行只删除它自己的日志；这次失败练习留下的旧日志不会被重跑删除，查看后可手动删除报错中列出的那个日志文件。

### 遇到问题先检查哪里

| 现象 | 检查与恢复 |
|---|---|
| 定义阶段没有输出 | `async def` 尚未执行，继续到第 7 节；不是后台卡住 |
| 缺少 `langgraph` CLI 或 server 依赖 | 回到第 1 节的 `uv sync ... --extra server`，确认项目内核 |
| 服务提前退出 / 启动超时 | 查看报错给出的临时日志路径，确认本机允许绑定端口；修复后重跑完整生命周期 |
| 启动时 run 已经 success，异步观察断言失败 | live 模型响应可能错过 8 秒观察窗口；可增加 researcher 的等待时间后重跑，不应删除断言 |
| CHECK 超时或任务 error | 先看实际状态与结果；40 秒是观察上限，不表示所有任务必定在此时间内完成 |
| live 的 401、网络错误或选错工具 | 检查模型配置与调用记录；不会自动退回 offline |

无需手动预先启动服务。正常 Python 异常由上下文管理器清理；强制结束整个内核或进程不属于这个异常清理实验。下一步回看 [同步委派中的消息与文件边界](../ch05/01-subagent-delegation.ipynb)，比较同步等待与后台任务的区别。
