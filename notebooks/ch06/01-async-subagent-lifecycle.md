> 本次执行模式：**offline**。源码指纹：`a4054c55a3a2`。

# 第 6 章｜异步子 Agent 的完整生命周期

对应 [第 6 章正文](../../content/ch06-async-subagents.md)。本实验从 Notebook 启动真实本地 Agent Server，观察 supervisor 通过 ASGI 委派后的后台任务。

**学习目标**：说明主任务返回与后台任务完成的区别；使用五个异步工具；通过 task/thread/run ID 和真实服务状态验证完成、更新与取消。

**预期现象**：启动返回时子任务尚在运行；更新保留 task ID 并创建新 run；取消后主 Agent 记录 cancelled，服务端 run 进入 interrupted。

## 1. 环境与模式

按 [统一安装说明](../README.md) 使用 Python 3.12 和 server 依赖组：

```bash
uv sync --project notebooks --locked --extra server
uv run --project notebooks --locked --extra server python -m course_notebooks.run ch06-async-subagents
```

默认 offline 用脚本模型规定 supervisor 选择哪个工具，服务、中间件、SDK 和后台图都真实执行。随附输出来自本次 offline 运行；它不证明真实模型的选工具能力。切换真实模型需按 README 配置并显式添加 `--mode live`，可能产生模型费用。无需远程部署，也不要求 LangSmith Key。


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

```text
Notebook（SDK 客户端）
  └─ 本地 Agent Server
       ├─ supervisor：主 Agent，选择异步工具
       └─ researcher：后台图，等待后返回结果
            ↑ AsyncSubAgent 通过同部署的 ASGI 路径调用
```

| 名称 | 本例含义 | 更新任务时 |
|---|---|---|
| graph_id | 服务器中注册的图，如 researcher | 保持不变 |
| thread_id | 一段有状态的会话 | 子 thread 不变 |
| task_id | 主 Agent 跟踪的子任务 ID，本例等于子 thread_id | 保持不变 |
| run_id | 在该 thread 上的一次执行 | 创建新的 run |

`async def` 定义可等待的函数，`await` 在等待网络或后台结果时让出执行权。真正的后台任务由 Agent Server 调度，不是 Notebook 自己创建一个 Python await 就模拟出来的。

服务注册见 [langgraph.json](langgraph.json)，主图见 [supervisor.py](graphs/supervisor.py)。下面直接展示当前文件中的核心构造，避免维护第二份实现。


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

researcher 故意等待 8 秒后回传输入，给查询、更新和取消留出窗口。它是固定教学图，不进行真实研究，也不用于比较研究质量或远程部署性能。


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



## 3. 如何检查一次工具调用？

`ask` 向服务端 supervisor 发送消息，再读取本轮的真实工具调用和返回。两种模式共用 `START|说明`、`CHECK|task_id` 等命令协议：offline 回调负责解析；live 的系统提示明确列出命令与工具参数的映射。

返回 state 是服务端运行后的状态。启动、更新和取消必须只执行一次指定操作；列举和查询允许模型追加只读状态查询，但不能夹带启动、更新或取消。每条结果都要核对工具名、调用 ID 和成功状态；不能只相信模型说“已完成”。实际工具序列会在出现额外查询时显示。轮询只在状态改变时打印，并设置截止时间。


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

启动应立即给出 task ID。随后读服务端 run 状态，证明后台任务仍在执行；查询成功后核对实际结果。先定义每个阶段，最后在同一生命周期中执行，确保任何阶段失败都能清理。


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

另起一个任务，再追加要求。验证 task ID 没变、run ID 已变，并核对实际发送的追加指令进入了子图结果。真实模型可以改写措辞，因此检查工具实际参数，不要求逐字复述用户提示。


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

取消第三个任务后，主 Agent 的跟踪状态为 cancelled；服务端确认 run 进入 interrupted 或 cancelled 后才算验证完成。


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

`async with` 进入时启动服务并等待就绪；正常完成或抛出异常，退出时都会清理。辅助代码只管理本次创建的资源，见 [local_server.py](local_server.py)。核心工具调用与断言仍在上面的阶段函数中。

下面的输出按三个阶段排列。只绑定本机地址；所有实验状态在临时服务目录，不污染仓库。


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
    Launched async subagent. task_id: 01a0dd0f-7b31-7020-9377-d7ebd983eedf
    主 Agent 已返回，后台 run 仍为： pending


    
    list_async_tasks
    1 tracked task(s):
    - task_id: 01a0dd0f-7b31-7020-9377-d7ebd983eedf  agent: researcher  status:
      running


    
    check_async_task
    status: running
    thread_id: 01a0dd0f-7b31-7020-9377-d7ebd983eedf


    
    check_async_task
    status: success
    thread_id: 01a0dd0f-7b31-7020-9377-d7ebd983eedf
    result: Research completed: 总结异步任务的状态变化
    
    阶段二：更新 → 新 run → 读取新结果


    
    start_async_task
    Launched async subagent. task_id: 01a0dd0f-a63b-7bc3-b9ed-338b44d053ac


    
    update_async_task
    Updated async subagent. task_id: 01a0dd0f-a63b-7bc3-b9ed-338b44d053ac


    
    check_async_task
    status: running
    thread_id: 01a0dd0f-a63b-7bc3-b9ed-338b44d053ac


    
    check_async_task
    status: success
    thread_id: 01a0dd0f-a63b-7bc3-b9ed-338b44d053ac
    result: Research completed: 追加要求：使用三条要点
    已验证：task ID 不变、run ID 更新、追加指令传递成功。
    
    阶段三：取消 → 服务端确认


    
    start_async_task
    Launched async subagent. task_id: 01a0dd0f-d162-7021-ba70-5ee53b40ad71


    
    cancel_async_task
    Cancelled async subagent task: 01a0dd0f-d162-7021-ba70-5ee53b40ad71


    
    list_async_tasks
    3 tracked task(s):
    - task_id: 01a0dd0f-7b31-7020-9377-d7ebd983eedf  agent: researcher  status:
      success
    - task_id: 01a0dd0f-a63b-7bc3-b9ed-338b44d053ac  agent: researcher  status:
      success
    - task_id: 01a0dd0f-d162-7021-ba70-5ee53b40ad71  agent: researcher  status:
      cancelled


    本次创建的任务、thread、服务进程与临时状态已清理。
    
    生命周期验证结果：
    完成 → success
    更新 → success
    取消 → interrupted


## 观察结论、练习与故障定位

- 五个工具通过真实 supervisor 调用；task ID 对应子 thread，run ID 标识一次执行。
- 更新保留 task ID 并创建新 run；取消同时检查主 Agent 状态和服务端终态。
- 本例只验证本地服务、ASGI 与生命周期；脚本模型不验证真实模型选择工具，固定 researcher 不验证研究质量。
- **练习**：在最后一格首个阶段之后主动 `raise ValueError("练习：提前退出")`，观察清理仍发生，失败日志保留；恢复后重跑。章内回归测试也覆盖后台任务运行时失败的清理。
- 找不到 CLI 时安装 server 依赖组；启动失败或超时会报告临时日志路径。live 的认证、网络或工具选择失败需要按实际错误处理。
- 8 秒是为了观察后台运行的教学窗口；真实模型响应很慢时可能错过窗口，可增加 researcher 中的等待时间后重跑，不应删除状态断言冒充已观察到异步执行。

清理成功时删除日志；失败时保留诊断日志。无需手动启动或关闭服务。下一步可回看 [同步子 Agent 的消息与文件边界](../../content/ch05-subagents.md)，区分进程内委派与服务端后台任务。
