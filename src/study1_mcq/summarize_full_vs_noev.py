"""Phase 4 aggregation for matched-scaffold C_full vs C_noev runs.

Reports λ, Δλ by type, persona cluster-bootstrap CI (descriptive),
type-level 2×2 cell counts (no item-level claims with single seed),
and 3-model descriptive baseline for matched C_noev.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
GPT4O_BASE = REPO_ROOT / "results" / "full_vs_noev_gpt4omini_32k"
OUT_MD = REPO_ROOT / "docs" / "results_summary_full_vs_noev_gpt4omini_0623.md"
OUT_JSON = REPO_ROOT / "results" / "full_vs_noev_gpt4omini_32k" / "phase4_summary.json"

CHANCE = 0.25
LAMBDA_DENOM = 0.75
N_BOOT = 2000
BOOT_SEED = 623


def load_records(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return pd.DataFrame(rows)


def acc_lambda(correct: int, n: int) -> float:
    if n == 0:
        return float("nan")
    return (correct / n - CHANCE) / LAMBDA_DENOM


def summarize_condition(df: pd.DataFrame) -> dict:
    n_all = len(df)
    parseable = df[df["parse_status_majority"] == "valid"]
    n_parse = len(parseable)
    correct_all = int(df["majority_is_gold"].sum())
    correct_parse = int(parseable["majority_is_gold"].sum())
    return {
        "n_all": n_all,
        "n_parseable_majority": n_parse,
        "correct_all": correct_all,
        "correct_parseable": correct_parse,
        "acc_all": correct_all / n_all if n_all else float("nan"),
        "acc_parseable": correct_parse / n_parse if n_parse else float("nan"),
        "lambda_all": acc_lambda(correct_all, n_all),
        "lambda_parseable": acc_lambda(correct_parse, n_parse),
    }


def by_type(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for qtype, g in df.groupby("question_type"):
        s = summarize_condition(g)
        rows.append({"question_type": qtype, **s})
    return pd.DataFrame(rows)


def merge_delta(full_df: pd.DataFrame, noev_df: pd.DataFrame) -> pd.DataFrame:
    full_t = by_type(full_df).rename(
        columns={
            c: f"full_{c}"
            for c in by_type(full_df).columns
            if c != "question_type"
        }
    )
    noev_t = by_type(noev_df).rename(
        columns={
            c: f"noev_{c}"
            for c in by_type(noev_df).columns
            if c != "question_type"
        }
    )
    merged = full_t.merge(noev_t, on="question_type")
    merged["delta_lambda_all"] = merged["full_lambda_all"] - merged["noev_lambda_all"]
    merged["delta_lambda_parseable"] = merged["full_lambda_parseable"] - merged["noev_lambda_parseable"]
    merged["n"] = merged["full_n_all"]
    return merged


def two_by_two_by_type(full_df: pd.DataFrame, noev_df: pd.DataFrame) -> pd.DataFrame:
    """Type-level aggregate 2×2 counts. Single-seed: no item-level membership claims."""
    merged = full_df.merge(
        noev_df[["item_id", "majority_is_gold", "parse_status_majority"]],
        on="item_id",
        suffixes=("_full", "_noev"),
    )
    rows = []
    for qtype, g in merged.groupby("question_type"):
        both = int(((g["majority_is_gold_full"]) & (g["majority_is_gold_noev"])).sum())
        noev_only = int((g["majority_is_gold_noev"] & ~g["majority_is_gold_full"]).sum())
        full_only = int((g["majority_is_gold_full"] & ~g["majority_is_gold_noev"]).sum())
        neither = int((~g["majority_is_gold_full"] & ~g["majority_is_gold_noev"]).sum())
        n = len(g)
        rows.append(
            {
                "question_type": qtype,
                "n": n,
                "both_correct": both,
                "noev_only": noev_only,
                "full_only": full_only,
                "neither": neither,
            }
        )
    return pd.DataFrame(rows)


def cluster_bootstrap_delta(full_df: pd.DataFrame, noev_df: pd.DataFrame) -> dict:
    merged = full_df.merge(noev_df[["item_id", "majority_is_gold"]], on="item_id", suffixes=("_full", "_noev"))
    rng = np.random.default_rng(BOOT_SEED)
    persona_ids = merged["persona_id"].unique()
    deltas = []
    for _ in range(N_BOOT):
        sampled = rng.choice(persona_ids, size=len(persona_ids), replace=True)
        boot = pd.concat([merged[merged["persona_id"] == pid] for pid in sampled], ignore_index=True)
        lf = acc_lambda(int(boot["majority_is_gold_full"].sum()), len(boot))
        ln = acc_lambda(int(boot["majority_is_gold_noev"].sum()), len(boot))
        deltas.append(lf - ln)
    arr = np.array(deltas)
    return {
        "n_clusters": int(len(persona_ids)),
        "n_bootstrap": N_BOOT,
        "delta_lambda_point": float(acc_lambda(int(merged["majority_is_gold_full"].sum()), len(merged)) - acc_lambda(int(merged["majority_is_gold_noev"].sum()), len(merged))),
        "delta_lambda_ci_2.5": float(np.percentile(arr, 2.5)),
        "delta_lambda_ci_97.5": float(np.percentile(arr, 97.5)),
        "note": "descriptive cluster bootstrap over persona_id; not inferential.",
    }


def load_matched_noev_baseline(model_slug: str) -> dict | None:
    path = REPO_ROOT / "results" / f"full_vs_noev_matched_{model_slug}_32k" / "noev" / "per_item.jsonl"
    if not path.exists():
        return None
    df = load_records(path)
    s = summarize_condition(df)
    return {"model": model_slug, **s}


def write_markdown(summary: dict, type_table: pd.DataFrame, two_by_two: pd.DataFrame) -> None:
    lines = [
        "# Matched-scaffold C_full vs C_noev — gpt-4o-mini (0623)",
        "",
        "## Headline (within-model Δλ, gpt-4o-mini-2024-07-18)",
        "",
        f"- λ_full (all 589): **{summary['gpt4o']['full']['lambda_all']:.3f}**",
        f"- λ_noev (all 589): **{summary['gpt4o']['noev']['lambda_all']:.3f}**",
        f"- **Δλ = {summary['gpt4o']['delta_lambda_all']:.3f}** (parseable majority: Δλ={summary['gpt4o']['delta_lambda_parseable']:.3f})",
        "",
        "## Descriptive baseline (matched C_noev, 3 models)",
        "",
        "This is **not** a contamination probe. Higher gpt-4o-mini C_noev vs local 8B models",
        "cannot separate memorized-gold contamination from capability/prior alignment.",
        "If gpt-4o-mini C_noev is **not elevated**, we can say there is no sign that",
        "contamination is inflating the contrast; if it **is elevated**, contamination remains",
        "one of several indistinguishable explanations in this design (counterfactual rewrite /",
        "C_optonly would be required to cut it — out of scope).",
        "",
        "Legacy reference bands (protocol-mismatched; do not compare directly):",
        "- Gate1 C_default llama/qwen: 33.4% / 43.6%",
        "- Old 3-shuffle C_noev llama/qwen: 34.5% / 39.2% (external pipeline; not reproduced here)",
        "",
    ]
    baselines = summary.get("matched_noev_baselines", [])
    if baselines:
        lines.append("| model | acc (all) | λ (all) | acc (parseable) |")
        lines.append("|---|---:|---:|---:|")
        for b in baselines:
            lines.append(
                f"| {b['model']} | {b['acc_all']:.1%} | {b['lambda_all']:.3f} | {b['acc_parseable']:.1%} |"
            )
    else:
        lines.append("_Local matched C_noev baselines not yet run._")

    lines.extend(
        [
            "",
            "## Type-level Δλ",
            "",
            type_table.to_markdown(index=False),
            "",
            "## 2×2 (type-level aggregate counts only)",
            "",
            "Single OpenAI seed; cells are **counts**, not item-level membership claims.",
            "Joint 'both correct' baseline is not 25% (conditions are correlated).",
            "",
            two_by_two.to_markdown(index=False),
            "",
            "## Interpretation guards",
            "",
            "- gpt-4o-mini fits 32k history; long-context failure confound is reduced vs 8B,",
            "  but capability vs contamination is not separable in this design.",
            "- Δλ>0 does not prove 'used history'; it is consistent with easier retrieval of",
            "  memorized gold when history is present.",
            "- Regime A (forced-choice letter); judge gate untouched.",
            "- Mini-experiment scope; not expanding 0623 localization/control audit.",
            "",
        ]
    )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    full_df = load_records(GPT4O_BASE / "full" / "per_item.jsonl")
    noev_df = load_records(GPT4O_BASE / "noev" / "per_item.jsonl")

    full_s = summarize_condition(full_df)
    noev_s = summarize_condition(noev_df)
    type_tbl = merge_delta(full_df, noev_df)
    two_by_two = two_by_two_by_type(full_df, noev_df)
    boot = cluster_bootstrap_delta(full_df, noev_df)

    baselines = []
    for slug in ("llama31_8b", "qwen25_7b"):
        b = load_matched_noev_baseline(slug)
        if b:
            baselines.append(b)

    summary = {
        "gpt4o": {
            "full": full_s,
            "noev": noev_s,
            "delta_lambda_all": full_s["lambda_all"] - noev_s["lambda_all"],
            "delta_lambda_parseable": full_s["lambda_parseable"] - noev_s["lambda_parseable"],
            "cluster_bootstrap_delta_lambda": boot,
        },
        "matched_noev_baselines": baselines,
        "type_table": type_tbl.to_dict(orient="records"),
        "two_by_two_by_type": two_by_two.to_dict(orient="records"),
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(summary, type_tbl, two_by_two)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
