"""Small, read-only display helpers."""
import importlib.metadata as metadata
import platform
import textwrap

from .model_config import model_configuration, selected_mode


def show_runtime():
    mode = selected_mode()
    print("运行模式：", mode, "（脚本模型）" if mode == "offline" else "（真实模型 API）")
    config = model_configuration(mode=mode)
    if config is not None:
        print("模型：", config["model_name"], "提供商：", config["provider"], "API 主机：", config["api_host"])
    print("Python：", platform.python_version(), "平台：", platform.system(), platform.machine())
    for package in ("deepagents", "langchain", "langchain-core", "langgraph", "langchain-openai"):
        print(f"{package}=={metadata.version(package)}")


def show_text(label, value, width=76):
    print(f"\n{label}")
    for line in str(value).splitlines():
        print(textwrap.fill(line, width=width, subsequent_indent="  ", break_on_hyphens=False))
