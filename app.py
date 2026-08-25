"""CLI entry point for the resume/job matching Agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from config import load_settings
from services.analyzer import Analyzer
from services.reporter import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="简历与岗位匹配分析 Agent")
    parser.add_argument("--resume", required=True, type=Path, help="简历 PDF")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--job-file", type=Path, help="岗位 PDF")
    group.add_argument("--job-text", help="岗位文字")
    parser.add_argument("--output", type=Path, help="Markdown 输出路径，默认 workspace/output/report.md")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = load_settings(require_api_key=True)
    analyzer = Analyzer(settings)
    report = analyzer.analyze(args.resume, args.job_file, args.job_text)
    output = args.output or (settings.output_root / "report.md")
    markdown_path, json_path = write_report(report, output)
    print(f"分析完成：{markdown_path}")
    print(f"结构化结果：{json_path}")
    print(f"证据匹配分：{report.scoring.total_score:.2f}；信息完整度：{report.scoring.completeness * 100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
