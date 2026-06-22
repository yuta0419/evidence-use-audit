"""Structural validation for the PersonaMem-v1 32k split.

No row count is assumed; every check reports the actual count and a
pass/fail verdict against the full population of rows present in the file.
"""

import ast
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "personamem_32k"
QUESTIONS_PATH = DATA_DIR / "questions_32k.csv"
CONTEXTS_PATH = DATA_DIR / "shared_contexts_32k.jsonl"


@dataclass
class CheckResult:
    name: str
    total: int
    failures: int

    @property
    def passed(self) -> bool:
        return self.failures == 0

    def __str__(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        return f"[{verdict}] {self.name}: {self.failures}/{self.total} failed"


def load_questions() -> pd.DataFrame:
    return pd.read_csv(QUESTIONS_PATH)


def load_context_ids() -> set[str]:
    ids: set[str] = set()
    with open(CONTEXTS_PATH) as f:
        for line in f:
            ids.update(json.loads(line).keys())
    return ids


def parse_options(raw: str) -> list[str]:
    return ast.literal_eval(raw)


def check_option_structure(df: pd.DataFrame) -> CheckResult:
    failures = 0
    for raw in df["all_options"]:
        try:
            opts = parse_options(raw)
            if not isinstance(opts, list) or len(opts) == 0:
                failures += 1
        except Exception:
            failures += 1
    return CheckResult("option structure parseable", len(df), failures)


def check_gold_resolvable(df: pd.DataFrame) -> CheckResult:
    failures = 0
    for raw, gold in zip(df["all_options"], df["correct_answer"]):
        try:
            opts = parse_options(raw)
            gold_letter = str(gold).strip().lower()
            matches = [o for o in opts if o.strip().lower().startswith(gold_letter)]
            if len(matches) != 1:
                failures += 1
        except Exception:
            failures += 1
    return CheckResult("gold letter uniquely resolvable to option text", len(df), failures)


def check_nongold_extractable(df: pd.DataFrame) -> CheckResult:
    failures = 0
    for raw, gold in zip(df["all_options"], df["correct_answer"]):
        try:
            opts = parse_options(raw)
            gold_letter = str(gold).strip().lower()
            nongold = [o for o in opts if not o.strip().lower().startswith(gold_letter)]
            if len(nongold) != len(opts) - 1:
                failures += 1
        except Exception:
            failures += 1
    return CheckResult("non-gold options extractable", len(df), failures)


def check_context_link(df: pd.DataFrame, context_ids: set[str]) -> CheckResult:
    failures = int((~df["shared_context_id"].isin(context_ids)).sum())
    return CheckResult("shared_context_id resolves into shared_contexts file", len(df), failures)


def check_context_boundary(df: pd.DataFrame) -> CheckResult:
    failures = int(df["end_index_in_shared_context"].isna().sum())
    return CheckResult("end_index_in_shared_context present", len(df), failures)


def main() -> None:
    df = load_questions()
    context_ids = load_context_ids()

    print(f"row count: {len(df)}")
    print(f"distinct persona_id: {df['persona_id'].nunique()}")
    print(f"distinct shared_context_id: {df['shared_context_id'].nunique()}")
    print(f"distinct question_type: {df['question_type'].nunique()}")

    results = [
        check_option_structure(df),
        check_gold_resolvable(df),
        check_nongold_extractable(df),
        check_context_link(df, context_ids),
        check_context_boundary(df),
    ]
    for r in results:
        print(r)

    if all(r.passed for r in results):
        print("overall: PASS")
    else:
        print("overall: FAIL")


if __name__ == "__main__":
    main()
