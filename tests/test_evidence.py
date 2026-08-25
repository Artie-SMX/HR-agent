from services.evidence import normalize_for_match, verify_evidence
from models import EvidenceVerification, SourceEvidence


def test_normalized_substring_handles_spaces_and_punctuation():
    assert normalize_for_match("Python，数据分析") == "python,数据分析"
    evidence = SourceEvidence(document_id="resume", page=1, quote="Python，数据分析")
    checked = verify_evidence(evidence, "技能： Python, 数据分析")
    assert checked.verification_status == EvidenceVerification.VERIFIED
    assert checked.match_method == "normalized_substring"


def test_fuzzy_window_handles_small_ocr_error():
    evidence = SourceEvidence(document_id="resume", page=1, quote="Pyth0n")
    checked = verify_evidence(evidence, "技能：Python")
    assert checked.verification_status == EvidenceVerification.VERIFIED
    assert checked.match_method in {"normalized_substring", "fuzzy_window"}


def test_missing_quote_becomes_unknown_not_match():
    evidence = SourceEvidence(document_id="resume", page=1, quote="Java")
    checked = verify_evidence(evidence, "技能：Python")
    assert checked.verification_status == EvidenceVerification.UNKNOWN
