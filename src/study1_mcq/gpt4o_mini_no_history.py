"""GPT-4o mini no-history (C_default) reference run over the full 589-item
32k split.

This is an independent reference measurement, NOT a redefinition of strict.
strict_default_error stays fixed as the llama3.1:8b + qwen2.5:7b AND
(CLAUDE.md #4). GPT-4o mini's own solved/error/invalid classification here is
reported side by side with llama/qwen, never merged into their bucket.

temp=0 only (single run; no temp=0.2 stability layer — see
docs/QC_notes_gpt4o_mini_no_history_0623.md for why).
raw_output is persisted per item (CLAUDE.md #11).
"""

import ast
import csv
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from src.study1_mcq.canonical_types import to_canonical
from src.study1_mcq.prompting import gold_letter, query_openai

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "data" / "personamem_32k" / "questions_32k.csv"
OUT_DIR = REPO_ROOT / "results" / "study1"
PER_ITEM_PATH = OUT_DIR / "gpt4o_mini_no_history_589.csv"
SUMMARY_PATH = OUT_DIR / "gpt4o_mini_no_history_589_summary.json"

MODEL = "gpt-4o-mini"
TEMPERATURE = 0.0
MAX_TOKENS = 256  # matches gate1.py's NUM_PREDICT to avoid the same truncation bug

CSV_COLUMNS = ["item_id", "persona_id", "canonical_type", "gold_key", "gpt4o_mini_pred", "gpt4o_mini_raw", "gpt4o_mini_bucket", "parse_status"]


def model_bucket(pred_letter: str | None, gold: str) -> str:
    if pred_letter is None:
        return "parse_invalid"
    return "solved" if pred_letter == gold else "error"


def load_done_item_ids() -> set[str]:
    if not PER_ITEM_PATH.exists():
        return set()
    existing = pd.read_csv(PER_ITEM_PATH)
    return set(existing["item_id"].astype(str))


def run(api_key: str) -> None:
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

        resp = query_openai(MODEL, question, options, TEMPERATURE, api_key, max_tokens=MAX_TOKENS)
        bucket = model_bucket(resp.pred_letter, gold)

        writer.writerow(
            [item_id, row["persona_id"], canonical_type, gold, resp.pred_letter or "", resp.raw_response, bucket, resp.parse_status]
        )
        f.flush()

        if (i + 1) % 25 == 0 or (i + 1) == total:
            print(f"  processed {i + 1}/{total}")

    f.close()


def summarize() -> None:
    df = pd.read_csv(PER_ITEM_PATH)
    n = len(df)

    bucket_counts = df["gpt4o_mini_bucket"].value_counts().to_dict()
    buckets = {
        name: {"count": int(bucket_counts.get(name, 0)), "rate": bucket_counts.get(name, 0) / n}
        for name in ("solved", "error", "parse_invalid")
    }

    type_breakdown = []
    for qtype, g in df.groupby("canonical_type"):
        n_type = len(g)
        type_breakdown.append(
            {
                "canonical_type": qtype,
                "n": n_type,
                "solved_rate": (g["gpt4o_mini_bucket"] == "solved").mean(),
                "small_n": n_type < 30,
            }
        )

    summary = {
        "n_items": n,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "buckets": buckets,
        "sanity_gate": {"sum_equals_n_items": {"sum": sum(b["count"] for b in buckets.values()), "n_items": n}},
        "by_canonical_type": type_breakdown,
        "comparison_note": (
            "Independent reference measurement. Does NOT redefine strict_default_error "
            "(llama3.1:8b + qwen2.5:7b AND, CLAUDE.md #4). See "
            "docs/QC_notes_gpt4o_mini_no_history_0623.md for llama/qwen/gpt4o-mini comparison."
        ),
        "date": str(date.today()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY not set (env or .env). Stopping before any API call.")
    run(key)
    summarize()
