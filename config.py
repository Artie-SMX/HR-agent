"""Runtime configuration with an intentionally small secret surface."""

from __future__ import annotations

import os
from datetime import date
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_root: Path
    workspace_root: Path
    output_root: Path
    log_root: Path
    model: str
    model_server: str
    api_key: str | None
    api_timeout: int
    evaluation_date: str


def load_settings(project_root: Path | None = None, *, require_api_key: bool = True) -> Settings:
    root = (project_root or Path(__file__).resolve().parent).resolve()
    load_dotenv(root / ".env", override=False)
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    if require_api_key and not key:
        raise RuntimeError(
            "未找到 DASHSCOPE_API_KEY。请复制 .env.example 为 .env，并在本机填写密钥；"
            "不要把密钥写入代码、命令行参数、日志或报告。"
        )
    workspace = root / "workspace"
    return Settings(
        project_root=root,
        workspace_root=workspace,
        output_root=workspace / "output",
        log_root=workspace / "logs",
        model=os.getenv("QWEN_MODEL", "qwen-plus"),
        model_server=os.getenv("QWEN_MODEL_SERVER", "dashscope"),
        api_key=key,
        api_timeout=int(os.getenv("QWEN_API_TIMEOUT", "120")),
        evaluation_date=os.getenv("EVALUATION_DATE") or date.today().isoformat(),
    )
