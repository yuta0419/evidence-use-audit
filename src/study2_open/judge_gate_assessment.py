"""Score a judge's verdicts against the human-confirmed ground truth.

Shared by the strict (judge_verdicts.csv) and lenient (judge_verdicts_lenient.csv)
judge variants so both are scored with the same, symmetric FP/FN definition:

  - false positive (FP): judge says "correct" on a control the human ground
    truth says is actually "incorrect" (for EITHER the positive or the
    negative control — an earlier version of this scoring only checked this
    direction for negative controls, which silently missed positive-control
    over-acceptance errors; fixed here, see
    docs/QC_notes_study2_judge_gate_human_adjudication_0623.md).
  - false negative (FN): judge says "incorrect" on a control the human
    ground truth says is actually "correct".

Human ground truth (judge_gate_human_sheet.csv: human_positive_is_correct /
human_negative_is_correct) is judge-prompt-agnostic — it answers "is this
response actually correct given the evidence", independent of which judge
configuration is being scored. The same human sheet is the reference for
both strict and lenient.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_DIR = REPO_ROOT / "results" / "0623_study2_judge_gate"
SAMPLE_PATH = GATE_DIR / "judge_gate_sample.csv"
HUMAN_SHEET_PATH = GATE_DIR / "judge_gate_human_sheet.csv"


def human_truth(value: str) -> str:
    return "correct" if value == "yes" else "incorrect"


def score_against_human_truth(verdicts_path: Path) -> dict:
    sample_rows = {r["question_id"]: r for r in csv.DictReader(open(SAMPLE_PATH))}
    human_rows = {r["question_id"]: r for r in csv.DictReader(open(HUMAN_SHEET_PATH))}

    verdicts = defaultdict(dict)
    for r in csv.DictReader(open(verdicts_path)):
        verdicts[r["question_id"]][r["control_type"]] = r

    per_type = defaultdict(lambda: {"item_ids": set(), "n_judgments": 0, "agree": 0, "fp": 0, "fn": 0})
    overall = {"n_judgments": 0, "agree": 0, "fp": 0, "fn": 0}

    for qid, srow in sample_rows.items():
        qtype = srow["question_type"]
        hrow = human_rows[qid]
        per_type[qtype]["item_ids"].add(qid)
        for control_type, human_col in (("positive", "human_positive_is_correct"), ("negative", "human_negative_is_correct")):
            v = verdicts[qid].get(control_type)
            if v is None or v["judge_verdict"] not in ("correct", "incorrect"):
                continue
            jv = v["judge_verdict"]
            truth = human_truth(hrow[human_col])
            per_type[qtype]["n_judgments"] += 1
            overall["n_judgments"] += 1
            if jv == truth:
                per_type[qtype]["agree"] += 1
                overall["agree"] += 1
            elif jv == "correct" and truth == "incorrect":
                per_type[qtype]["fp"] += 1
                overall["fp"] += 1
            elif jv == "incorrect" and truth == "correct":
                per_type[qtype]["fn"] += 1
                overall["fn"] += 1

    def rate(d: dict) -> dict:
        n = d["n_judgments"]
        return {
            "n_items": len(d["item_ids"]),
            "n_judgments": n,
            "raw_agreement": d["agree"] / n if n else None,
            "false_positive_count": d["fp"],
            "false_negative_count": d["fn"],
            "item_ids": sorted(d["item_ids"]),
        }

    return {
        "overall": {
            "n_judgments": overall["n_judgments"],
            "raw_agreement": overall["agree"] / overall["n_judgments"] if overall["n_judgments"] else None,
            "false_positive_count": overall["fp"],
            "false_negative_count": overall["fn"],
        },
        "by_type": {qtype: rate(d) for qtype, d in per_type.items()},
    }


def write_summary(verdicts_path: Path, out_path: Path, *, prompt_version: str, judge_model: str, extra_note: str) -> dict:
    scored = score_against_human_truth(verdicts_path)
    summary = {
        "note": extra_note,
        "judge_model": judge_model,
        "prompt_version": prompt_version,
        **scored,
    }
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    strict_summary = write_summary(
        GATE_DIR / "judge_verdicts.csv",
        GATE_DIR / "judge_gate_human_assessment_summary.json",
        prompt_version="judge_prompt_v1",
        judge_model="gpt-4o-mini",
        extra_note=(
            "Computed against HUMAN ground truth (judge_gate_human_sheet.csv, human-confirmed 2026-06-23), "
            "not the provisional intended-label signal in judge_gate_summary.json. FP/FN are symmetric: FP = "
            "judge says correct when human truth says incorrect (either control type); FN = judge says incorrect "
            "when human truth says correct. (Corrected 2026-06-23 from an earlier version that only checked FP "
            "on negative controls and FN on positive controls — see docs/QC_notes_study2_judge_gate_human_adjudication_0623.md.)"
        ),
    )
    lenient_summary = write_summary(
        GATE_DIR / "judge_verdicts_lenient.csv",
        GATE_DIR / "judge_gate_lenient_assessment_summary.json",
        prompt_version="judge_prompt_v2_lenient",
        judge_model="gpt-4o-mini",
        extra_note=(
            "Lenient judge (judge_prompt_v2_lenient), scored against the SAME human ground truth used for the "
            "strict judge (judge_gate_human_sheet.csv, human-confirmed 2026-06-23) — not a fresh human re-label, "
            "since that ground truth answers a judge-agnostic question (is this response actually correct given "
            "the evidence). Directly comparable to judge_gate_human_assessment_summary.json. Uses the same "
            "symmetric FP/FN definition (see module docstring)."
        ),
    )
    print("STRICT:", json.dumps(strict_summary["overall"], indent=2))
    print("LENIENT:", json.dumps(lenient_summary["overall"], indent=2))
