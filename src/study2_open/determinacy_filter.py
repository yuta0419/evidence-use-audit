"""Determinacy filter for LongMemEval (Study 2, gate stage).

Proposal/flagging step only (CLAUDE.md #3; docs/設計ブロック_0621.md §5.1). Marks
each non-KU oracle item for:
  - target_determinacy_flag: does the item have a positive, content-bearing gold
    target? False for abstention items (question_id ending "_abs"), whose gold
    target is "insufficient information" rather than a fact to audit for evidence
    sufficiency.
  - single_source_localizable_flag: can the supporting evidence be localized to
    exactly one session, using the oracle split's own per-turn `has_answer`
    annotations?
Both flags are rule-based over fields the oracle split already carries — no LLM
call, no human judgment. This is a proposal for human review, not an automatic
final cut: human adjudication of judge_gate_human_sheet.csv decides inclusion.

KU items are excluded entirely upstream of these flags (CLAUDE.md invariant;
designed-block §5.1: knowledge-update items structurally contain competing
old/new values and violate single-source localization).
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORACLE_PATH = REPO_ROOT / "data" / "longmemeval" / "longmemeval_oracle.json"

KU_TYPE = "knowledge-update"


def load_oracle() -> list[dict]:
    return json.loads(ORACLE_PATH.read_text())


def is_abstention(question_id: str) -> bool:
    return question_id.endswith("_abs")


def evaluate_item(item: dict) -> dict:
    """Rule-based determinacy flags for one non-KU oracle item."""
    sessions = item["haystack_sessions"]
    n_evidence_sessions = len(sessions)
    answer_turns_by_session = [[i for i, t in enumerate(s) if t.get("has_answer")] for s in sessions]
    n_has_answer_turns = sum(len(ts) for ts in answer_turns_by_session)
    abstention = is_abstention(item["question_id"])

    target_determinacy_flag = not abstention
    target_determinacy_reason = (
        "abstention item: gold target is 'insufficient information', not a positive "
        "fact to audit for evidence sufficiency"
        if abstention
        else ""
    )

    single_source_localizable_flag = n_evidence_sessions == 1 and n_has_answer_turns >= 1
    if n_evidence_sessions != 1:
        localizable_reason = f"evidence spans {n_evidence_sessions} sessions, not 1"
    elif n_has_answer_turns == 0:
        localizable_reason = "no has_answer turn found within the single evidence session"
    else:
        localizable_reason = ""

    if single_source_localizable_flag:
        evidence_session_id = item["haystack_session_ids"][0]
        evidence_turn_indices = answer_turns_by_session[0]
    else:
        evidence_session_id = ""
        evidence_turn_indices = []

    return {
        "question_id": item["question_id"],
        "question_type": item["question_type"],
        "excluded_as_ku": False,
        "is_abstention": abstention,
        "n_evidence_sessions": n_evidence_sessions,
        "n_has_answer_turns": n_has_answer_turns,
        "target_determinacy_flag": target_determinacy_flag,
        "target_determinacy_reason": target_determinacy_reason,
        "single_source_localizable_flag": single_source_localizable_flag,
        "localizable_reason": localizable_reason,
        "evidence_session_id": evidence_session_id,
        "evidence_turn_indices": evidence_turn_indices,
        "determinacy_filter_pass": target_determinacy_flag and single_source_localizable_flag,
    }


def build_determinacy_table(oracle_items: list[dict]) -> list[dict]:
    """Evaluate every oracle item. KU items are recorded as excluded, not evaluated."""
    rows = []
    for item in oracle_items:
        if item["question_type"] == KU_TYPE:
            rows.append(
                {
                    "question_id": item["question_id"],
                    "question_type": item["question_type"],
                    "excluded_as_ku": True,
                    "is_abstention": is_abstention(item["question_id"]),
                    "n_evidence_sessions": len(item["haystack_sessions"]),
                    "n_has_answer_turns": None,
                    "target_determinacy_flag": False,
                    "target_determinacy_reason": "excluded: knowledge-update (competing old/new values; CLAUDE.md invariant)",
                    "single_source_localizable_flag": False,
                    "localizable_reason": "excluded: knowledge-update",
                    "evidence_session_id": "",
                    "evidence_turn_indices": [],
                    "determinacy_filter_pass": False,
                }
            )
            continue
        rows.append(evaluate_item(item))
    return rows


def evidence_text_from_item(item: dict, evidence_turn_indices: list[int]) -> str:
    """Verbatim text of the localized evidence turns (single-session items only)."""
    if not evidence_turn_indices:
        return ""
    session = item["haystack_sessions"][0]
    turns = [session[i] for i in evidence_turn_indices]
    return "\n".join(f"{t['role']}: {t['content']}" for t in turns)
