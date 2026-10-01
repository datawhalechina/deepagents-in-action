> 本次执行模式：**offline**。源码指纹：`9bad9627b4a3`。

# 第 2 章 Notebook（一）：快速上手与自定义工具

对应课程章节：[第 2 章：快速上手 — 5 分钟构建你的第一个 Deep Agent](../../content/ch02-quickstart.md)，覆盖「Hello World：最简单的 Deep Agent」「编写自定义工具」「小试牛刀：写一个计算器 Agent」三节。

正文用几行代码就让 Agent 回答了天气、做了货币换算。可是只看最后一句回答，我们无法确定工具真的运行过：模型也可能直接“编”一个数字。这份 Notebook 把一次 `invoke()` 拆开，逐条查看模型请求了哪个工具、传了什么参数、Python 函数实际返回了什么。

你只需基础 Python，不必预先掌握 LangChain。若还没见过工具调用，建议先做 [最小工具实验](../_template/01-minimal-tool.ipynb)。本 Notebook 可以单独从第一格运行，不依赖 Tavily、数据库或沙箱。

## 学习目标

跑完本 Notebook 后，你应该能够：

1. 用 `create_deep_agent()` 跑通正文的 Hello World，并读懂 `agent.invoke()` 返回的 `messages`；
2. 说明工具“三要素”（类型标注、docstring、默认值）分别变成了工具 Schema 里的哪个字段；
3. 在消息中找到 `AIMessage.tool_calls` 和对应的 `ToolMessage`，用工具名、参数和计算结果确认工具真的被调用；
4. 区分两类工具失败：参数不符合 Schema 时框架返回错误消息，函数内部抛出异常时整次运行中断。

**预期现象**：天气工具返回 `It's always sunny in 北京!`；换算工具返回 `{"amount": 720.0, "currency": "CNY"}`，计算工具算出 `777.6`。检查格会打印“已验证”；只看到模型最后一句回复不算完成。

## 运行环境与运行模式

使用课程锁定的 Python 3.12 环境，安装与内核选择见 [Notebook 索引](../README.md)。在仓库根目录执行下面的命令，可以从第一格完整运行本实验：

```bash
uv sync --project notebooks --locked
uv run --project notebooks --locked python -m course_notebooks.run ch02-quickstart
```

核心依赖：deepagents 0.7.15、langchain 1.4.2、langgraph 1.2.11、langchain-openai 1.6.2；完整依赖由 uv.lock 锁定。下一格输出本次实际环境。

默认 **offline** 模式使用脚本模型：模型消息是预先写好的，工具函数和 Agent 框架仍真实执行。随附输出来自这个模式；它验证框架机制，不证明真实模型会正确选择工具。需要真实模型时，按 [统一配置说明](../README.md) 准备 Key，再在上面的命令末尾加 `--mode live`。live 需要网络，可能产生调用费用；缺配置或调用失败会直接报错，不会退回脚本模型。


```python
from course_notebooks.nbtools import show_runtime

show_runtime()
```

    运行模式： offline （脚本模型）
    Python： 3.12.13 平台： Windows AMD64
    deepagents==0.7.15
    langchain==1.4.2
    langgraph==1.2.11
    langchain-openai==1.6.2


## 1. Hello World：最简单的 Deep Agent

正文的 Hello World 由三部分组成：一个模型、一个 `get_weather` 工具、一次 `create_deep_agent()`。正文这样创建模型：

```python
model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct"),
    api_key=os.environ["SILICONFLOW_API_KEY"],
    base_url="https://api.siliconflow.cn/v1",
)
```

Notebook 里改用课程辅助函数 `create_model(...)`：live 模式下它按同样的环境变量创建 `ChatOpenAI`；默认 offline 模式下，它直接返回我们传入的脚本模型，不读取 Key、不发网络请求。其余代码与正文一致。

脚本模型 `ScriptedChatModel` 按顺序回放 `responses` 列表里的消息。`AIMessage` 表示“模型发出的消息”：第一条不含普通文字，只在 `tool_calls` 里请求调用 `get_weather`；第二条是结束对话的回复。

| 字段 | 本例的值 | 含义 |
|---|---|---|
| `name` | `get_weather` | 请求哪个工具 |
| `args` | `{"city": "北京"}` | 传给函数的参数 |
| `id` | `ch02-weather` | 本次调用的编号，工具结果会用它回指请求 |

创建这些消息时还没有执行任何工具。


```python
from langchain_core.messages import AIMessage, ToolMessage
from course_notebooks.model_config import create_model
from course_notebooks.testing import ScriptedChatModel

CITY = "北京"

weather_model = create_model(ScriptedChatModel(responses=[
    AIMessage(content="", tool_calls=[{
        "name": "get_weather", "args": {"city": CITY}, "id": "ch02-weather",
    }]),
    AIMessage(content=f"（脚本预设回复）已查询{CITY}的天气，结果见工具返回。"),
]))
print("模型接口：", type(weather_model).__name__)
```

    模型接口： ScriptedChatModel


### 1.1 定义工具，运行 Agent

`get_weather` 是一个普通 Python 函数，没有加任何装饰器。把它放进 `tools=[...]`，`create_deep_agent()` 会读取函数名、参数类型和 docstring，自动整理成模型能看懂的工具说明。

`agent.invoke(...)` 才真正开始运行：输入是一个字典，其中 `messages` 是对话列表，`{"role": "user", "content": ...}` 表示用户说的话。运行一直持续到模型不再请求工具为止。最后一行和正文一样，只打印最后一条消息的文字。


```python
from deepagents import create_deep_agent


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


agent = create_deep_agent(
    model=weather_model,
    tools=[get_weather],
    system_prompt="You are a helpful assistant.",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "北京今天天气怎么样？"}]}
)

print(result["messages"][-1].content)
```

    （脚本预设回复）已查询北京的天气，结果见工具返回。


### 1.2 `invoke()` 返回了什么？

上一格只打印了最后一句话，这句话在 offline 模式下是预先写好的，不能说明工具运行过。`result` 其实是一个字典，保存运行结束时的 Agent **状态**（state），也就是各步骤之间传递的数据。先看它有哪些键，再逐条看 `result["messages"]`：

- 消息类型 `human`、`ai`、`tool` 分别对应用户、模型和工具结果；
- 模型消息如果请求了工具，明细打印在 `tool_calls` 里；
- 工具消息（`ToolMessage`）用 `tool_call_id` 指向它回应的那次请求，`status` 表示执行成功还是出错。


```python
print("状态中的键：", sorted(result))
print("消息条数：", len(result["messages"]))
for index, message in enumerate(result["messages"]):
    print(f"[{index}] {message.type:<5} {type(message).__name__:<12} {str(message.content)[:80]}")
    if isinstance(message, AIMessage):
        for call in message.tool_calls:
            print("      请求工具:", call["name"], "参数:", call["args"], "调用 ID:", call["id"])
    if isinstance(message, ToolMessage):
        print("      回应调用 ID:", message.tool_call_id, "工具:", message.name, "状态:", message.status)
```

    状态中的键： ['files', 'messages']
    消息条数： 4
    [0] human HumanMessage 北京今天天气怎么样？
    [1] ai    AIMessage    
          请求工具: get_weather 参数: {'city': '北京'} 调用 ID: ch02-weather
    [2] tool  ToolMessage  It's always sunny in 北京!
          回应调用 ID: ch02-weather 工具: get_weather 状态: success
    [3] ai    AIMessage    （脚本预设回复）已查询北京的天气，结果见工具返回。


**怎样读这段输出**：offline 模式下应看到编号 `[0]` 到 `[3]` 的四条消息。`[0]` 是用户问题；`[1]` 的 `ai` 文字为空，真正的内容在它下面“请求工具”那一行；`[2]` 的 `tool` 是 Python 函数实际返回的 `It's always sunny in 北京!`，它回应的调用 ID 与请求一致；`[3]` 的 `ai` 才是上一格打印出来的最终回复。

状态里的 `files` 是 Deep Agent 自带的虚拟文件系统，本次没有写文件，所以是空的。第 3 章会专门讲它。

下一格把这些观察写成自动检查：先找出 `get_weather` 请求，确认查询的正是题目里的城市，再找 ID 对应、状态成功、内容与参数一致的工具结果，最后确认对话以一条不再请求工具的模型回复结束。期望的城市作为参数传给检查函数，默认接受 `北京` 和 `Beijing` 两种写法（不区分大小写）；问北京却查了上海，工具即使正常返回也会被判为不符合要求。检查只依赖工具名、参数和返回值，不依赖最终回答的措辞。


```python
from langchain_core.messages import AIMessage, ToolMessage


def check_weather(messages, city=("北京", "Beijing")):
    calls = {call["id"]: call for message in messages if isinstance(message, AIMessage)
             for call in message.tool_calls if call["name"] == "get_weather"}
    assert calls, "模型没有请求 get_weather。"
    accepted = {name.casefold() for name in city}
    asked = [str(call["args"].get("city", "")) for call in calls.values()]
    calls = {call_id: call for call_id, call in calls.items()
             if str(call["args"].get("city", "")).strip().casefold() in accepted}
    assert calls, f"get_weather 查询的是 {asked}，不是题目要求的城市（{' / '.join(city)}）。"
    answered = [message for message in messages if isinstance(message, ToolMessage)
                and message.tool_call_id in calls and message.name == "get_weather"
                and message.status == "success"
                and message.content == f"It's always sunny in {calls[message.tool_call_id]['args'].get('city')}!"]
    assert answered, "get_weather 没有成功返回与请求参数对应的结果。"
    assert isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls and messages[-1].content, \
        "缺少最终回复。"
    print("已验证 get_weather 的请求、调用关联、成功状态与返回值：", answered[-1].content)


check_weather(result["messages"])
```

    已验证 get_weather 的请求、调用关联、成功状态与返回值： It's always sunny in 北京!


## 2. 编写自定义工具：三要素变成了什么？

正文说 Agent 通过“参数类型标注、docstring、默认值”理解工具。模型实际看到的是一份 **工具 Schema**：框架从函数签名和 docstring 生成的 JSON 描述。我们照正文定义两个工具，再把 Schema 打印出来对照。

- `calculate(expression: str)`：参数是整条算式字符串，返回计算结果；
- `convert_currency(amount, from_currency, to_currency="CNY")`：用固定汇率换算货币，`to_currency` 有默认值。

正文的 `calculate` 直接用 `eval` 做演示，并提醒实际项目不要这样做。工具参数来自模型，本质上是不可信输入，所以这里在 `eval` 前加了一道检查：只放行数字、小数点、括号和 `+ - * /`，其他内容一律拒绝。`re.fullmatch` 要求整条字符串都符合这个模式。


```python
import re


def calculate(expression: str) -> float:
    """Evaluate a math expression and return the result.

    Args:
        expression: A math expression, e.g. "1 + 2 * 3".
    """
    # 正文用 eval 演示；这里只放行数字和四则运算符号，不把任意代码交给 eval
    if not re.fullmatch(r"[\d\s.+\-*/()]+", expression) or "**" in expression:
        raise ValueError(f"只支持数字、括号和 + - * /：{expression!r}")
    return eval(expression)


def convert_currency(amount: float, from_currency: str, to_currency: str = "CNY") -> dict:
    """Convert an amount from one currency to another.

    Args:
        amount: The amount to convert.
        from_currency: The source currency code, e.g. "USD".
        to_currency: The target currency code, defaults to "CNY".
    """
    # 这里用固定汇率做演示；真实场景可接入汇率 API
    rates = {"USD": 7.2, "CNY": 1.0, "EUR": 7.8}
    cny = amount * rates[from_currency]
    return {"amount": round(cny / rates[to_currency], 2), "currency": to_currency}


print("直接调用函数：", calculate("1 + 2 * 3"), convert_currency(100, "USD"))
```

    直接调用函数： 7 {'amount': 720.0, 'currency': 'CNY'}


### 2.1 打印工具 Schema

`convert_to_openai_tool(函数)` 生成与发给模型相同格式的工具描述。下一格逐个打印工具名、说明、必填参数，以及每个参数的类型、默认值和说明，并用 `assert` 固定三条对应关系。


```python
from langchain_core.utils.function_calling import convert_to_openai_tool

schemas = {}
for fn in (calculate, convert_currency):
    schema = convert_to_openai_tool(fn)["function"]
    schemas[schema["name"]] = schema
    params = schema["parameters"]
    print(f"工具 {schema['name']}：{schema['description']}")
    print("  必填参数：", params.get("required", []))
    for name, spec in params["properties"].items():
        default = f"，默认值 {spec['default']!r}" if "default" in spec else ""
        print(f"  - {name}: {spec['type']}{default}；{spec.get('description', '')}")

currency = schemas["convert_currency"]["parameters"]
assert currency["properties"]["amount"]["type"] == "number"      # 类型标注 float → number
assert currency["required"] == ["amount", "from_currency"]      # 有默认值的参数不必填
assert currency["properties"]["to_currency"]["default"] == "CNY"
print("\n已验证：类型标注、docstring 与默认值都进入了工具 Schema。")
```

    工具 calculate：Evaluate a math expression and return the result.
      必填参数： ['expression']
      - expression: string；A math expression, e.g. "1 + 2 * 3".
    工具 convert_currency：Convert an amount from one currency to another.
      必填参数： ['amount', 'from_currency']
      - amount: number；The amount to convert.
      - from_currency: string；The source currency code, e.g. "USD".
      - to_currency: string，默认值 'CNY'；The target currency code, defaults to "CNY".
    
    已验证：类型标注、docstring 与默认值都进入了工具 Schema。


对照输出看三要素：

| 要素 | 在 Schema 中的位置 | 本例 |
|---|---|---|
| 参数类型标注 | 每个参数的 `type` | `amount: float` 变成 `number`，`expression: str` 变成 `string` |
| Docstring | 工具的 `description`；`Args:` 下的逐行说明变成参数的 `description` | “Convert an amount from one currency to another.” |
| 默认值 | 参数从 `required` 列表中消失，并带上 `default` | `to_currency` 不必填，默认 `CNY` |

这就是正文所说“类型标注决定输入形态，docstring 决定调用时机，默认值减少必填项”的具体形态。类型标注不只是说明文字：第 4 节会看到，框架会按它检查模型传来的参数。

## 3. 小试牛刀：计算器 Agent

正文的问题是“把 100 美元换算成人民币，再乘以 1.08 的通胀系数”。完成它需要两步，而且第二步要用到第一步的结果：

```text
convert_currency(amount=100, from_currency="USD")  →  {"amount": 720.0, "currency": "CNY"}
calculate(expression="720.0 * 1.08")               →  777.6
```

下一格的脚本按这个顺序发出两次调用。注意：脚本里的 `720.0` 是提前写死的，脚本模型并不会读取换算结果。因此后面的检查会用**实际的** `convert_currency` 返回值重新算一遍，核对 `calculate` 的结果是否与它一致。live 模式下，这一步要由真实模型自己读取工具结果完成。

每个独立实验都新建一个脚本模型，避免上一段实验把响应列表消耗到一半。


```python
calc_model = create_model(ScriptedChatModel(responses=[
    AIMessage(content="", tool_calls=[{
        "name": "convert_currency", "args": {"amount": 100, "from_currency": "USD"},
        "id": "ch02-convert",
    }]),
    AIMessage(content="", tool_calls=[{
        "name": "calculate", "args": {"expression": "720.0 * 1.08"}, "id": "ch02-calculate",
    }]),
    AIMessage(content="（脚本预设回复）换算与计算已完成，结果见工具返回。"),
]))

calc_agent = create_deep_agent(
    model=calc_model,
    tools=[calculate, convert_currency],
    system_prompt="你是一个计算助手，能帮用户做数学运算和货币换算。",
)

calc_result = calc_agent.invoke(
    {"messages": [{"role": "user", "content": "帮我把 100 美元换算成人民币，再用它乘以 1.08 的通胀系数。"}]}
)

for message in calc_result["messages"]:
    if isinstance(message, AIMessage):
        for call in message.tool_calls:
            print("请求", call["name"], call["args"], "ID:", call["id"])
        if not message.tool_calls:
            print("最终回复：", message.content[:80])
    if isinstance(message, ToolMessage):
        print("  返回", message.name, message.status, message.content, "ID:", message.tool_call_id)
```

    请求

     convert_currency {'amount': 100, 'from_currency': 'USD'} ID: ch02-convert
      返回 convert_currency success {"amount": 720.0, "currency": "CNY"} ID: ch02-convert
    请求 calculate {'expression': '720.0 * 1.08'} ID: ch02-calculate
      返回 calculate success 777.6 ID: ch02-calculate
    最终回复： （脚本预设回复）换算与计算已完成，结果见工具返回。


**怎样读这段输出**：应看到两对“请求 → 返回”。`convert_currency` 的请求里没有 `to_currency`，函数用了默认值 `CNY`；它返回的字典被框架转成 JSON 文本 `{"amount": 720.0, "currency": "CNY"}` 放进 ToolMessage。`calculate` 返回 `777.6`。

下一格的检查分三步：

1. 找到参数为 100、`USD`、目标币种为 `CNY`（显式传入或使用默认值）且成功返回的换算，用 `json.loads` 把 JSON 文本还原成字典；
2. 确认两步真的接上了：`calculate` 是在换算结果返回**之后**才请求的，而且算式里用到了这个**实际**换算结果；
3. 确认这次 `calculate` 成功算出换算结果 × 1.08（`math.isclose` 容忍浮点误差），最后以最终回复结束。

检查不限定算式的写法：`720 * 1.08`、`1.08 * 720.0` 都可以。但如果模型在同一次请求里同时调用两个工具，或者先直接算出 `777.6` 再去换汇，`calculate` 就没有用到换算结果，检查会指出这一步没有接上。


```python
import json
import math
import re

from langchain_core.messages import AIMessage, ToolMessage


def check_calculator(messages, amount=100, source="USD", factor=1.08):
    calls, requested_at = {}, {}
    for index, message in enumerate(messages):
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                calls[call["id"]], requested_at[call["id"]] = call, index
    succeeded = [(index, message) for index, message in enumerate(messages)
                 if isinstance(message, ToolMessage) and message.status == "success"
                 and message.tool_call_id in calls and calls[message.tool_call_id]["name"] == message.name]
    converted, converted_at = None, None
    for index, message in succeeded:
        args = calls[message.tool_call_id]["args"]
        if (message.name == "convert_currency" and args.get("amount") == amount
                and args.get("from_currency") == source and args.get("to_currency", "CNY") == "CNY"):
            converted, converted_at = json.loads(message.content), index
    assert converted and converted.get("currency") == "CNY", "没有成功的 100 USD → CNY 换算。"
    expected = converted["amount"] * factor

    later = [message for _, message in succeeded if message.name == "calculate"
             and requested_at[message.tool_call_id] > converted_at]
    assert later, "calculate 应在拿到换算结果之后再请求；同一次请求里同时调用两个工具时，算式还用不上换算结果。"
    chained = [message for message in later if any(
        math.isclose(float(number), converted["amount"])
        for number in re.findall(r"\d+(?:\.\d+)?", str(calls[message.tool_call_id]["args"].get("expression", ""))))]
    assert chained, f"calculate 的算式没有用到换算结果 {converted['amount']}。"
    assert any(math.isclose(float(message.content), expected) for message in chained), \
        f"calculate 没有算出 {converted['amount']} × {factor} = {expected:g}。"
    assert isinstance(messages[-1], AIMessage) and not messages[-1].tool_calls, "缺少最终回复。"
    print(f"已验证：{amount} {source} → {converted['amount']} CNY，× {factor} = {expected:g}")


check_calculator(calc_result["messages"])
```

    已验证：100 USD → 720.0 CNY，× 1.08 = 777.6


## 4. 工具出错时会发生什么？

工具参数由模型生成，难免出错。下面构造两种错误调用，观察框架怎样处理。这一节**固定使用脚本模型**，即使选择了 live 模式也一样：我们需要故意发出错误参数，而真实模型不会按指令犯错。

| 错误 | 构造方式 | 预期 |
|---|---|---|
| 参数不符合类型标注 | `amount` 传入文字 `"a lot"` | 框架按 Schema 校验失败，返回 `status="error"` 的 ToolMessage，函数不会运行 |
| 函数内部抛出异常 | `from_currency` 传入汇率表里没有的 `"JPY"` | 参数类型正确，函数运行到 `rates["JPY"]` 抛出 `KeyError`，整次 `invoke()` 中断 |

`run_scripted(tool_call)` 是本节的小辅助函数：用一条工具请求加一条结束回复创建脚本模型，再运行一次计算器 Agent。


```python
def run_scripted(tool_call):
    model = ScriptedChatModel(responses=[
        AIMessage(content="", tool_calls=[tool_call]),
        AIMessage(content="（脚本预设回复）结束。"),
    ])
    agent = create_deep_agent(model=model, tools=[calculate, convert_currency])
    return agent.invoke({"messages": [{"role": "user", "content": "换算"}]})


bad_type = run_scripted({"name": "convert_currency", "id": "ch02-bad-type",
                         "args": {"amount": "a lot", "from_currency": "USD"}})
error_message = next(m for m in bad_type["messages"] if isinstance(m, ToolMessage))
print("状态：", error_message.status)
print("内容：", error_message.content)
assert error_message.status == "error" and "amount" in error_message.content

try:
    run_scripted({"name": "convert_currency", "id": "ch02-unknown-currency",
                  "args": {"amount": 1, "from_currency": "JPY"}})
except KeyError as error:
    print("\n函数内部异常中断了 invoke()：KeyError", error)
else:
    raise AssertionError("预期 rates['JPY'] 抛出 KeyError。")
```

    状态：

     error
    内容： Error invoking tool 'convert_currency' with kwargs {'amount': 'a lot', 'from_currency': 'USD'} with error:
     amount: Input should be a valid number, unable to parse string as a number
     Please fix the error and try again.


    
    函数内部异常中断了 invoke()：KeyError 'JPY'


两种错误的区别很重要：

- **参数校验错误**变成一条普通的工具结果，内容说明哪个参数不合法，并提示“Please fix the error and try again”。这条消息会交回模型，真实模型可以据此改正参数再试。这也说明类型标注会被真正执行，不只是给人看的注释。
- **函数内部异常**没有被转换成工具结果，而是直接从 `invoke()` 抛出，整个 Agent 运行停止。正文的 `calculate` 也一样：模型写出一个非法算式，`eval` 或上面的检查就会抛错。

实际项目里，对可预见的错误（未知币种、非法算式）要在工具内部处理，返回清楚的错误说明，而不是让异常中断整次运行。

## 5. 改一个变量再观察

**改哪里**：在第 2 节定义工具的代码格中，把汇率表里的 `"USD": 7.2` 改为 `"USD": 7.0`，其他代码都不动。

**先预测**：

1. `convert_currency` 会返回多少人民币？
2. 脚本里第二次调用写死的是 `720.0 * 1.08`，`calculate` 会返回多少？
3. `check_calculator` 会通过吗？如果失败，停在哪一步？

**再运行**：选择“重启内核并运行全部”，核对第 3 节的输出：换算返回 `{"amount": 700.0, "currency": "CNY"}`，`calculate` 仍然返回 `777.6`；`check_calculator` 停在“calculate 的算式没有用到换算结果 700.0。”。第 1、2 节和第 4 节不受影响。

**这说明**：脚本模型只是回放预先写好的消息，不会读取工具结果，所以第二步用的仍是旧数字。检查先看算式里有没有实际换算结果 `700.0`：`720.0 * 1.08` 里没有，两步没有衔接上，检查就停在这里，还轮不到核对 `700.0 × 1.08 = 756`。每一步都“成功”，也不等于任务完成。live 模式下，这一步由真实模型读取 `700.0` 再写算式，检查的正是它有没有做到。

**恢复**：把汇率改回 `7.2`，重启内核并运行全部，确认所有检查重新通过。

## 6. 常见问题与清理

| 现象 | 先检查什么 |
|---|---|
| `ModuleNotFoundError` | 是否完成安装，是否选择 `notebooks/.venv` 的项目内核；见 [统一安装说明](../README.md) |
| `NameError`，例如 `calculate` 未定义 | 是否跳过了前面的代码格；重启内核并从头运行 |
| live 模式缺 Key、401 或网络超时 | 检查仓库根目录 `.env`、模型端点与网络；offline 无需这些凭证 |
| live 模式下 `check_weather` 或 `check_calculator` 失败 | 查看消息列表：模型可能没有调用工具，直接心算或编造了答案。小模型（如 7B）不一定稳定调用工具，可用 `MODEL_NAME` 换更强的模型再试；某个模型通过不代表所有模型都通过 |
| `KeyError` 或 `ValueError` 从 `invoke()` 抛出 | 工具函数内部出错会中断运行，见第 4 节；检查模型传入的币种或算式 |

本实验的状态都在内存中，没有启动外部进程，重启内核即可清理。不要提交 `.env`、Key 或未经检查的输出。

## 小结与下一步

- 一个带类型标注和 docstring 的 Python 函数就是一个工具，框架据此生成 Schema；默认值决定哪些参数必填。
- 验证工具调用要把三样东西对上：模型的请求（`tool_calls`）、调用 ID（`tool_call_id`）、工具的实际返回（`ToolMessage`）。最终回复的措辞不是证据。
- 参数不合法时框架返回错误消息，函数内部异常则会中断运行。

下一份 [第 2 章 Notebook（二）：研究助手](02-research-assistant.ipynb) 接入搜索工具，并观察 Deep Agent 的任务规划和虚拟文件。
