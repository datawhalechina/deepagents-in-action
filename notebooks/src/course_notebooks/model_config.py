"""Explicit offline/live model selection shared by notebooks and local services."""
import os
from pathlib import Path

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


def create_model(
    scripted: BaseChatModel | None, *, root: Path | None = None, mode: str | None = None
) -> BaseChatModel:
    """Return the supplied scripted model offline; require valid config for live.

    Mode is chosen before loading .env so a stored key cannot opt readers into billing.
    Generic provider key, endpoint and model must be supplied together.
    """
    if selected_mode(mode) == "offline":
        if scripted is None:
            raise ValueError("offline 模式需要显式提供脚本模型。")
        return scripted
    load_dotenv((root or repository_root()) / ".env", override=False)
    if os.getenv("MODEL_API_KEY") or os.getenv("MODEL_BASE_URL"):
        missing = [key for key in ("MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_NAME") if not os.getenv(key)]
        if missing:
            raise ValueError("通用模型配置需同时设置 MODEL_API_KEY、MODEL_BASE_URL、MODEL_NAME；缺少：" + ", ".join(missing))
        key, endpoint, name = (os.environ[k] for k in ("MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_NAME"))
    else:
        key = os.getenv("SILICONFLOW_API_KEY")
        if not key:
            raise ValueError("live 模式缺少 SILICONFLOW_API_KEY，或完整的 MODEL_* 配置。")
        endpoint = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
    return StreamingChatOpenAI(model=name, api_key=key, base_url=endpoint, temperature=0, timeout=60, max_retries=1)
