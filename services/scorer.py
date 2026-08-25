"""Deterministic scoring; the LLM supplies judgments, never the final arithmetic."""

from __future__ import annotations

from collections import defaultdict

from models import DimensionScore, MatchItem, MatchStatus, ScoreBreakdown


DEFAULT_WEIGHTS = {
    "project": 45.0,
    "skill": 35.0,
    "education": 8.0,
    "major": 7.0,
    "year": 5.0,
    "school_level": 0.0,
}
STATUS_SCORE = {
    MatchStatus.MATCH: 1.0,
    MatchStatus.PARTIAL: 0.5,
    MatchStatus.MISMATCH: 0.0,
    MatchStatus.UNKNOWN: 0.0,
}


def _project_score(items: list[MatchItem]) -> float:
    """Per-criterion max: a strong relevant project is not penalized by unrelated projects."""
    if not items:
        return 0.0
    by_criterion: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for item in items:
        # The extractor labels project sub-criteria as scenario/task/skill/outcome.
        criterion = item.requirement_id.split(":", 1)[-1]
        by_criterion[criterion].append((STATUS_SCORE.get(item.status, 0.0), item.priority))
    internal = {"scenario": 0.30, "task": 0.30, "skill": 0.30, "outcome": 0.10}
    weighted = 0.0
    used = 0.0
    for criterion, weight in internal.items():
        values = by_criterion.get(criterion)
        if values:
            best_score = max(score for score, _priority in values)
            best_priority = max(priority for score, priority in values if score == best_score)
            weighted += weight * best_score * best_priority
            used += weight * best_priority
    if used:
        return weighted / used
    # A model may return generic IDs such as req-3 instead of criterion IDs.
    # Keep the project dimension scorable with the same must/preferred rule.
    scores = [STATUS_SCORE.get(item.status, 0.0) for item in items]
    priorities = [item.priority for item in items]
    return sum(score * priority for score, priority in zip(scores, priorities)) / sum(priorities)


def calculate_score(matches: list[MatchItem], weights: dict[str, float] | None = None) -> ScoreBreakdown:
    weights = weights or DEFAULT_WEIGHTS
    grouped: dict[str, list[MatchItem]] = defaultdict(list)
    for item in matches:
        if item.status != MatchStatus.NA:
            grouped[item.dimension].append(item)
    valid_weights = {name: weight for name, weight in weights.items() if grouped.get(name) and weight > 0}
    denominator = sum(valid_weights.values()) or 1.0
    dimensions: list[DimensionScore] = []
    total = 0.0
    applicable = known = 0
    for dimension, raw_weight in weights.items():
        items = grouped.get(dimension, [])
        if not items:
            dimensions.append(DimensionScore(dimension=dimension, raw_weight=raw_weight))
            continue
        scores = [STATUS_SCORE.get(item.status, 0.0) for item in items]
        priorities = [item.priority for item in items]
        # Within a dimension: must=2 and preferred=1 weighted average.
        dimension_score = _project_score(items) if dimension == "project" else sum(score * priority for score, priority in zip(scores, priorities)) / sum(priorities)
        normalized = raw_weight / denominator if raw_weight > 0 else 0.0
        total += normalized * dimension_score
        applicable += len(items)
        dimension_known = sum(item.status in {MatchStatus.MATCH, MatchStatus.PARTIAL, MatchStatus.MISMATCH} for item in items)
        known += dimension_known
        dimensions.append(DimensionScore(
            dimension=dimension,
            raw_weight=raw_weight,
            normalized_weight=normalized,
            score=dimension_score,
            applicable_items=len(items),
            known_items=dimension_known,
        ))
    hard = [item for item in matches if item.priority == 2 and item.status == MatchStatus.MISMATCH]
    hard_gate = "fail" if hard else ("pass" if all(item.status != MatchStatus.UNKNOWN for item in matches if item.priority == 2) else "review")
    return ScoreBreakdown(
        total_score=round(total * 100, 2),
        completeness=round(known / applicable, 4) if applicable else 0.0,
        dimensions=dimensions,
        hard_gate=hard_gate,
        formula=(
            "w_normalized_i = w_i / sum(valid_weights); "
            "S_i = sum(priority_j * score_j) / sum(priority_j); "
            "total = 100 * sum(w_normalized_i * S_i). "
            "Project: P_r = max(projects) for each criterion, internal weights 0.30/0.30/0.30/0.10."
        ),
    )
