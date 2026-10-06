"""Small, read-only display helpers."""
import importlib.metadata as metadata
import platform
import textwrap

from .model_config import selected_mode


def show_runtime():
    print("运行模式：", selected_mode(), "（脚本模型）" if selected_mode() == "offline" else "（真实模型 API）")
    print("Python：", platform.python_version(), "平台：", platform.system(), platform.machine())
    for package in ("deepagents", "langchain", "langchain-core", "langgraph", "langchain-openai"):
        print(f"{package}=={metadata.version(package)}")


def show_text(label, value, width=76):
    print(f"\n{label}")
    for line in str(value).splitlines():
        print(textwrap.fill(line, width=width, subsequent_indent="  ", break_on_hyphens=False))
