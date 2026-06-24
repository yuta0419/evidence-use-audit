"""Study 2a Phase 4 — score auditor outputs with the fixed strict judge.

Reuses src.study2_open.judge_gate.call_judge (judge_prompt_v1, gpt-4o-mini,
temperature=0) verbatim — the judge is not redesigned or re-validated here
(CLAUDE.md / Study 2a brief; the lenient variant was tried separately in
judge_gate_lenient.py and rejected, see
docs/QC_notes_study2_judge_gate_human_adjudication_0623.md).

Every (model, condition, item) auditor output from Phase 3
(results/0623_study2a_sufficiency/{model}/{condition}/per_item.jsonl) is
scored against the SAME canonical evidence: the oracle gold span
(determinacy_filter.evidence_text_from_item), regardless of which condition
the auditor actually saw. The judge's job is to verify whether the
candidate's claim matches the ground-truth evidence, not to re-litigate what
context the auditor had — that comparison (noev vs oracle vs full) happens at
aggregation time, not by changing what the judge is shown.

Checkpointed JSONL per condition; resumable (CLAUDE.md #5, avoid double
billing the judge).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.study2_open.determinacy_filter import evidence_text_from_item, load_oracle
from src.study2_open.judge_gate import JUDGE_MODEL, PROMPT_VERSION, call_judge

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_DIR = REPO_ROOT / "results" / "0623_study2_judge_gate"
DETERMINACY_PATH = GATE_DIR / "determinacy_filter.csv"
JUDGE_PROMPT_PATH = GATE_DIR / "judge_prompt_v1.md"

AUDITOR_BASE = REPO_ROOT / "results" / "0623_study2a_sufficiency"
CONDITIONS = ("noev", "oracle", "full")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(model_slug: str, conditions: list[str]) -> None:
    manifest = {
        "script_version": "study2a_judge_score_v1_0623",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "auditor_model_slug": model_slug,
        "conditions_scored": conditions,
        "judge_model": JUDGE_MODEL,
        "judge_prompt_version": PROMPT_VERSION,
        "judge_prompt_path": str(JUDGE_PROMPT_PATH.relative_to(REPO_ROOT)),
        "judge_prompt_sha256": file_sha256(JUDGE_PROMPT_PATH),
        "evidence_shown_to_judge": "always the oracle gold span (determinacy_filter.evidence_text_from_item), "
        "regardless of which condition the auditor saw",
        "lenient_variant_rejected": "see docs/QC_notes_study2_judge_gate_human_adjudication_0623.md addendum",
    }
    out_path = auditor_dir(model_slug) / "judge_scores" / "manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

JUDGE_SCORE_COLUMNS = [
    "item_id", "question_type", "model", "condition",
    "candidate_response", "candidate_source",
    "judge_verdict", "judge_rationale", "judge_raw_output",
]


def auditor_dir(model_slug: str) -> Path:
    return AUDITOR_BASE / model_slug


def judge_score_path(model_slug: str, condition: str) -> Path:
    return auditor_dir(model_slug) / "judge_scores" / f"{condition}.jsonl"


def load_auditor_records(model_slug: str, condition: str) -> list[dict]:
    path = auditor_dir(model_slug) / condition / "per_item.jsonl"
    records = []
    with open(path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_evidence_turn_indices() -> dict[str, list[int]]:
    import csv

    out: dict[str, list[int]] = {}
    with open(DETERMINACY_PATH) as f:
        for row in csv.DictReader(f):
            raw = row["evidence_turn_indices"]
            out[row["question_id"]] = json.loads(raw) if raw else []
    return out


def load_done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done = set()
    with open(path) as f:
        for line in f:
            if line.strip():
                done.add(json.loads(line)["item_id"])
    return done


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def candidate_response_for(auditor_record: dict) -> tuple[str, str]:
    """Never discard raw_output (CLAUDE.md #11): prefer parsed_answer, fall
    back to raw_output if parsing failed, fall back to empty string only if
    both are empty."""
    if auditor_record.get("parsed_answer"):
        return auditor_record["parsed_answer"], "parsed_answer"
    if auditor_record.get("raw_output", "").strip():
        return auditor_record["raw_output"], "raw_output_fallback"
    return "", "empty"


def run(model_slug: str, conditions: list[str]) -> dict:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set. Stopping before any API call.")

    write_manifest(model_slug, conditions)

    oracle_items = {it["question_id"]: it for it in load_oracle()}
    evidence_turn_indices_by_id = load_evidence_turn_indices()

    n_scored = 0
    n_skipped_empty = 0
    n_invalid = 0

    for condition in conditions:
        auditor_records = load_auditor_records(model_slug, condition)
        out_path = judge_score_path(model_slug, condition)
        done = load_done_ids(out_path)

        for i, rec in enumerate(auditor_records, start=1):
            item_id = rec["item_id"]
            if item_id in done:
                continue

            item = oracle_items[item_id]
            evidence_text = evidence_text_from_item(item, evidence_turn_indices_by_id.get(item_id, []))
            candidate_response, candidate_source = candidate_response_for(rec)

            score_record = {
                "item_id": item_id,
                "question_type": rec["question_type"],
                "model": rec["model"],
                "condition": condition,
                "candidate_response": candidate_response,
                "candidate_source": candidate_source,
                "judge_verdict": "",
                "judge_rationale": "",
                "judge_raw_output": "",
            }

            if candidate_source == "empty":
                score_record["judge_verdict"] = "skipped_empty_response"
                n_skipped_empty += 1
                append_record(out_path, score_record)
                continue

            judge_json, raw_text = call_judge(item["question"], evidence_text, candidate_response, api_key)
            score_record["judge_raw_output"] = raw_text
            if judge_json is None or judge_json.get("verdict") not in ("correct", "incorrect"):
                score_record["judge_verdict"] = "invalid"
                n_invalid += 1
            else:
                score_record["judge_verdict"] = judge_json["verdict"]
                score_record["judge_rationale"] = judge_json.get("rationale", "")
                n_scored += 1
            append_record(out_path, score_record)
            print(f"  [{condition}] {i}/{len(auditor_records)} item_id={item_id} verdict={score_record['judge_verdict']}")

    return {
        "judge_model": JUDGE_MODEL,
        "judge_prompt_version": PROMPT_VERSION,
        "n_scored": n_scored,
        "n_skipped_empty": n_skipped_empty,
        "n_invalid": n_invalid,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score Study 2a auditor outputs with the fixed strict judge")
    p.add_argument("--model-slug", default="gpt_4o_mini", help="output dir slug under results/0623_study2a_sufficiency/")
    p.add_argument("--condition", choices=[*CONDITIONS, "all"], default="all")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    conditions = list(CONDITIONS) if args.condition == "all" else [args.condition]
    summary = run(args.model_slug, conditions)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
