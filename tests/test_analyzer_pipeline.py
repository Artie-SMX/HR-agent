from pathlib import Path

from config import Settings
from models import MatchStatus
from services.analyzer import Analyzer
from tools.document_parser import PageText


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        workspace_root=tmp_path / "workspace",
        output_root=tmp_path / "workspace" / "output",
        log_root=tmp_path / "workspace" / "logs",
        model="qwen-plus",
        model_server="dashscope",
        api_key="test-only",
        api_timeout=30,
        evaluation_date="2026-08-25",
    )


def test_pipeline_normalizes_model_variants_and_applies_date_rule(tmp_path):
    analyzer = Analyzer(_settings(tmp_path))
    responses = iter([
        {
            "education": [{"school": "金陵理工学院", "school_level": "本科", "major": "数据科学", "status": "在读", "graduation_year": 2025}],
            "skills": [{"name": "Python"}, {"name": "SQL"}],
            "projects": [{"name": "电商项目", "evidence": "电商项目"}],
            "work_experiences": [{"company": "某公司", "skills": "SQL"}],
        },
        {"must_requirements": [{"id": "req-1", "dimension": "education", "text": "本科在读", "priority": 2, "evidence": "本科在读"}], "preferred_requirements": [{"id": "req-2", "dimension": "project_experience", "text": "有数据分析项目经历", "priority": 1, "evidence": "数据分析项目"}]},
        [
            {"requirement_id": "req-1:degree", "dimension": "education", "requirement": "本科", "priority": 2, "status": "匹配", "resume_evidence": "本科", "job_evidence": "本科在读"},
            {"requirement_id": "req-1:status", "dimension": "year", "requirement": "在读", "priority": 2, "status": "匹配", "resume_evidence": "2021.09-2025.06", "job_evidence": "本科在读"},
            {"requirement_id": "req-2", "dimension": "project_experience", "requirement": "有数据分析项目经历", "priority": 1, "status": "匹配", "resume_evidence": "电商项目", "job_evidence": "数据分析项目"},
        ],
    ])
    analyzer._call_json = lambda _prompt: next(responses)
    resume_pages = [PageText(1, "教育背景：金陵理工学院 本科 数据科学 2021.09-2025.06", "text", 1.0), PageText(2, "电商项目 Python SQL", "text", 1.0)]
    job_pages = [PageText(1, "必须：本科在读；优先：有数据分析项目经历", "text", 1.0)]
    resume = analyzer.parse_resume("resume", resume_pages, "\n".join(page.text for page in resume_pages))
    job = analyzer.parse_job("job-text", job_pages, job_pages[0].text)
    matches = analyzer.match(resume, job, "resume", job_pages[0].text, "resume", "job-text", {1: resume_pages[0].text, 2: resume_pages[1].text}, {1: job_pages[0].text})
    matches = [analyzer._verify_match(item, resume_pages, job_pages, "resume", "job-text") for item in matches]
    matches = analyzer._apply_deterministic_rules(matches, resume)
    assert resume.education == "本科"
    assert resume.status.startswith("已毕业")
    assert len(resume.work_experiences) == 1
    assert {item.dimension for item in job.requirements} == {"education", "year", "project"}
    assert [item.status for item in matches] == [MatchStatus.MATCH, MatchStatus.MISMATCH, MatchStatus.MATCH]
    assert matches[-1].dimension == "project"
