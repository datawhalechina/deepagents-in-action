"""Explicit offline/live model selection shared by notebooks and local services."""
import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

from .streaming_model import StreamingChatOpenAI


def repository_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "scripts/chapters.json").is_file():
            return candidate
    raise ValueError("请从课程仓库目录运行 Notebook。")


def selected_mode(mode: str | None = None) -> str:
    value = mode if mode is not None else os.getenv("COURSE_MODE", "offline")
    if value not in {"offline", "live"}:
        raise ValueError("COURSE_MODE 必须明确为 offline 或 live。")
    return value


def _live_configuration(root: Path | None, environ: Mapping[str, str] | None = None):
    if environ is None:
        load_dotenv((root or repository_root()) / ".env", override=False)
        environ = os.environ
    if environ.get("MODEL_API_KEY") or environ.get("MODEL_BASE_URL"):
        missing = [key for key in ("MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_NAME") if not environ.get(key)]
        if missing:
            raise ValueError("通用模型配置需同时设置 MODEL_API_KEY、MODEL_BASE_URL、MODEL_NAME；缺少：" + ", ".join(missing))
        key, endpoint, name = (environ[k] for k in ("MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_NAME"))
        provider = "openai-compatible"
    else:
        key = environ.get("SILICONFLOW_API_KEY")
        if not key:
            raise ValueError("live 模式缺少 SILICONFLOW_API_KEY，或完整的 MODEL_* 配置。")
        name = environ.get("MODEL_NAME")
        if not name:
            raise ValueError("live 模式缺少 MODEL_NAME；请按本章说明选择模型，并在 .env 中明确填写。")
        endpoint = environ.get("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1"
        provider = "siliconflow"
    return provider, dict(model=name, api_key=key, base_url=endpoint, temperature=0, timeout=60, max_retries=1)


def model_configuration(
    *, root: Path | None = None, mode: str | None = None, environ: Mapping[str, str] | None = None
) -> dict | None:
    """Describe the requested live model; never return keys or a full endpoint URL.

    The runner passes its prepared kernel environment so the record uses the same
    environment-over-dotenv precedence as the kernel. Offline does not read .env.
    """
    if selected_mode(mode) == "offline":
        return None
    provider, config = _live_configuration(root, environ)
    return {
        "provider": provider, "model_name": config["model"],
        "api_host": urlsplit(config["base_url"]).hostname,
        "temperature": config["temperature"], "timeout_seconds": config["timeout"],
        "max_retries": config["max_retries"],
    }


def create_model(
    scripted: BaseChatModel | None, *, root: Path | None = None, mode: str | None = None
) -> BaseChatModel:
    """Return the supplied scripted model offline; require explicit config for live.

    Mode is chosen before loading .env so a stored key cannot opt readers into billing.
    Generic provider key, endpoint and model must be supplied together.
    """
    if selected_mode(mode) == "offline":
        if scripted is None:
            raise ValueError("offline 模式需要显式提供脚本模型。")
        return scripted
    _, config = _live_configuration(root)
    return StreamingChatOpenAI(**config)
