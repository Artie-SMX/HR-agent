"""Evidence verification tolerant of OCR and punctuation variation."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from models import EvidenceVerification, SourceEvidence


_PUNCT_TRANSLATION = str.maketrans({
    "，": ",", "。": ".", "；": ";", "：": ":", "！": "!", "？": "?",
    "（": "(", "）": ")", "【": "[", "】": "]", "“": '"', "”": '"',
    "‘": "'", "’": "'", "、": ",", "－": "-", "—": "-", "–": "-",
})


def normalize_for_match(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").translate(_PUNCT_TRANSLATION)
    # Common OCR confusions are normalized only when the digit is inside an
    # alphabetic token; standalone numbers (years, scores, versions) remain intact.
    value = re.sub(r"(?<=[A-Za-z])0(?=[A-Za-z])", "o", value)
    value = re.sub(r"(?<=[A-Za-z])1(?=[A-Za-z])", "l", value)
    return re.sub(r"\s+", "", value).casefold()


def _similarity(left: str, right: str) -> float:
    try:
        from rapidfuzz.fuzz import ratio
        return ratio(left, right) / 100
    except ImportError:
        return SequenceMatcher(None, left, right).ratio()


def best_window_similarity(quote: str, page_text: str) -> tuple[float, str]:
    target = normalize_for_match(quote)
    source = normalize_for_match(page_text)
    if not target or not source:
        return 0.0, ""
    if target in source:
        return 1.0, quote
    # A small band around the target length handles one OCR character added/removed.
    lengths = range(max(1, len(target) - 3), min(len(source), len(target) + 3) + 1)
    best = (0.0, "")
    for size in lengths:
        for start in range(0, len(source) - size + 1):
            candidate = source[start:start + size]
            score = _similarity(target, candidate)
            if score > best[0]:
                best = (score, candidate)
    return best


def verify_evidence(evidence: SourceEvidence, page_text: str, *, threshold: float = 0.85) -> SourceEvidence:
    """Return a copy annotated with exact, normalized, fuzzy or failed verification."""
    if evidence.page < 1 or not evidence.quote.strip():
        return evidence.model_copy(update={"verification_status": EvidenceVerification.FAILED, "match_method": "failed"})
    normalized_quote = normalize_for_match(evidence.quote)
    normalized_page = normalize_for_match(page_text)
    if normalized_quote and normalized_quote in normalized_page:
        return evidence.model_copy(update={
            "verification_status": EvidenceVerification.VERIFIED,
            "match_method": "normalized_substring",
            "similarity": 1.0,
            "matched_text": evidence.quote,
        })
    similarity, matched = best_window_similarity(evidence.quote, page_text)
    if similarity >= threshold:
        return evidence.model_copy(update={
            "verification_status": EvidenceVerification.VERIFIED,
            "match_method": "fuzzy_window",
            "similarity": round(similarity, 4),
            "matched_text": matched,
        })
    return evidence.model_copy(update={
        "verification_status": EvidenceVerification.UNKNOWN,
        "match_method": "not_found",
        "similarity": round(similarity, 4),
        "matched_text": None,
    })
