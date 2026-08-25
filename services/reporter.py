"""Human-readable Markdown report plus machine-readable JSON."""

from __future__ import annotations

import json
from pathlib import Path

from models import AnalysisReport, EvidenceVerification, MatchStatus


def _evidence_lines(evidence, empty_label: str = "简历未提供") -> str:
    if not evidence:
        return empty_label
    parts = []
    for item in evidence:
        flag = "已校验" if item.verification_status == EvidenceVerification.VERIFIED else "待复核"
        parts.append(f"[{item.document_id} 第 {item.page} 页；{flag}] {item.quote}")
    return "；".join(parts)


def render_markdown(report: AnalysisReport) -> str:
    labels = {
        MatchStatus.MATCH: "匹配", MatchStatus.PARTIAL: "部分匹配", MatchStatus.MISMATCH: "不匹配",
        MatchStatus.UNKNOWN: "未知", MatchStatus.NA: "不适用",
    }
    lines = [
        "# 简历与岗位匹配分析报告", "",
        f"- 证据匹配分：**{report.scoring.total_score:.2f}/100**",
        f"- 信息完整度：**{report.scoring.completeness * 100:.2f}%**",
        f"- 必须条件门槛：**{report.scoring.hard_gate}**（不替代人工录用判断）", "",
        "## 1. 最大风险项", "",
    ]
    if report.risks:
        for item in report.risks[:5]:
            lines.append(f"- **{labels[item.status]}**｜{item.requirement}：{item.reason or '待进一步核验'}")
    else:
        lines.append("- 未发现可排序的匹配项。")
    lines.extend(["", "## 2. 逐项匹配（风险优先）", ""])
    for item in report.matches:
        lines.extend([
            f"### {labels[item.status]}｜{item.dimension}｜{item.requirement_id}",
            f"- 岗位要求：{item.requirement}",
            f"- 简历证据：{_evidence_lines(item.resume_evidence)}",
            f"- 岗位证据：{_evidence_lines(item.job_evidence, '岗位未提供')}",
            f"- 最佳项目证据：{item.project_name or '不适用'}",
            f"- 判断：{item.reason or '未提供理由'}",
            f"- 人工复核：{'是' if item.review_required else '否'}", "",
        ])
    lines.extend(["## 3. 权重及计算过程", "", f"`{report.scoring.formula}`", ""])
    lines.append("| 维度 | 原始权重 | 归一化权重 | 维度分 | 有效项 | 可确认项 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for item in report.scoring.dimensions:
        lines.append(f"| {item.dimension} | {item.raw_weight:.1f}% | {item.normalized_weight:.4f} | {item.score:.4f} | {item.applicable_items} | {item.known_items} |")
    lines.extend(["", "## 4. 待确认信息与面试追问", ""])
    if report.interview_questions:
        lines.extend(f"- {question}" for question in report.interview_questions)
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 5. 处理警告", ""])
    if report.warnings:
        lines.extend(f"- {warning}" for warning in report.warnings)
    else:
        lines.append("- 无")
    lines.extend(["", "> 本报告仅展示可追溯证据和待复核风险，不自动生成录用或淘汰结论。", ""])
    return "\n".join(lines)


def write_report(report: AnalysisReport, output_path: Path) -> tuple[Path, Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(report), encoding="utf-8")
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path, json_path
