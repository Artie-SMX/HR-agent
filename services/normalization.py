"""Normalize permissive LLM JSON before applying strict Pydantic contracts.

This layer repairs representation differences only (list vs. scalar, aliases,
and common labels). It never invents missing evidence; malformed evidence is
discarded and reported so the later matcher can produce ``unknown``.
"""

from __future__ import annotations

from typing import Any

from services.evidence import best_window_similarity, normalize_for_match


def _items(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any, keys: tuple[str, ...] = ("name", "title", "text", "value")) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in keys:
            result = _text(value.get(key))
            if result:
                return result
        return None
    return str(value).strip() or None


def _strings(value: Any, keys: tuple[str, ...] = ("name", "title", "text", "value", "skill")) -> list[str]:
    result: list[str] = []
    for item in _items(value):
        text = _text(item, keys)
        if text:
            result.append(text)
    return result


def _locate_quote(quote: str, pages: dict[int, str] | None) -> tuple[int, float] | None:
    if not pages or not quote:
        return None
    target = normalize_for_match(quote)
    for page, text in pages.items():
        if target and target in normalize_for_match(text):
            return page, 1.0
    best: tuple[int, float] | None = None
    for page, text in pages.items():
        similarity, _ = best_window_similarity(quote, text)
        if best is None or similarity > best[1]:
            best = (page, similarity)
    return best if best and best[1] >= 0.85 else None


def _evidence(value: Any, document_id: str, warnings: list[str], pages: dict[int, str] | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _items(value):
        item_dict = item if isinstance(item, dict) else {"quote": _text(item)}
        quote = _text(item_dict.get("quote") or item_dict.get("text") or item_dict.get("content") or item_dict.get("snippet"), ("quote", "text", "content", "snippet"))
        page_value = item_dict.get("page") or item_dict.get("page_number") or item_dict.get("pageNo")
        try:
            page = int(page_value)
        except (TypeError, ValueError):
            page = 0
        if quote and page < 1:
            located = _locate_quote(quote, pages)
            if located:
                page, similarity = located
                result.append({
                    "document_id": str(item_dict.get("document_id") or document_id),
                    "page": page,
                    "quote": quote,
                    "match_method": "page_lookup",
                    "similarity": similarity,
                })
                continue
        if not quote or page < 1:
            warnings.append("忽略了缺少 quote 或有效 page 的证据项；该项需人工复核")
            continue
        result.append({
            "document_id": str(item_dict.get("document_id") or document_id),
            "page": page,
            "quote": quote,
        })
    return result


def normalize_resume_payload(raw: Any, document_id: str, warnings: list[str], pages: dict[int, str] | None = None, evaluation_date: str | None = None) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    education = data.get("education")
    education_record = next((item for item in _items(education) if isinstance(item, dict)), {})
    if not education_record and isinstance(data.get("education_info"), dict):
        education_record = data["education_info"]
    education_text = _text(education_record.get("degree") or education_record.get("level") or education_record.get("education") or education_record.get("school_level"))
    if not education_text and not isinstance(education, (list, dict)):
        education_text = _text(education)
    graduation_text = _text(data.get("graduation_year") or data.get("graduation") or education_record.get("graduation_year"))
    status = _text(data.get("status") or data.get("student_status") or education_record.get("status"))
    try:
        evaluation_year = int((evaluation_date or "").split("-", 1)[0])
        graduation_year = int(graduation_text or "")
    except (TypeError, ValueError):
        evaluation_year = graduation_year = 0
    if graduation_year and evaluation_year and graduation_year < evaluation_year:
        status = "已毕业（根据毕业时间推定）"

    projects: list[dict[str, Any]] = []
    for index, raw_project in enumerate(_items(data.get("projects")), start=1):
        project = raw_project if isinstance(raw_project, dict) else {"name": _text(raw_project) or f"未命名项目{index}"}
        projects.append({
            "name": _text(project.get("name") or project.get("title")) or f"未命名项目{index}",
            "time": _text(project.get("time") or project.get("date")),
            "role": _text(project.get("role")),
            "scenario": _text(project.get("scenario") or project.get("background") or project.get("context")),
            "tasks": _strings(project.get("tasks") or project.get("responsibilities")),
            "actions": _strings(project.get("actions") or project.get("methods") or project.get("work")),
            "skills": _strings(project.get("skills") or project.get("technologies") or project.get("tools")),
            "outcomes": _strings(project.get("outcomes") or project.get("results") or project.get("achievements")),
            "evidence": _evidence(project.get("evidence") or project.get("sources"), document_id, warnings, pages),
        })

    work_experiences: list[dict[str, Any]] = []
    work_source = data.get("work_experiences") or data.get("work_experience") or data.get("internships") or data.get("internship_experience")
    for index, raw_work in enumerate(_items(work_source), start=1):
        work = raw_work if isinstance(raw_work, dict) else {"company": _text(raw_work) or f"未命名单位{index}"}
        work_experiences.append({
            "company": _text(work.get("company") or work.get("organization") or work.get("employer")) or f"未命名单位{index}",
            "role": _text(work.get("role") or work.get("position")),
            "time": _text(work.get("time") or work.get("date")),
            "tasks": _strings(work.get("tasks") or work.get("responsibilities")),
            "actions": _strings(work.get("actions") or work.get("methods") or work.get("work")),
            "skills": _strings(work.get("skills") or work.get("technologies") or work.get("tools")),
            "outcomes": _strings(work.get("outcomes") or work.get("results") or work.get("achievements")),
            "evidence": _evidence(work.get("evidence") or work.get("sources"), document_id, warnings, pages),
        })

    school_level = _text(data.get("school_level") or data.get("school_type") or education_record.get("school_level"))
    if school_level in {"大专", "本科", "硕士", "博士"}:
        school_level = None

    return {
        "education": education_text,
        "school": _text(data.get("school") or data.get("university") or education_record.get("school") or education_record.get("institution")),
        "school_level": school_level,
        "major": _text(data.get("major") or education_record.get("major")),
        "status": status,
        "graduation_year": graduation_text,
        "skills": _strings(data.get("skills")),
        "awards": _strings(data.get("awards") or data.get("honors"), ("name", "title", "text", "value", "award")),
        "projects": projects,
        "work_experiences": work_experiences,
        "evidence": _evidence(data.get("evidence") or data.get("sources"), document_id, warnings, pages),
    }


def _requirement_items(value: Any, priority_hint: int | None = None) -> list[tuple[Any, int | None]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [(item, priority_hint) for item in value]
    if isinstance(value, dict):
        aliases = {"must": 2, "required": 2, "mandatory": 2, "preferred": 1, "nice_to_have": 1}
        if any(key in value for key in ("text", "requirement", "description", "name", "title")):
            return [(value, priority_hint)]
        result: list[tuple[Any, int | None]] = []
        for key, nested in value.items():
            result.extend(_requirement_items(nested, aliases.get(str(key).lower(), priority_hint)))
        return result
    return [(value, priority_hint)]


def _priority(value: Any, fallback: int | None = None) -> int:
    if isinstance(value, str):
        value = value.lower()
        if value in {"must", "required", "mandatory", "必需", "必须"}:
            return 2
        if value in {"preferred", "optional", "优先"}:
            return 1
    try:
        return 2 if int(value) >= 2 else 1
    except (TypeError, ValueError):
        return fallback or 1


def _dimension(value: Any) -> str:
    raw = str(value or "skill").strip().lower()
    aliases = {
        "technical_skills": "skill", "technical_skill": "skill", "skills": "skill", "skill_requirements": "skill",
        "project_requirements": "project", "project_experience": "project", "projects": "project", "experience": "project",
        "degree": "education", "education_level": "education", "academic": "education",
        "graduation": "year", "graduation_year": "year", "student_status": "year", "status": "year",
        "school": "school_level", "university_level": "school_level",
    }
    return aliases.get(raw, raw if raw in {"project", "skill", "education", "major", "year", "school_level"} else "skill")


def _requirement_dimension(text: str, supplied: Any) -> str:
    """Repair a common model error: project-experience requirements labelled as skills."""
    dimension = _dimension(supplied)
    project_markers = (
        "项目经历", "项目经验", "项目实践", "项目案例", "项目成果",
        "数据分析项目", "参与项目", "负责项目", "项目经验",
    )
    if dimension == "skill" and any(marker in text for marker in project_markers):
        return "project"
    return dimension


def normalize_job_payload(raw: Any, document_id: str, warnings: list[str], pages: dict[int, str] | None = None) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    requirements: list[dict[str, Any]] = []
    sources: list[tuple[Any, int | None]] = []
    if data.get("requirements") is not None:
        sources.extend(_requirement_items(data.get("requirements")))
    for key, priority in (("must_have", 2), ("must_requirements", 2), ("required_requirements", 2), ("preferred", 1), ("preferred_requirements", 1), ("nice_to_have", 1)):
        if data.get(key) is not None:
            sources.extend(_requirement_items(data.get(key), priority))
    if not sources and data.get("requirements_by_priority") is not None:
        sources.extend(_requirement_items(data.get("requirements_by_priority")))
    for index, (raw_item, priority_hint) in enumerate(sources, start=1):
        item = raw_item if isinstance(raw_item, dict) else {"text": _text(raw_item)}
        text = _text(item.get("text") or item.get("requirement") or item.get("description") or item.get("name"))
        if not text:
            warnings.append("忽略了缺少 text 的岗位要求")
            continue
        dimension = _requirement_dimension(
            text,
            item.get("dimension") or item.get("type") or item.get("category"),
        )
        base_id = str(item.get("id") or f"{dimension}:{index}")
        # Keep degree and current-student requirements independently scorable.
        compound = "在读" in text and any(token in text for token in ("本科", "硕士", "博士", "大专"))
        texts = [(_text(text.replace("在读", "").strip(" /、,，")) or text, base_id + ":degree"), ("在读", base_id + ":status")] if compound else [(text, base_id)]
        for requirement_text, requirement_id in texts:
            requirements.append({
                "id": requirement_id,
                "dimension": "education" if requirement_id.endswith(":degree") else ("year" if requirement_id.endswith(":status") else dimension),
                "text": requirement_text,
                "priority": _priority(item.get("priority"), priority_hint),
                "evidence": _evidence(item.get("evidence") or item.get("sources"), document_id, warnings, pages),
            })
    return {"title": _text(data.get("title") or data.get("job_title")), "duties": _strings(data.get("duties") or data.get("responsibilities")), "requirements": requirements}


_STATUS = {"匹配": "match", "部分匹配": "partial", "不匹配": "mismatch", "未知": "unknown", "不适用": "N/A"}


def normalize_match_payload(raw: Any, resume_id: str, job_id: str, warnings: list[str], resume_pages: dict[int, str] | None = None, job_pages: dict[int, str] | None = None) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw = raw.get("matches") or raw.get("items") or raw.get("results") or []
    result: list[dict[str, Any]] = []
    for index, raw_item in enumerate(_items(raw), start=1):
        if not isinstance(raw_item, dict):
            continue
        dimension = _dimension(raw_item.get("dimension") or raw_item.get("category"))
        status = _STATUS.get(str(raw_item.get("status") or "unknown"), str(raw_item.get("status") or "unknown").lower())
        if status not in {"match", "partial", "mismatch", "unknown", "N/A"}:
            status = "unknown"
        result.append({
            "requirement_id": str(raw_item.get("requirement_id") or raw_item.get("id") or f"{dimension}:{index}"),
            "dimension": dimension,
            "requirement": _text(raw_item.get("requirement") or raw_item.get("requirement_text") or raw_item.get("text")) or "未提供岗位要求",
            "priority": _priority(raw_item.get("priority")),
            "status": status,
            "resume_evidence": _evidence(raw_item.get("resume_evidence") or raw_item.get("resumeEvidence") or raw_item.get("resume_sources"), resume_id, warnings, resume_pages),
            "job_evidence": _evidence(raw_item.get("job_evidence") or raw_item.get("jobEvidence") or raw_item.get("job_sources"), job_id, warnings, job_pages),
            "reason": _text(raw_item.get("reason") or raw_item.get("explanation")) or "",
            "project_name": _text(raw_item.get("project_name") or raw_item.get("project")),
            "review_required": bool(raw_item.get("review_required") or raw_item.get("needs_review")),
        })
    return result
