"""Diagnostic-only investigation of the 11 t0_parse_invalid items from Gate 1.

Scope (per explicit user authorization, 2026-06-22):
  - Targets only the 11 items currently in item_default_bucket ==
    't0_parse_invalid' in the existing results/study1/gate1_per_item.csv.
  - Re-queries only the model(s) whose t0 prediction was NaN for that item
    (confirmed: llama3.1:8b in all 11 cases; qwen2.5:7b parsed validly for
    all 11 and is not re-queried).
  - temp=0, reusing build_prompt/call_ollama/parse_letter from prompting.py
    unmodified. This is a diagnostic capture of raw_output, not a new Gate 1
    run: it must never write to gate1_per_item.csv, gate1_summary.json, or
    strict_pool.csv, and must never change any bucket count.
  - If the re-parsed letter differs from the original (None, since these
    items were parse_invalid), that is reported as a determinism flag, not
    silently accepted.
"""

import ast
import json
from pathlib import Path

import pandas as pd

from src.study1_mcq.canonical_types import to_canonical
from src.study1_mcq.prompting import build_prompt, call_ollama, gold_letter, parse_letter

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "study1"
GATE1_PER_ITEM_PATH = RESULTS_DIR / "gate1_per_item.csv"
QUESTIONS_PATH = Path(__file__).resolve().parents[2] / "data" / "personamem_32k" / "questions_32k.csv"

OUT_PATH = RESULTS_DIR / "parse_invalid_diagnosis.csv"

MODELS = {"llama": "llama3.1:8b", "qwen": "qwen2.5:7b"}


def main() -> None:
    gate1 = pd.read_csv(GATE1_PER_ITEM_PATH)
    invalid = gate1[gate1["item_default_bucket"] == "t0_parse_invalid"].copy()
    questions = pd.read_csv(QUESTIONS_PATH).set_index("question_id")

    rows = []
    for _, item in invalid.iterrows():
        item_id = item["item_id"]
        q_row = questions.loc[item_id]
        question = q_row["user_question_or_message"]
        options = ast.literal_eval(q_row["all_options"])
        gold = gold_letter(q_row["correct_answer"])

        for key, model_name in MODELS.items():
            orig_pred = item["llama_t0_pred"] if key == "llama" else item["qwen_t0_pred"]
            orig_was_invalid = pd.isna(orig_pred)
            if not orig_was_invalid:
                continue  # this model parsed fine originally; not in scope

            prompt = build_prompt(question, options)
            raw = call_ollama(model_name, prompt, 0.0)
            reparsed = parse_letter(raw)

            rows.append(
                {
                    "item_id": item_id,
                    "persona_id": item["persona_id"],
                    "canonical_type": to_canonical(q_row["question_type"]),
                    "invalid_model": key,
                    "gold": gold,
                    "raw_output": raw,
                    "original_pred_key": None,
                    "diagnostic_reparsed_pred_key": reparsed,
                    "pred_key_changed_vs_original": reparsed is not None,
                }
            )
            print(f"item_id={item_id} model={key} raw={raw!r} reparsed={reparsed}")

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_PATH, index=False)
    print(f"\nwrote {len(out_df)} diagnostic rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
