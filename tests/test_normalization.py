from services.normalization import normalize_job_payload, normalize_match_payload, normalize_resume_payload


def test_resume_variants_are_normalized_without_validation_error():
    warnings = []
    payload = normalize_resume_payload({
        "education": [{"school": "东华大学", "degree": "本科", "major": "信息管理"}],
        "awards": [{"name": "奖学金"}],
        "projects": [{"name": "分析项目", "actions": None, "outcomes": "完成报告", "evidence": {"page": 1, "text": "项目原文"}}],
        "evidence": {"page": 1, "content": "本科"},
    }, "resume", warnings)
    assert payload["education"] == "本科"
    assert payload["awards"] == ["奖学金"]
    assert payload["projects"][0]["actions"] == []
    assert payload["projects"][0]["outcomes"] == ["完成报告"]
    assert payload["projects"][0]["evidence"][0]["quote"] == "项目原文"
    assert not warnings


def test_missing_quote_is_discarded_and_reported():
    warnings = []
    payload = normalize_resume_payload({"evidence": {"page": 1, "text": None}}, "resume", warnings)
    assert payload["evidence"] == []
    assert warnings


def test_job_and_match_aliases_are_normalized():
    warnings = []
    job = normalize_job_payload({"requirements": {"must": [{"description": "熟悉 Python"}]}}, "job-text", warnings)
    assert job["requirements"][0]["priority"] == 2
    matches = normalize_match_payload({"matches": [{"id": "s1", "status": "匹配", "text": "Python", "resumeEvidence": {"page": 1, "quote": "Python"}}]}, "resume", "job-text", warnings)
    assert matches[0]["status"] == "match"
    assert matches[0]["resume_evidence"][0]["document_id"] == "resume"


def test_project_experience_text_is_not_left_in_skill_dimension():
    warnings = []
    job = normalize_job_payload(
        {"requirements": [{"dimension": "skill", "text": "有数据分析项目经历", "priority": 1}]},
        "job-text",
        warnings,
    )
    assert job["requirements"][0]["dimension"] == "project"


def test_string_evidence_is_located_on_the_real_page():
    warnings = []
    payload = normalize_match_payload(
        [{"dimension": "technical_skills", "status": "match", "requirement": "Python", "resume_evidence": "Python（Pandas）"}],
        "resume", "job-text", warnings, {1: "核心技能：Python（Pandas）"}, {1: "技能要求：Python"}
    )
    assert payload[0]["dimension"] == "skill"
    assert payload[0]["resume_evidence"][0]["page"] == 1
    assert not warnings


def test_graduation_date_overrides_stale_student_status():
    warnings = []
    payload = normalize_resume_payload(
        {"education": [{"school": "金陵理工学院", "school_level": "本科", "status": "在读", "graduation_year": 2025}]},
        "resume", warnings, evaluation_date="2026-08-25"
    )
    assert payload["education"] == "本科"
    assert payload["school_level"] is None
    assert payload["status"].startswith("已毕业")


def test_work_experience_is_preserved():
    warnings = []
    payload = normalize_resume_payload(
        {"work_experiences": [{"company": "某公司", "role": "数据分析实习生", "skills": "SQL", "outcomes": "转化率提升6.2%"}]},
        "resume", warnings
    )
    assert payload["work_experiences"][0]["company"] == "某公司"
    assert payload["work_experiences"][0]["skills"] == ["SQL"]
