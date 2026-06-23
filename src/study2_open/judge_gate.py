"""Study 2 (LongMemEval) — determinacy filter + judge validation gate.

GATE-ONLY STAGE (CLAUDE.md #1, #2, #3). This script does NOT run any evidence-only
sufficiency experiment, any model-answering experiment, or any behavioral audit.
It produces:
  1. determinacy_filter.csv  — every non-KU oracle item, rule-flagged for target
     determinacy and single-source evidence localizability (proposal, not a final
     cut; see src/study2_open/determinacy_filter.py).
  2. judge_gate_sample.csv   — 30 determinacy-passing items (seed=619, sorted ids
     before sampling) with mechanically-built positive/negative control responses
     (see src/study2_open/negative_control.py — never LLM-free-generated).
  3. judge_gate_human_sheet.csv — the human adjudication sheet (empty human_*
     columns). The human is the authority; the judge is the object under test.
  4. judge_verdicts.csv      — per (item x control) judge verdict + raw_output.
  5. judge_prompt_v1.md      — the exact, version-pinned judge prompt used.
  6. judge_gate_summary.json — pool/sample counts and a PROVISIONAL judge-vs-
     intended-label signal (not the real gate result; that is the human verdict).
  7. README.md               — gate scope and next-step guardrail.

API key handling mirrors src/study1_mcq/phaseA_removal_feasibility.py: read
OPENAI_API_KEY from the environment (optionally via .env), and if absent, do not
make any API call (CLAUDE.md #13). Only the 30 sampled items' control pairs are
ever sent to the judge API — never the full LongMemEval corpus.
"""

import csv
import json
import os
import random
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.study2_open.determinacy_filter import (
    build_determinacy_table,
    evidence_text_from_item,
    load_oracle,
)
from src.study2_open.negative_control import build_negative_control

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "0623_study2_judge_gate"
DETERMINACY_PATH = OUT_DIR / "determinacy_filter.csv"
SAMPLE_PATH = OUT_DIR / "judge_gate_sample.csv"
HUMAN_SHEET_PATH = OUT_DIR / "judge_gate_human_sheet.csv"
VERDICTS_PATH = OUT_DIR / "judge_verdicts.csv"
PROMPT_PATH = OUT_DIR / "judge_prompt_v1.md"
SUMMARY_PATH = OUT_DIR / "judge_gate_summary.json"
README_PATH = OUT_DIR / "README.md"

SAMPLE_SIZE = 30
SEED = 619
JUDGE_MODEL = "gpt-4o-mini"
PROMPT_VERSION = "judge_prompt_v1"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

JUDGE_SYSTEM_PROMPT = """You are a strict evaluator judging whether a candidate response to a question is correct, using ONLY the provided evidence. Your task is to verify whether the candidate response is supported by the evidence, not whether it sounds plausible or fluent.

Rules you must follow strictly:
- Base your verdict ONLY on the provided evidence. Do not use outside/world knowledge to fill gaps, and do not guess.
- Mark "correct" only if the candidate response states the fact/value/preference that the evidence actually supports as the answer to the question.
- Mark "incorrect" if the candidate response states a different fact/value than the evidence supports, contradicts the evidence, or is a generic/non-committal statement that does not give the evidence-supported answer.
- A fluent, on-topic, but evidence-unsupported or factually different response must be marked "incorrect". Do not reward surface plausibility or topical relevance over evidence support.
- Return your answer as a single JSON object matching the schema given, with no extra commentary, no markdown fencing.
"""

JUDGE_USER_TEMPLATE = """## Question
{question}

## Evidence (verbatim, from the conversation history)
{evidence_text}

## Candidate response to judge
{candidate_response}

## Task
Judge whether the candidate response above is correct, i.e. whether it states the answer that the evidence supports.

Return exactly this JSON shape and nothing else:
{{
  "verdict": "correct" or "incorrect",
  "rationale": "..."
}}
"""

DETERMINACY_COLUMNS = [
    "question_id",
    "question_type",
    "excluded_as_ku",
    "is_abstention",
    "n_evidence_sessions",
    "n_has_answer_turns",
    "target_determinacy_flag",
    "target_determinacy_reason",
    "single_source_localizable_flag",
    "localizable_reason",
    "evidence_session_id",
    "evidence_turn_indices",
    "determinacy_filter_pass",
]

SAMPLE_COLUMNS = [
    "question_id",
    "question_type",
    "question",
    "positive_control_response",
    "negative_control_response",
    "negative_control_rule",
    "negative_control_reason",
    "evidence_session_id",
    "evidence_turn_indices",
    "evidence_text",
]

HUMAN_COLUMNS = [
    "human_positive_is_correct",
    "human_negative_is_correct",
    "human_notes",
    "human_determinacy_ok",
    "human_localizable_ok",
]

VERDICT_COLUMNS = [
    "question_id",
    "question_type",
    "control_type",
    "candidate_response",
    "intended_label",
    "judge_verdict",
    "judge_rationale",
    "matches_intended",
    "judge_raw_output",
]


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            out = {}
            for c in columns:
                v = row.get(c, "")
                if v is None:
                    v = ""
                elif isinstance(v, (list, dict)):
                    v = json.dumps(v, ensure_ascii=False)
                out[c] = v
            writer.writerow(out)


def call_judge(question: str, evidence_text: str, candidate_response: str, api_key: str) -> tuple[dict | None, str]:
    user_prompt = JUDGE_USER_TEMPLATE.format(
        question=question, evidence_text=evidence_text, candidate_response=candidate_response
    )
    resp = requests.post(
        OPENAI_CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": JUDGE_MODEL,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    raw_text = resp.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(raw_text), raw_text
    except json.JSONDecodeError:
        return None, raw_text


def type_counts(rows: list[dict], key: str = "question_type") -> dict:
    counts: dict = {}
    for r in rows:
        counts[r[key]] = counts.get(r[key], 0) + 1
    return counts


README_TEXT = """# Study 2 judge validation gate (0623)

## What this is

This is a **gate**, not a behavioral experiment. It answers two feasibility
questions before any evidence-use audit is run on LongMemEval:

1. Does a determinacy-filtered, single-source-localizable item pool survive at
   all (`determinacy_filter.csv`)?
2. Is the LLM judge trustworthy — does it accept gold answers and, crucially,
   reject evidence-independent answers (`judge_verdicts.csv`,
   `judge_gate_summary.json`)?

No sufficiency experiment, no model-answering experiment, and no behavioral audit
were run here (CLAUDE.md #1, #2, #3; docs/設計ブロック_0621.md §4-§5.1).

## Negative controls are rule-built, not LLM-generated

`negative_control_response` in `judge_gate_sample.csv` is built mechanically by
`src/study2_open/negative_control.py`: either a deterministic value substitution
(r1: year/weekday/month/ordinal-day/integer, shifted by a fixed rule) or a fixed
generic-deflection template that splices in the verbatim question text (r2). No
LLM was used to write any negative control, to avoid reintroducing the provenance
circularity already avoided in PersonaMem Phase A removal.

## Human adjudication is required before any sufficiency experiment

The judge verdicts in `judge_verdicts.csv` and the provisional signal in
`judge_gate_summary.json` are computed against the *intended* control labels
(positive=correct, negative=incorrect) — they are a provisional sanity signal,
not the real gate result. The human, not the judge, is the authority. Fill in
`judge_gate_human_sheet.csv` (human_positive_is_correct,
human_negative_is_correct, human_notes, human_determinacy_ok,
human_localizable_ok) before treating any item/type as gate-passing.

## What must NOT start yet

The next phase (Study 2a evidence-only sufficiency, and Study 2b evidence
contingency) must NOT start until:
  - `judge_gate_human_sheet.csv` is filled in, and
  - the judge gate is assessed against the human verdicts (raw agreement, false
    positive rate, false negative rate, per-type FP concentration — see
    docs/設計ブロック_0621.md §4.2).

False positives (the judge rating an evidence-independent negative_control
"correct") are the highest-priority defect to check, since they would let
evidence-independent answers pass as if they used evidence.
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")

    oracle_items = load_oracle()
    items_by_id = {it["question_id"]: it for it in oracle_items}

    determinacy_rows = build_determinacy_table(oracle_items)
    determinacy_rows.sort(key=lambda r: r["question_id"])
    write_csv(DETERMINACY_PATH, determinacy_rows, DETERMINACY_COLUMNS)

    non_ku_rows = [r for r in determinacy_rows if not r["excluded_as_ku"]]
    passing_rows = [r for r in non_ku_rows if r["determinacy_filter_pass"]]
    passing_by_id = {r["question_id"]: r for r in passing_rows}

    passing_ids_sorted = sorted(passing_by_id.keys())
    rng = random.Random(SEED)
    sampled_ids = sorted(rng.sample(passing_ids_sorted, k=min(SAMPLE_SIZE, len(passing_ids_sorted))))

    sample_rows = []
    for qid in sampled_ids:
        item = items_by_id[qid]
        drow = passing_by_id[qid]
        question = item["question"]
        positive = str(item["answer"])
        evidence_text = evidence_text_from_item(item, drow["evidence_turn_indices"])
        neg = build_negative_control(question, positive)
        sample_rows.append(
            {
                "question_id": qid,
                "question_type": item["question_type"],
                "question": question,
                "positive_control_response": positive,
                "negative_control_response": neg["negative_control_response"],
                "negative_control_rule": neg["negative_control_rule"],
                "negative_control_reason": neg["negative_control_reason"],
                "evidence_session_id": drow["evidence_session_id"],
                "evidence_turn_indices": drow["evidence_turn_indices"],
                "evidence_text": evidence_text,
            }
        )
    write_csv(SAMPLE_PATH, sample_rows, SAMPLE_COLUMNS)

    human_rows = []
    for row in sample_rows:
        hrow = dict(row)
        for c in HUMAN_COLUMNS:
            hrow[c] = ""
        human_rows.append(hrow)
    write_csv(HUMAN_SHEET_PATH, human_rows, SAMPLE_COLUMNS + HUMAN_COLUMNS)

    PROMPT_PATH.write_text(
        f"# Judge prompt: {PROMPT_VERSION}\n\n"
        "This is the exact, version-pinned prompt sent to the judge model "
        f"({JUDGE_MODEL}, temperature=0) for every (item x control) pair in the "
        "Study 2 judge validation gate.\n\n"
        "## System prompt\n\n```\n" + JUDGE_SYSTEM_PROMPT + "```\n\n"
        "## User prompt template\n\n```\n" + JUDGE_USER_TEMPLATE + "```\n"
    )

    verdict_rows = []
    n_judge_calls = 0
    n_judge_invalid = 0
    agreement_hits = 0
    fp_count = 0
    fn_count = 0
    fp_by_type: dict = {}

    for row in sample_rows:
        for control_type, candidate, intended in (
            ("positive", row["positive_control_response"], "correct"),
            ("negative", row["negative_control_response"], "incorrect"),
        ):
            verdict_row = {
                "question_id": row["question_id"],
                "question_type": row["question_type"],
                "control_type": control_type,
                "candidate_response": candidate,
                "intended_label": intended,
                "judge_verdict": "",
                "judge_rationale": "",
                "matches_intended": "",
                "judge_raw_output": "",
            }
            if control_type == "negative" and row["negative_control_rule"] == "unavailable":
                verdict_row["judge_verdict"] = "skipped"
                verdict_row["judge_raw_output"] = "SKIPPED: negative_control unavailable for this item"
                verdict_rows.append(verdict_row)
                continue
            if not api_key:
                verdict_row["judge_verdict"] = "skipped"
                verdict_row["judge_raw_output"] = "SKIPPED: OPENAI_API_KEY not set; no API call made"
                verdict_rows.append(verdict_row)
                continue

            n_judge_calls += 1
            judge_json, raw_text = call_judge(row["question"], row["evidence_text"], candidate, api_key)
            verdict_row["judge_raw_output"] = raw_text
            if judge_json is None or judge_json.get("verdict") not in ("correct", "incorrect"):
                n_judge_invalid += 1
                verdict_row["judge_verdict"] = "invalid"
            else:
                verdict_row["judge_verdict"] = judge_json["verdict"]
                verdict_row["judge_rationale"] = judge_json.get("rationale", "")
                matches = judge_json["verdict"] == intended
                verdict_row["matches_intended"] = matches
                agreement_hits += int(matches)
                if control_type == "negative" and judge_json["verdict"] == "correct":
                    fp_count += 1
                    fp_by_type[row["question_type"]] = fp_by_type.get(row["question_type"], 0) + 1
                if control_type == "positive" and judge_json["verdict"] == "incorrect":
                    fn_count += 1
            verdict_rows.append(verdict_row)

    write_csv(VERDICTS_PATH, verdict_rows, VERDICT_COLUMNS)

    rule_usage = {"r1": 0, "r2": 0, "unavailable": 0}
    unavailable_items = []
    for row in sample_rows:
        rule_usage[row["negative_control_rule"]] += 1
        if row["negative_control_rule"] == "unavailable":
            unavailable_items.append({"question_id": row["question_id"], "reason": row["negative_control_reason"]})

    n_judge_scored = n_judge_calls - n_judge_invalid
    summary = {
        "stage": "gate-only (no behavioral/sufficiency experiment)",
        "non_ku_pool_size": len(non_ku_rows),
        "non_ku_pool_by_type": type_counts(non_ku_rows),
        "determinacy_passing_pool_size": len(passing_rows),
        "determinacy_passing_pool_by_type": type_counts(passing_rows),
        "sample_size": len(sample_rows),
        "sample_by_type": type_counts(sample_rows),
        "negative_control_rule_usage": rule_usage,
        "unavailable_negative_controls": unavailable_items,
        "provisional_judge_signal_vs_intended_labels": {
            "note": (
                "PROVISIONAL: computed against intended control labels (positive=correct, "
                "negative=incorrect), not human verdicts. judge_gate_human_sheet.csv, once "
                "filled in by a human, is the real reference."
            ),
            "n_judge_calls_attempted": n_judge_calls,
            "n_judge_invalid_output": n_judge_invalid,
            "n_judge_scored": n_judge_scored,
            "raw_agreement": (agreement_hits / n_judge_scored) if n_judge_scored else None,
            "false_positive_count": fp_count,
            "false_negative_count": fn_count,
            "false_positive_by_type": fp_by_type,
        },
        "judge_model": JUDGE_MODEL if api_key else None,
        "prompt_version": PROMPT_VERSION,
        "api_key_source": "environment variable OPENAI_API_KEY (optionally loaded from local .env via python-dotenv)",
        "api_key_missing": api_key is None,
        "external_send_count": n_judge_calls,
        "random_seed": SEED,
        "sample_size_requested": SAMPLE_SIZE,
        "sampled_question_ids": sampled_ids,
        "date": str(date.today()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    README_PATH.write_text(README_TEXT)

    print("Files created:")
    for p in [DETERMINACY_PATH, SAMPLE_PATH, HUMAN_SHEET_PATH, VERDICTS_PATH, PROMPT_PATH, SUMMARY_PATH, README_PATH]:
        print(f"  {p.relative_to(REPO_ROOT)}")

    print(f"\nNon-KU pool size: {len(non_ku_rows)}")
    print(f"Non-KU pool by type: {summary['non_ku_pool_by_type']}")

    print(f"\nDeterminacy-filter passing pool size: {len(passing_rows)}")
    print(f"Passing pool by type: {summary['determinacy_passing_pool_by_type']}")

    print(f"\n30-sample by type: {summary['sample_by_type']}")

    print(f"\nNegative control rule usage: {rule_usage}")

    sig = summary["provisional_judge_signal_vs_intended_labels"]
    print("\nProvisional judge signal vs intended labels (PROVISIONAL — human verdicts pending):")
    print(f"  n_judge_calls_attempted: {sig['n_judge_calls_attempted']}")
    print(f"  n_judge_invalid_output: {sig['n_judge_invalid_output']}")
    print(f"  raw_agreement: {sig['raw_agreement']}")
    print(f"  false_positive_count: {sig['false_positive_count']}")
    print(f"  false_negative_count: {sig['false_negative_count']}")
    print(f"  false_positive_by_type: {sig['false_positive_by_type']}")

    if unavailable_items:
        print(f"\nItems where negative_control = unavailable ({len(unavailable_items)}):")
        for u in unavailable_items:
            print(f"  {u['question_id']}: {u['reason']}")
    else:
        print("\nNo items had negative_control = unavailable.")

    if api_key is None:
        print(
            "\nOPENAI_API_KEY not set: no judge API calls were made. "
            "judge_verdicts.csv contains SKIPPED rows only."
        )

    print(
        "\nGate stage complete. Human adjudication of judge_gate_human_sheet.csv is required "
        "before any evidence-only sufficiency experiment. Do not start the sufficiency "
        "(behavioral) phase until the human verdicts are filled and the judge gate is assessed."
    )


if __name__ == "__main__":
    main()
