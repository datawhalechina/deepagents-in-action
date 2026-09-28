> 本次执行模式：**offline**。源码指纹：`49c81ae1afe9`。

# 第 10 章实验：Agent 在哪里运行代码，报告怎样带回来？

对应[第 10 章正文](../../content/ch10-sandboxes.md)。假设要汇总三笔订单：应用提供数据，Agent 在沙箱里运行 Python，应用最后取回报告。运行命令和下载文件分别由谁完成？命令失败时，应该看哪个字段？

本实验使用**真实的本地 Docker 容器**。Docker 把程序放进独立的运行环境；这里不挂载宿主目录，不把模型密钥传入容器，并关闭容器网络。它不是远程托管沙箱，也不是把宿主临时目录当成沙箱。

| 要观察什么 | 应看到什么 |
|---|---|
| 宿主传入输入 | `upload_files()` 的两项结果均无错误 |
| Agent 执行程序 | `execute` 请求对应实际命令结果，退出码为 0 |
| Agent 查看报告 | `read_file` 返回生成的文件内容 |
| 宿主取回产物 | 下载的 JSON 中有 3 笔订单、总额 75 |
| 失败与清理 | 缺失文件有逐项错误；失败命令退出码为 7；退出实验后容器不存在 |

默认脚本模型只安排工具请求，Python 程序、文件传输、框架与容器都实际运行。随附输出不证明真实模型会编写程序或正确选择工具。

## 1. 环境与运行模式

只需基础 Python。本 Notebook 从第一格建立自己的变量；Jupyter / VS Code 的**内核**是运行这些变量的 Python 进程，不依赖前几章的内核状态。

按[公共 README](../README.md) 安装 Python 3.12 的锁定环境，并安装、启动 [Docker Desktop](https://docs.docker.com/desktop/) 或可用的 Docker Engine。Windows 建议使用 Docker Desktop 的 Linux 容器模式。先在仓库根目录的**终端**运行：

```bash
docker info
uv sync --project notebooks --locked
uv run --project notebooks --locked python -m course_notebooks.run ch10-sandboxes
```

默认 **offline** 不调用模型 API，但仍需要 Docker；首次运行会下载固定摘要的 Python 镜像，需要访问镜像仓库，后续使用本地缓存。未安装 Docker、Engine 未启动或镜像下载失败都会报错，不改用宿主 Shell。镜像详情与 Backend 适配代码见 [docker_sandbox.py](docker_sandbox.py)。

使用真实模型时，按 README 配置未提交的根目录 `.env`，在执行命令末尾添加 `--mode live`。交互式内核先执行 `import os` 并设置 `os.environ["COURSE_MODE"] = "live"`，再从导入格顺序运行。模型 API 可能收费；live 失败不会退回 offline。本例在两种模式中都运行预先提供的分析程序，验证的不是模型自行编程能力。


```python
import json
import sys
from textwrap import dedent

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, ToolMessage

from course_notebooks.model_config import create_model, repository_root
from course_notebooks.nbtools import show_runtime, show_text
from course_notebooks.testing import ScriptedChatModel

chapter_dir = repository_root() / "notebooks" / "ch10"
if str(chapter_dir) not in sys.path:
    sys.path.insert(0, str(chapter_dir))
from docker_sandbox import DockerSandbox, IMAGE, container_exists, docker

show_runtime()
print("Docker Engine：", docker("info", "--format", "{{.ServerVersion}}").decode().strip())
show_text("固定的容器镜像：", IMAGE, width=90)
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Darwin arm64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


    Docker Engine： 29.1.3
    
    固定的容器镜像：
    python@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e


### 先认清宿主、Backend 和容器

宿主是运行 Notebook 和 Agent 的环境。**Backend** 是框架调用文件或执行接口时使用的后端对象，本例把调用转给 Docker 容器。Agent 自身的模型循环仍在宿主上，只有程序和文件操作在容器里；正文把这种方式叫 **Sandbox as tool**。

```text
宿主：准备输入 → upload_files() → 容器中的数据与程序
宿主：Agent 的模型提出 execute 请求
                         ↓
               Backend → 容器运行 Python，生成报告
                         ↓
宿主：模型收到 ToolMessage，提出 read_file 请求并读取报告
宿主：download_files() ← 容器中的报告
```

`AIMessage.tool_calls` 只表示模型提出了请求；框架真正执行后，用 `ToolMessage` 记录结果，并通过 `tool_call_id` 对应原请求的 `id`。`invoke()` 启动这段循环，返回的 `result["messages"]` 保存消息历史，属于 Agent 的 **State（运行数据）**。

| 接口 | 谁调用 | 本例的作用 |
|---|---|---|
| `upload_files()` | 宿主应用代码 | 在任务开始前传入数据与程序，内容是 `bytes` |
| `execute`、`read_file` | Agent 通过框架调用 | 在容器内执行程序、查看文件 |
| `download_files()` | 宿主应用代码 | 任务结束后取回报告，每个文件单独返回结果 |

容器网络关闭不会阻止宿主调用模型 API。这里没有挂载宿主目录，容器也没有继承宿主的模型配置；上传哪些数据仍由应用决定。

## 2. 准备数据与分析程序

先在宿主内存中准备三笔订单与一个短程序。程序在容器里读取 `/workspace/orders.json`，计算“数量 × 单价”的总和，写入 `/workspace/report.json`。这些绝对路径属于容器，不是本机路径。

`dedent()` 去掉多行字符串的公共缩进，使程序能直接作为文件执行。`encode("utf-8")` 将文本变成上传 API 接收的字节；后面下载时再解码。价格使用整数，避免在这个小实验中讨论小数舍入。


```python
ORDERS = [
    {"item": "纸张", "quantity": 2, "price": 10},
    {"item": "笔", "quantity": 3, "price": 5},
    {"item": "书", "quantity": 1, "price": 40},
]
PROGRAM = dedent("""
    import json
    from pathlib import Path

    rows = json.loads(Path("/workspace/orders.json").read_text(encoding="utf-8"))
    report = {
        "orders": len(rows),
        "total": sum(row["quantity"] * row["price"] for row in rows),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    Path("/workspace/report.json").write_text(text, encoding="utf-8")
    print(text)
""")
INPUT_FILES = [
    ("/workspace/orders.json", json.dumps(ORDERS, ensure_ascii=False).encode("utf-8")),
    ("/workspace/analyze.py", PROGRAM.encode("utf-8")),
]
CALLS = [
    {"name": "execute", "args": {"command": "python /workspace/analyze.py"},
     "id": "ch10-execute"},
    {"name": "read_file", "args": {"file_path": "/workspace/report.json"},
     "id": "ch10-read"},
]
show_text("本次输入：", json.dumps(ORDERS, ensure_ascii=False, indent=2))
print("预期总额：2 × 10 + 3 × 5 + 1 × 40 = 75")
```

    
    本次输入：
    [
      {
        "item": "纸张",
        "quantity": 2,
        "price": 10
      },
      {
        "item": "笔",
        "quantity": 3,
        "price": 5
      },
      {
        "item": "书",
        "quantity": 1,
        "price": 40
      }
    ]
    预期总额：2 × 10 + 3 × 5 + 1 × 40 = 75


数据已经准备好，但还没有创建容器或执行程序。`CALLS` 列出本次任务需要的两个调用：先运行程序，再读取报告。offline 模型会按这个顺序提出请求；live 模型会收到同样的任务要求。

## 3. 给 Agent 接入执行后端

`create_deep_agent()` 把模型与工具组装成可执行的图（Graph），也就是前面看到的循环流程。传入 `backend=...` 指定文件与命令执行的后端。框架识别 `SandboxBackendProtocol` 后才向模型提供 `execute`；本例的 `DockerSandbox` 继承 `BaseSandbox`，实现执行、上传、下载与 `id`，其余文件工具复用基类实现。

`DockerSandbox` 是本章自定义的教学后端，不是 Deep Agents 官方内置类。它通过 Docker CLI 创建、操作和回收真实容器；上传、下载把字节交给容器里的固定 Python 脚本，不调用模型，也不把传输包装成 Agent 的 `execute` 请求。[查看适配源码](docker_sandbox.py)。远程 Provider 的原生传输方式仍应参考对应 SDK。

容器使用非 root 用户、只读根文件系统，只有 `/workspace` 和 `/tmp` 各有 16 MiB 可写空间；上限为 256 MiB 内存、1 个 CPU、64 个进程。单条命令最多 30 秒，日志最多读取 32 KiB，更多输出标为 `truncated`。命令超时返回退出码 124；若 Docker 通信本身超时，则回收容器并终止实验。这些是本实验的配置，不是所有 Provider 的默认值。

`task_input()` 把工具名和参数整理成用户消息；`make_agent()` 为每个实验组装 Agent，并创建新模型。offline 的响应列表按当前实验的 `planned_calls` 依次提出请求，最后给出结束回复；它不会检查工具结果，列表也会循环。下面仍要验证真实调用、退出码和文件内容。live 使用公共 `create_model()` 配置真实模型，任务不符合要求时断言报错。


```python
def make_agent(backend, planned_calls):
    responses = [AIMessage(content="", tool_calls=[call]) for call in planned_calls]
    responses.append(AIMessage(content="本轮结束；请核对实际退出码和下载的报告。"))
    model = create_model(ScriptedChatModel(responses=responses))
    return create_deep_agent(
        model=model,
        backend=backend,
        system_prompt=(
            "仅按用户给出的顺序调用指定工具，参数原样保留。"
            "不要委派、规划、安装依赖或调用其他工具。"
            "读取报告后结束；若命令失败，说明失败并结束，不要重试。"
        ),
    )


def task_input(calls):
    tasks = [{"name": call["name"], "args": call["args"]} for call in calls]
    return {"messages": [("user", "依次完成以下工具任务：\n" +
                          json.dumps(tasks, ensure_ascii=False, indent=2))]}
```

## 4. 一次完成上传、运行、下载与回收

把需要容器的操作放在同一个 `with DockerSandbox()` 中。`with` 进入时创建容器，正常结束或抛出异常时都会调用回收；不依赖读者再执行最后一个清理格。若内核被强行终止、来不及清理，容器的主进程也只存活 5 分钟，退出后由 Docker 的 `--rm` 删除。

下一格按顺序做四件事：

1. 查看容器配置，并用 `python --version` 检查真实执行环境。
2. 用 `upload_files()` 传入两个文件，逐项核对 `error`。
3. 用 `invoke()` 启动 Agent，让它执行程序、读取报告。
4. 下载报告和一个故意不存在的文件，观察下载可以部分成功。

结果保留在宿主变量 `result`、`report` 中，离开 `with` 后还可以检查它们；容器里的文件则随回收消失。只展示相关配置，不打印完整容器信息或宿主路径。`recursion_limit=24` 限制图的执行步数，避免 live 模型反复请求工具；它不是费用上限。


```python
with DockerSandbox() as backend:
    container_name = backend.id
    info = backend.inspect()
    assert info["HostConfig"]["NetworkMode"] == "none"
    assert info["HostConfig"]["ReadonlyRootfs"] and info["Mounts"] == []
    assert not any(value.startswith(("MODEL_", "SILICONFLOW_"))
                   for value in info["Config"]["Env"])
    print("容器配置：网络关闭；根文件系统只读；无宿主挂载。")
    runtime = backend.execute("python --version")
    assert runtime.exit_code == 0
    show_text("容器运行时：", runtime.output)

    uploads = backend.upload_files(INPUT_FILES)
    assert len(uploads) == len(INPUT_FILES)
    for upload, (path, _) in zip(uploads, INPUT_FILES):
        assert upload.path == path and upload.error is None
        print("上传成功：", upload.path)

    agent = make_agent(backend, CALLS)
    result = agent.invoke(task_input(CALLS), config={"recursion_limit": 24})
    downloads = backend.download_files([
        "/workspace/report.json", "/workspace/missing.json",
    ])
    assert downloads[0].error is None and downloads[0].content is not None
    assert downloads[1].content is None and downloads[1].error == "file_not_found"
    report = json.loads(downloads[0].content.decode("utf-8"))
    show_text("宿主下载的报告：", json.dumps(report, ensure_ascii=False, indent=2))
    print("缺失文件的逐项错误：", downloads[1].error)

assert not container_exists(container_name), "容器没有回收"
print("容器已回收；报告副本仍保存在宿主变量 report 中。")
```

    容器配置：网络关闭；根文件系统只读；无宿主挂载。
    
    容器运行时：
    Python 3.12.14


    上传成功： /workspace/orders.json
    上传成功： /workspace/analyze.py


    
    宿主下载的报告：
    {
      "orders": 3,
      "total": 75
    }
    缺失文件的逐项错误： file_not_found
    容器已回收；报告副本仍保存在宿主变量 report 中。


输出中的 `orders: 3`、`total: 75` 来自实际下载的文件。第二个文件返回 `file_not_found`，没有影响第一个文件下载。最后的回收检查确认资源已删除；镜像缓存仍保留，后续运行可以复用。

这还不能单独证明 Agent 按要求用了工具：应用本身也可以执行 Backend 接口。下一节将下载内容与 Agent 消息链对应起来。

## 5. 核对请求、结果和实际产物

`check_loop()` 检查工具名与参数符合任务要求，每个返回消息都对应原调用 ID，并打印结果。嵌套推导式先遍历模型消息，再取出各条消息中的调用；`zip()` 将每个调用和它的返回配对。本例按顺序运行工具，因此也检查返回的顺序。

`execute` 的 `ToolMessage.artifact["exit_code"]` 保存命令退出码，**0 才表示程序成功**。`read_file` 的结果先用 `@@ lines ... @@` 标明读取范围，下面才是 JSON 内容。检查时用 `partition("\n")` 去掉第一行范围提示，再解析 JSON，与宿主下载后解析出的 JSON 对象比较。


```python
def check_loop(result, planned_calls):
    messages = result["messages"]
    calls = [call for message in messages if isinstance(message, AIMessage)
             for call in message.tool_calls]
    actual = [{"name": call["name"], "args": call["args"]} for call in calls]
    expected = [{"name": call["name"], "args": call["args"]} for call in planned_calls]
    assert actual == expected, "工具名称、参数或调用顺序与任务要求不同"
    replies = [message for message in messages if isinstance(message, ToolMessage)]
    assert len(replies) == len(calls), "工具结果数量不符"
    for call, reply in zip(calls, replies):
        assert reply.tool_call_id == call["id"] and reply.name == call["name"]
        assert reply.status == "success", "工具接口调用出错"
        print("请求工具：", call["name"])
        show_text("  参数：", json.dumps(call["args"], ensure_ascii=False, indent=2))
        print("  调用 ID：", reply.tool_call_id)
        print("  工具消息状态：", reply.status)
        if reply.name == "execute":
            print("  命令退出码：", reply.artifact["exit_code"])
        show_text("  工具实际返回：", reply.text)
    assert isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls
    return replies

replies = check_loop(result, CALLS)
assert replies[0].artifact["exit_code"] == 0, "分析程序执行失败"
read_report = json.loads(replies[1].text.partition("\n")[2])
assert read_report == report, "Agent 读取的内容与宿主下载的报告不一致"
assert report == {"orders": 3, "total": 75}, "报告不符合三笔订单、总额 75 的要求"
print("已核对：执行请求、成功退出码、读取请求与下载报告一致。")
```

    请求工具： execute
    
      参数：
    {
      "command": "python /workspace/analyze.py"
    }
      调用 ID： ch10-execute
      工具消息状态： success
      命令退出码： 0
    
      工具实际返回：
    {
      "orders": 3,
      "total": 75
    }
    
    [Command succeeded with exit code 0]
    请求工具： read_file
    
      参数：
    {
      "file_path": "/workspace/report.json"
    }
      调用 ID： ch10-read
      工具消息状态： success
    
      工具实际返回：
    @@ lines 1-4 of 4 @@
    {
      "orders": 3,
      "total": 75
    }
    已核对：执行请求、成功退出码、读取请求与下载报告一致。


应看到 `execute → read_file` 两个请求及各自的结果；退出码为 0，文件读取和宿主下载均显示总额 75。上传、下载不是模型提出的工具调用，而是上一格的应用代码。

## 6. 命令失败：工具消息成功不等于程序成功

新建一个独立容器，运行会打印说明并以 **7** 退出的 Python 命令。这不是分析任务的一部分，而是有意观察失败返回。脚本模型随后照常给出结束回复，因此尤其需要检查真实退出码。

锁定版本中，Backend 成功返回执行结果时，框架生成的工具消息仍可能是 `status="success"`；它表示工具接口返回了结果。程序是否成功还要看 `artifact["exit_code"]`。不要把这里的语义套到第 9 章的拒绝反馈上。


```python
FAIL_PROGRAM = b"print('planned failure')\nraise SystemExit(7)\n"
FAIL_CALLS = [{
    "name": "execute", "args": {"command": "python /workspace/fail.py"},
    "id": "ch10-failure",
}]
with DockerSandbox() as failed_backend:
    failed_container = failed_backend.id
    uploaded = failed_backend.upload_files([("/workspace/fail.py", FAIL_PROGRAM)])
    assert uploaded[0].error is None
    failed_agent = make_agent(failed_backend, FAIL_CALLS)
    failed_result = failed_agent.invoke(
        task_input(FAIL_CALLS), config={"recursion_limit": 24},
    )

failed_replies = check_loop(failed_result, FAIL_CALLS)
assert failed_replies[0].artifact["exit_code"] == 7
assert "planned failure" in failed_replies[0].text
assert not container_exists(failed_container), "失败实验留下了容器"
print("命令确实失败；执行结果已返回；失败实验的容器也已回收。")
```

    请求工具： execute
    
      参数：
    {
      "command": "python /workspace/fail.py"
    }
      调用 ID： ch10-failure
      工具消息状态： success
      命令退出码： 7
    
      工具实际返回：
    planned failure
    
    [Command failed with exit code 7]
    命令确实失败；执行结果已返回；失败实验的容器也已回收。


输出中工具消息状态是 `success`，命令退出码却是 7，并带有实际程序打印的 `planned failure`。这说明工具调用成功返回了一个失败的命令结果；最终模型回复不能把它变成成功。

## 7. 练习、边界与常见问题

### 改一个变量再观察

1. 只把第 2 节第一笔订单的 `price` 从 10 改成 12，先预测总额：应该从 75 变成多少？
2. 重启内核并全部运行。第 4 节下载的报告应显示 **79**，第 5 节仍要求 75 的业务断言会失败；这不是执行失败，而是输入已改变，原验收要求不再匹配。
3. 此时第 4 节的容器已经回收，报错不会留下任务环境。恢复价格 10，重启内核并全部运行，两个实验都应通过。

### 本实验验证到哪里？

- 验证真实本地容器、Backend 接口、Agent 工具循环、文件传输与正常/异常退出清理；offline 不验证模型推理或自动编程质量。
- 不验证 LangSmith、Daytona 等远程 Provider 的账号、网络、费用、TTL 或复用行为。换成远程 Backend 时仍要沿用对应 Provider 的创建与销毁接口。
- 容器的网络、挂载与资源限制是实验配置，不是对恶意代码的完整安全保证；容器仍依赖 Docker Engine 的隔离机制。下载产物也应由应用检查后使用，本例只解析 JSON，不执行下载的代码。
- Backend 将超过 32 KiB 的命令输出标为 `truncated=True`；部分输出不能当作完整日志。本例输出很短，不演示正文的长日志保存流程。
- `with` 会处理正常返回和 Python 异常；若 Docker Engine 不可达，回收会明确报错，不能把连接失败当作“容器已经不存在”。镜像缓存与 Docker Engine 本身不由本实验删除或关闭。

| 现象 | 检查什么 |
|---|---|
| Docker 命令不存在或连接失败 | 安装 Docker，启动 Engine，先在终端确认 `docker info` 成功 |
| 首次镜像下载失败 | 检查 Docker 到镜像仓库的网络；镜像摘要在适配文件中，不随意换成其他镜像 |
| 报告下载结果的 `content` 为 `None` | 逐项检查 `error`，确认程序成功并写入目标路径 |
| `execute` 结果是非零退出码 | 查看实际命令输出；消息状态或模型说完成都不能替代退出码 |
| live 调用顺序断言失败 | 核对模型提出的工具与参数；不以 offline 结果代替这次真实模型结果 |

实验中的容器已回收，剩余报告只是宿主内存中的副本；重启内核即可清空变量。回到[第 10 章正文](../../content/ch10-sandboxes.md)了解远程集成、文件平面与生命周期；制作章节时参考[贡献指南](../CONTRIBUTING.md)。
