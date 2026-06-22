"""Step C: M3 (gemma2:27b) external validation on the frozen strict pool.

CLAUDE.md #4, #5: M3 is never folded into the strict definition (no
strict_3), and the strict pool from Step A is frozen before this script
runs. M3 is queried only on that frozen pool, at temp=0, reusing Step A's
prompt/parser (src/study1_mcq/prompting.py) — no new prompt logic.
"""

import ast
import csv
import json
from pathlib import Path

import pandas as pd

from src.study1_mcq.prompting import gold_letter, query

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "study1"
GATE1_PER_ITEM_PATH = RESULTS_DIR / "gate1_per_item.csv"
QUESTIONS_PATH = Path(__file__).resolve().parents[2] / "data" / "personamem_32k" / "questions_32k.csv"

STRICT_POOL_PATH = RESULTS_DIR / "strict_pool.csv"
M3_OUTPUT_PATH = RESULTS_DIR / "m3_on_strict.csv"
M3_SUMMARY_PATH = RESULTS_DIR / "m3_summary.json"

M3_MODEL = "gemma2:27b"
SMALL_N_THRESHOLD = 30
NUM_PREDICT = 256  # 2026-06-22: matches gate1.py's NUM_PREDICT for consistency


def freeze_strict_pool() -> pd.DataFrame:
    """Extract strict_default_error items from Step A output and freeze them.

    If strict_pool.csv already exists, it is treated as the frozen
    population and is not regenerated from a re-run of Step A.
    """
    if STRICT_POOL_PATH.exists():
        print(f"strict pool already frozen at {STRICT_POOL_PATH}, using existing file")
        return pd.read_csv(STRICT_POOL_PATH)

    gate1 = pd.read_csv(GATE1_PER_ITEM_PATH)
    strict = gate1[gate1["item_default_bucket"] == "strict_default_error"].copy()
    strict.to_csv(STRICT_POOL_PATH, index=False)
    print(f"froze strict pool: {len(strict)} items -> {STRICT_POOL_PATH}")
    return strict


def load_done_item_ids() -> set[str]:
    if not M3_OUTPUT_PATH.exists():
        return set()
    existing = pd.read_csv(M3_OUTPUT_PATH)
    return set(existing["item_id"].astype(str))


def run_m3_on_strict_pool(strict_pool: pd.DataFrame) -> None:
    questions = pd.read_csv(QUESTIONS_PATH).set_index("question_id")

    done_ids = load_done_item_ids()
    write_header = not M3_OUTPUT_PATH.exists()
    f = open(M3_OUTPUT_PATH, "a", newline="", encoding="utf-8")
    writer = csv.writer(f)
    if write_header:
        writer.writerow(["item_id", "canonical_type", "persona_id", "m3_pred", "m3_raw", "m3_solved", "parse_status"])

    total = len(strict_pool)
    for i, strict_row in enumerate(strict_pool.itertuples()):
        item_id = str(strict_row.item_id)
        if item_id in done_ids:
            continue

        q_row = questions.loc[strict_row.item_id]
        options = ast.literal_eval(q_row["all_options"])
        gold = gold_letter(q_row["correct_answer"])

        resp = query(M3_MODEL, q_row["user_question_or_message"], options, 0.0, num_predict=NUM_PREDICT)
        parse_status = "valid" if resp.pred_letter is not None else "invalid"
        m3_solved = resp.pred_letter == gold if resp.pred_letter is not None else False

        writer.writerow(
            [item_id, strict_row.question_type, strict_row.persona_id, resp.pred_letter or "", resp.raw_response, m3_solved, parse_status]
        )
        f.flush()

        if (i + 1) % 25 == 0 or (i + 1) == total:
            print(f"  processed {i + 1}/{total}")

    f.close()


def summarize() -> None:
    df = pd.read_csv(M3_OUTPUT_PATH)
    n = len(df)
    n_solved = int((df["m3_solved"] == True).sum())  # noqa: E712
    n_invalid = int((df["parse_status"] == "invalid").sum())

    type_breakdown = []
    for qtype, g in df.groupby("canonical_type"):
        n_type = len(g)
        type_breakdown.append(
            {
                "canonical_type": qtype,
                "n": n_type,
                "m3_solve_rate": (g["m3_solved"] == True).mean(),  # noqa: E712
                "small_n": n_type < SMALL_N_THRESHOLD,
            }
        )

    summary = {
        "n_strict_pool": n,
        "m3_solve_rate_on_strict": n_solved / n if n > 0 else None,
        "n_solved": n_solved,
        "n_parse_invalid": n_invalid,
        "by_canonical_type": type_breakdown,
        "reading": (
            "descriptive only; low m3_solve_rate -> strict pool persists with a different, "
            "stronger model lineage (residual); high m3_solve_rate -> default-solvability "
            "is confounded with capability for that slice. Neither claim generalizes to "
            "'strong models in general' (single M3 model), and neither implies strict items "
            "require evidence (CLAUDE.md #8)."
        ),
    }
    M3_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    pool = freeze_strict_pool()
    run_m3_on_strict_pool(pool)
    summarize()
