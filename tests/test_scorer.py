from models import MatchItem, MatchStatus
from services.scorer import calculate_score


def test_dimension_weights_are_renormalized_when_dimension_missing():
    items = [MatchItem(requirement_id="s1", dimension="skill", requirement="Python", priority=2, status=MatchStatus.MATCH)]
    result = calculate_score(items)
    assert result.dimensions[1].normalized_weight == 1.0
    assert result.total_score == 100.0


def test_must_requirement_has_double_weight_inside_dimension():
    items = [
        MatchItem(requirement_id="s1", dimension="skill", requirement="must", priority=2, status=MatchStatus.MATCH),
        MatchItem(requirement_id="s2", dimension="skill", requirement="preferred", priority=1, status=MatchStatus.MISMATCH),
    ]
    result = calculate_score(items)
    assert result.dimensions[1].score == 2 / 3


def test_project_dimension_uses_best_project_for_each_criterion():
    items = [
        MatchItem(requirement_id="project:scenario", dimension="project", requirement="场景", priority=1, status=MatchStatus.MISMATCH, project_name="旧项目"),
        MatchItem(requirement_id="project:scenario", dimension="project", requirement="场景", priority=1, status=MatchStatus.MATCH, project_name="相关项目"),
    ]
    result = calculate_score(items)
    assert result.total_score == 100.0


def test_project_dimension_falls_back_for_generic_requirement_ids():
    items = [
        MatchItem(requirement_id="req-1", dimension="project", requirement="项目经历", priority=2, status=MatchStatus.MATCH),
        MatchItem(requirement_id="req-2", dimension="project", requirement="项目成果", priority=1, status=MatchStatus.MATCH),
    ]
    result = calculate_score(items)
    assert result.dimensions[0].score == 1.0


def test_expected_current_date_case_has_high_score_but_failing_hard_gate():
    items = [
        MatchItem(requirement_id="project:task", dimension="project", requirement="数据分析项目", priority=1, status=MatchStatus.MATCH),
        MatchItem(requirement_id="skill:1", dimension="skill", requirement="Python 和 SQL", priority=2, status=MatchStatus.MATCH),
        MatchItem(requirement_id="education:degree", dimension="education", requirement="本科", priority=2, status=MatchStatus.MATCH),
        MatchItem(requirement_id="year:status", dimension="year", requirement="在读", priority=2, status=MatchStatus.MISMATCH),
    ]
    result = calculate_score(items)
    assert result.total_score == 94.62
    assert result.completeness == 1.0
    assert result.hard_gate == "fail"
