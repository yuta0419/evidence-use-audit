"""Step A: Gate 1 — default-solvability three-way split.

C_default = question (user_question_or_message) + native options (all_options)
only. No persona profile / shared context / retrieved memory / evidence
snippet is ever included (CLAUDE.md #9).

Per-model temp=0 status (3 states): solved / error / parse_invalid.
Item-level bucket (CLAUDE.md #4, #5 — this is the only bucket definition;
M3 never enters it):
  - t0_parse_invalid:     either model's temp=0 output failed to parse
  - strict_default_error: both models parse-valid and both != gold
  - loose_default_error:  both models parse-valid, exactly one == gold
  - default_solved:       both models parse-valid and both == gold

unstable_any (separate attribute, independent of the bucket above): for a
model that is *solved* at temp=0, we run 5 additional samples at
temp=0.2 and check whether all 5 reproduce the correct letter. If a model
is not solved at temp=0 it is not eligible for this check. unstable_any is
True if any eligible model is unstable, False if all eligible models are
stable, and None (not applicable) if no model is eligible (i.e. the item
is not solved by either model at temp=0).
"""

import ast
import csv
import json
from pathlib import Path

import pandas as pd

from src.study1_mcq.canonical_types import to_canonical
from src.study1_mcq.prompting import gold_letter, query

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "personamem_32k" / "questions_32k.csv"
OUT_DIR = Path(__file__).resolve().parents[2] / "results" / "study1"
PER_ITEM_PATH = OUT_DIR / "gate1_per_item.csv"
SUMMARY_PATH = OUT_DIR / "gate1_summary.json"

MODELS = {"llama": "llama3.1:8b", "qwen": "qwen2.5:7b"}
N_STABILITY_RUNS = 5
STABILITY_TEMP = 0.2
NUM_PREDICT = 256  # 2026-06-22: raised from 16 (see docs/QC_notes_gate1_rerun_0622.md)

OLD_BASELINE = {
    "source": "docs/設計ブロック_0621.md §3.1",
    "models": ["llama3.1:8b", "qwen2.5:7b"],
    "n_items": 589,
    "strict_default_error": {"count": 266, "rate": 266 / 589},
    "loose_default_error": {"count": 166, "rate": 166 / 589},
    "default_solved": {"count": 157, "rate": 157 / 589},
    "note": "旧run参考値。新runでの再現を目的としない。新run値と並記のみ。",
}

V1_BUGGY_RUN_REFERENCE = {
    "source": "results/study1/archive_v1_truncation_and_article_bug/gate1_summary.json",
    "models": ["llama3.1:8b", "qwen2.5:7b"],
    "n_items": 589,
    "num_predict": 16,
    "parser": "leading-token-only (parse_letter_v1_leading_token)",
    "strict_default_error": {"count": 273, "rate": 273 / 589},
    "loose_default_error": {"count": 161, "rate": 161 / 589},
    "default_solved": {"count": 144, "rate": 144 / 589},
    "t0_parse_invalid": {"count": 11, "rate": 11 / 589},
    "note": (
        "この新run内の前回値。num_predict=16 truncation と leading-token parser の "
        "'A'冠詞誤検出バグの影響下にある値（docs/QC_notes_gate1_new_run.md,"
        "docs/QC_notes_gate1_rerun_0622.md 参照）。今回の修正後run値と並記のみ。"
    ),
}

CSV_COLUMNS = [
    "item_id",
    "persona_id",
    "question_type",
    "gold_key",
    "llama_t0_pred",
    "qwen_t0_pred",
    "llama_t0_raw",
    "qwen_t0_raw",
    "llama_t0_bucket",
    "qwen_t0_bucket",
    "item_default_bucket",
    "unstable_any",
    "parse_status",
]


def model_t0_bucket(pred_letter: str | None, gold: str) -> str:
    if pred_letter is None:
        return "parse_invalid"
    return "solved" if pred_letter == gold else "error"


def item_bucket(llama_bucket: str, qwen_bucket: str) -> str:
    if llama_bucket == "parse_invalid" or qwen_bucket == "parse_invalid":
        return "t0_parse_invalid"
    solved_count = sum(b == "solved" for b in (llama_bucket, qwen_bucket))
    if solved_count == 2:
        return "default_solved"
    if solved_count == 0:
        return "strict_default_error"
    return "loose_default_error"


def check_unstable(model: str, question: str, options: list[str], gold: str) -> bool:
    for _ in range(N_STABILITY_RUNS):
        resp = query(model, question, options, STABILITY_TEMP, num_predict=NUM_PREDICT)
        if resp.pred_letter != gold:
            return True
    return False


def load_done_item_ids() -> set[str]:
    if not PER_ITEM_PATH.exists():
        return set()
    existing = pd.read_csv(PER_ITEM_PATH)
    return set(existing["item_id"].astype(str))


def run_gate1() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH)

    done_ids = load_done_item_ids()
    write_header = not PER_ITEM_PATH.exists()
    f = open(PER_ITEM_PATH, "a", newline="", encoding="utf-8")
    writer = csv.writer(f)
    if write_header:
        writer.writerow(CSV_COLUMNS)

    total = len(df)
    for i, row in df.iterrows():
        item_id = str(row["question_id"])
        if item_id in done_ids:
            continue

        question = row["user_question_or_message"]
        options = ast.literal_eval(row["all_options"])
        gold = gold_letter(row["correct_answer"])
        canonical_type = to_canonical(row["question_type"])

        t0 = {}
        t0_raw = {}
        for key, model_name in MODELS.items():
            resp = query(model_name, question, options, 0.0, num_predict=NUM_PREDICT)
            t0[key] = resp.pred_letter
            t0_raw[key] = resp.raw_response

        llama_bucket = model_t0_bucket(t0["llama"], gold)
        qwen_bucket = model_t0_bucket(t0["qwen"], gold)
        bucket = item_bucket(llama_bucket, qwen_bucket)
        parse_status = "valid" if "parse_invalid" not in (llama_bucket, qwen_bucket) else "invalid"

        unstable_flags = []
        for key, model_name in MODELS.items():
            model_bucket = llama_bucket if key == "llama" else qwen_bucket
            if model_bucket == "solved":
                unstable_flags.append(check_unstable(model_name, question, options, gold))
        unstable_any = any(unstable_flags) if unstable_flags else None

        row_out = [
            item_id,
            str(row["persona_id"]),
            canonical_type,
            gold,
            t0["llama"] if t0["llama"] is not None else "",
            t0["qwen"] if t0["qwen"] is not None else "",
            t0_raw["llama"],
            t0_raw["qwen"],
            llama_bucket,
            qwen_bucket,
            bucket,
            "" if unstable_any is None else str(unstable_any),
            parse_status,
        ]
        writer.writerow(row_out)
        f.flush()

        if (i + 1) % 25 == 0 or (i + 1) == total:
            print(f"  processed {i + 1}/{total}")

    f.close()


def summarize() -> None:
    df = pd.read_csv(PER_ITEM_PATH)
    n = len(df)

    bucket_counts = df["item_default_bucket"].value_counts().to_dict()
    buckets_summary = {
        name: {"count": int(bucket_counts.get(name, 0)), "rate": bucket_counts.get(name, 0) / n}
        for name in ("strict_default_error", "loose_default_error", "default_solved", "t0_parse_invalid")
    }

    total_check_sum = sum(b["count"] for b in buckets_summary.values())

    consistency_mismatches = 0
    for _, row in df.iterrows():
        if row["item_default_bucket"] == "t0_parse_invalid":
            continue
        solved_count = sum(row[c] == "solved" for c in ("llama_t0_bucket", "qwen_t0_bucket"))
        expected = {2: "default_solved", 1: "loose_default_error", 0: "strict_default_error"}[solved_count]
        if row["item_default_bucket"] != expected:
            consistency_mismatches += 1

    eligible_mask = df["unstable_any"].notna()
    n_eligible = int(eligible_mask.sum())
    n_unstable = int((df.loc[eligible_mask, "unstable_any"] == True).sum())  # noqa: E712

    summary = {
        "n_items": n,
        "buckets": buckets_summary,
        "sanity_gate": {
            "bucket_sum_equals_n_items": {"sum": total_check_sum, "n_items": n, "pass": total_check_sum == n},
            "per_model_to_item_bucket_consistency": {
                "mismatches": consistency_mismatches,
                "pass": consistency_mismatches == 0,
            },
        },
        "unstable": {
            "definition": (
                "model is eligible if its temp=0 prediction == gold; "
                "unstable if any of 5 temp=0.2 samples != gold; "
                "unstable_any (item) = OR over eligible models"
            ),
            "n_eligible_model_item_checks": n_eligible,
            "n_unstable_model_item_checks": n_unstable,
        },
        "old_baseline_reference": OLD_BASELINE,
        "v1_buggy_run_reference": V1_BUGGY_RUN_REFERENCE,
    }

    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_gate1()
    summarize()
