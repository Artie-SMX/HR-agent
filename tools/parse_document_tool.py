"""Constrained Qwen-Agent tool: only registered PDFs under workspace/input."""

from __future__ import annotations

import json
from pathlib import Path

from qwen_agent.tools import BaseTool

from .document_parser import parse_pdf


class ParseDocumentTool(BaseTool):
    name = "parse_document"
    description = (
        "读取已注册的简历或岗位 PDF，返回保留页码的 Markdown 和页面质量信息。"
        "只能读取 workspace/input 中给出的 document_id。"
    )
    parameters = {
        "type": "object",
        "properties": {"document_id": {"type": "string", "description": "已注册文档 ID"}},
        "required": ["document_id"],
    }

    def __init__(self, input_root: Path, **kwargs):
        super().__init__(kwargs)
        self.input_root = input_root.resolve()

    def call(self, params, **kwargs):
        args = self._verify_json_format_args(params)
        document_id = str(args["document_id"])
        candidates = list(self.input_root.glob(f"{document_id}.pdf"))
        if len(candidates) != 1 or self.input_root not in candidates[0].resolve().parents:
            raise ValueError("document_id 未注册或不在 workspace/input 内")
        parsed = parse_pdf(candidates[0], document_id)
        return json.dumps(
            {
                "document_id": parsed.document_id,
                "markdown": parsed.markdown,
                "quality": parsed.quality,
                "warnings": parsed.warnings,
                "pages": [item.__dict__ for item in parsed.pages],
            },
            ensure_ascii=False,
        )
