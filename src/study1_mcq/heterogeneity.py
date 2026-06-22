"""Step B: type heterogeneity over Step A's Gate 1 output.

No new model calls. Descriptive only — no inferential statistics
(CLAUDE.md #7), no causal language (CLAUDE.md #8).
"""

from pathlib import Path

import numpy as np
import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "study1"
PER_ITEM_PATH = RESULTS_DIR / "gate1_per_item.csv"

SMALL_N_THRESHOLD = 30
CELL_MIN_N = 3
MIN_QUALIFYING_CELLS = 2

BUCKETS = ("strict_default_error", "loose_default_error", "default_solved", "t0_parse_invalid")


def load_per_item() -> pd.DataFrame:
    df = pd.read_csv(PER_ITEM_PATH)
    df["unstable_any"] = df["unstable_any"].map({"True": True, "False": False, True: True, False: False})
    return df


def table_a(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for qtype, g in df.groupby("question_type"):
        n = len(g)
        rows.append(
            {
                "question_type": qtype,
                "n": n,
                "strict_pct": 100 * (g["item_default_bucket"] == "strict_default_error").mean(),
                "loose_pct": 100 * (g["item_default_bucket"] == "loose_default_error").mean(),
                "solved_pct": 100 * (g["item_default_bucket"] == "default_solved").mean(),
                "small_n": n < SMALL_N_THRESHOLD,
            }
        )
    table = pd.DataFrame(rows).sort_values("strict_pct", ascending=False).reset_index(drop=True)

    n_all = len(df)
    all_row = {
        "question_type": "ALL",
        "n": n_all,
        "strict_pct": 100 * (df["item_default_bucket"] == "strict_default_error").mean(),
        "loose_pct": 100 * (df["item_default_bucket"] == "loose_default_error").mean(),
        "solved_pct": 100 * (df["item_default_bucket"] == "default_solved").mean(),
        "small_n": False,
    }
    table = pd.concat([table, pd.DataFrame([all_row])], ignore_index=True)
    return table


def table_b(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for qtype, g_type in df.groupby("question_type"):
        cell_stats = []
        n_personas_present = g_type["persona_id"].nunique()
        for persona_id, g_cell in g_type.groupby("persona_id"):
            n_cell = len(g_cell)
            if n_cell >= CELL_MIN_N:
                pct_strict = 100 * (g_cell["item_default_bucket"] == "strict_default_error").mean()
                cell_stats.append(pct_strict)

        n_cells = len(cell_stats)
        if n_cells >= MIN_QUALIFYING_CELLS:
            pct_strict_range = max(cell_stats) - min(cell_stats)
            pct_strict_sd = float(np.std(cell_stats, ddof=1))
        else:
            pct_strict_range = "insufficient"
            pct_strict_sd = "insufficient"

        rows.append(
            {
                "question_type": qtype,
                "n_personas_present": n_personas_present,
                "n_cells_item_ge_3": n_cells,
                "pct_strict_range": pct_strict_range,
                "pct_strict_sd": pct_strict_sd,
            }
        )
    return pd.DataFrame(rows)


def table_c(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for bucket in BUCKETS:
        g = df[df["item_default_bucket"] == bucket]
        eligible = g["unstable_any"].notna()
        n_eligible = int(eligible.sum())
        n_unstable = int((g.loc[eligible, "unstable_any"] == True).sum())  # noqa: E712
        rows.append(
            {
                "item_default_bucket": bucket,
                "n_items": len(g),
                "n_eligible_for_stability_check": n_eligible,
                "n_unstable": n_unstable,
                "unstable_pct_among_eligible": (100 * n_unstable / n_eligible) if n_eligible > 0 else None,
            }
        )
    table = pd.DataFrame(rows)
    table.attrs["note"] = "unstable_any is a separate attribute, independent of the primary bucket definition (CLAUDE.md #4-#6 buckets are unaffected)."
    return table


def marginal_sd_comparison(df: pd.DataFrame, table_a_df: pd.DataFrame) -> dict:
    type_strict_pcts = table_a_df.loc[table_a_df["question_type"] != "ALL", "strict_pct"].to_numpy()
    type_sd = float(np.std(type_strict_pcts, ddof=1))

    persona_strict_pcts = []
    for _, g in df.groupby("persona_id"):
        persona_strict_pcts.append(100 * (g["item_default_bucket"] == "strict_default_error").mean())
    persona_sd = float(np.std(persona_strict_pcts, ddof=1))

    return {
        "type_marginal_strict_pct_sd": type_sd,
        "type_marginal_k": len(type_strict_pcts),
        "persona_marginal_strict_pct_sd": persona_sd,
        "persona_marginal_k": len(persona_strict_pcts),
        "note": "descriptive only, no inferential statistics, no causal interpretation.",
    }


def main() -> None:
    df = load_per_item()

    ta = table_a(df)
    tb = table_b(df)
    tc = table_c(df)
    marginal = marginal_sd_comparison(df, ta)

    ta.to_csv(RESULTS_DIR / "table_A.csv", index=False)
    tb.to_csv(RESULTS_DIR / "table_B.csv", index=False)
    tc.to_csv(RESULTS_DIR / "table_C.csv", index=False)

    print("=== Table A: type-level bucket rates ===")
    print(ta.to_string(index=False))
    print("\n=== Table B: type x persona strict% dispersion (cells with n>=3 only) ===")
    print(tb.to_string(index=False))
    print("\n=== Table C: stability by bucket ===")
    print(tc.to_string(index=False))
    print("\n=== type-marginal vs persona-marginal strict% sd (descriptive only) ===")
    print(marginal)


if __name__ == "__main__":
    main()
