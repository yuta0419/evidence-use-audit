"""Study 2 — lenient judge variant, scored against the existing human ground truth.

This does NOT redraw the 30-item sample or redo determinacy filtering — it
reuses the frozen `results/0623_study2_judge_gate/judge_gate_sample.csv`
(seed=619) exactly as-is, so the lenient judge is evaluated on the identical
items/controls as the strict judge (`src/study2_open/judge_gate.py`).

It also does NOT collect a fresh blank human sheet. The human ground truth
recorded in `judge_gate_human_sheet.csv` (human_positive_is_correct /
human_negative_is_correct) answers "is this response actually correct given
the evidence shown" — a fact about the response and the evidence, not about
any particular judge prompt. That makes it a valid reference for scoring ANY
judge configuration against, including this lenient one, without re-asking a
human to re-label the same 30 items from scratch.

Produces:
  1. judge_prompt_v2_lenient.md   — the exact, version-pinned lenient prompt.
  2. judge_verdicts_lenient.csv   — per (item x control) lenient judge verdict.

Run src/study2_open/judge_gate_assessment.py afterward to score these verdicts
against the human ground truth (overall + per-type agreement/FP/FN, directly
comparable to the strict judge's scoring — both go through the same scoring
function so the FP/FN definition can't silently drift between the two).

API key handling mirrors judge_gate.py (CLAUDE.md #13).
"""

import csv
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "results" / "0623_study2_judge_gate"
SAMPLE_PATH = OUT_DIR / "judge_gate_sample.csv"
HUMAN_SHEET_PATH = OUT_DIR / "judge_gate_human_sheet.csv"
VERDICTS_LENIENT_PATH = OUT_DIR / "judge_verdicts_lenient.csv"
PROMPT_LENIENT_PATH = OUT_DIR / "judge_prompt_v2_lenient.md"

JUDGE_MODEL = "gpt-4o-mini"
PROMPT_VERSION = "judge_prompt_v2_lenient"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

JUDGE_SYSTEM_PROMPT = """You are a lenient evaluator judging whether a candidate response to a question is correct, using the provided evidence. Your task is to verify whether the candidate response conveys the evidence-supported answer, allowing for paraphrase, partial specificity, abbreviation, or extra hedging language — but the core fact/value the response asserts must still be the one the evidence actually supports.

Rules you must follow:
- Base your verdict on the provided evidence. Do not use outside/world knowledge to fill gaps the evidence does not cover, and do not guess.
- Mark "correct" if the candidate response conveys the evidence-supported fact/value/preference as its answer, even if phrased differently, abbreviated, or accompanied by extra commentary, as long as it does not state a different or contradictory fact.
- Mark "incorrect" if the candidate response states a different fact/value than the evidence supports, contradicts the evidence, or is a generic/non-committal statement that avoids committing to the evidence-supported answer (e.g. "I don't have that information confirmed" when the evidence does provide it).
- Being more permissive on wording does not mean being permissive on grounding: a fluent, on-topic response that asserts a fact not stated in the evidence must still be marked "incorrect" even under this lenient standard.
- Return your answer as a single JSON object matching the schema given, with no extra commentary, no markdown fencing.
"""

JUDGE_USER_TEMPLATE = """## Question
{question}

## Evidence (verbatim, from the conversation history)
{evidence_text}

## Candidate response to judge
{candidate_response}

## Task
Judge whether the candidate response above is correct under the lenient standard described: does it convey the evidence-supported answer, even if loosely or incompletely phrased, without asserting an unsupported or contradictory fact?

Return exactly this JSON shape and nothing else:
{{
  "verdict": "correct" or "incorrect",
  "rationale": "..."
}}
"""

VERDICT_COLUMNS = [
    "question_id", "question_type", "control_type", "candidate_response",
    "judge_verdict", "judge_rationale", "judge_raw_output",
]


def call_judge(question: str, evidence_text: str, candidate_response: str, api_key: str) -> tuple[dict | None, str]:
    user_prompt = JUDGE_USER_TEMPLATE.format(question=question, evidence_text=evidence_text, candidate_response=candidate_response)
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


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def main() -> None:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set. Stopping before any API call.")

    sample_rows = list(csv.DictReader(open(SAMPLE_PATH)))

    PROMPT_LENIENT_PATH.write_text(
        f"# Judge prompt: {PROMPT_VERSION}\n\n"
        "Lenient variant, scored against the existing human-confirmed ground truth in "
        "judge_gate_human_sheet.csv (not a fresh human re-label). Same 30-item sample, "
        "same 2 controls/item, as judge_prompt_v1 (strict).\n\n"
        "## System prompt\n\n```\n" + JUDGE_SYSTEM_PROMPT + "```\n\n"
        "## User prompt template\n\n```\n" + JUDGE_USER_TEMPLATE + "```\n"
    )

    verdict_rows = []
    for row in sample_rows:
        for control_type, candidate in (("positive", row["positive_control_response"]), ("negative", row["negative_control_response"])):
            if control_type == "negative" and row["negative_control_rule"] == "unavailable":
                verdict_rows.append({"question_id": row["question_id"], "question_type": row["question_type"], "control_type": control_type, "candidate_response": candidate, "judge_verdict": "skipped", "judge_rationale": "", "judge_raw_output": "SKIPPED: negative_control unavailable"})
                continue
            judge_json, raw_text = call_judge(row["question"], row["evidence_text"], candidate, api_key)
            if judge_json is None or judge_json.get("verdict") not in ("correct", "incorrect"):
                verdict_rows.append({"question_id": row["question_id"], "question_type": row["question_type"], "control_type": control_type, "candidate_response": candidate, "judge_verdict": "invalid", "judge_rationale": "", "judge_raw_output": raw_text})
            else:
                verdict_rows.append({"question_id": row["question_id"], "question_type": row["question_type"], "control_type": control_type, "candidate_response": candidate, "judge_verdict": judge_json["verdict"], "judge_rationale": judge_json.get("rationale", ""), "judge_raw_output": raw_text})

    write_csv(VERDICTS_LENIENT_PATH, verdict_rows, VERDICT_COLUMNS)
    print(f"wrote {len(verdict_rows)} verdicts to {VERDICTS_LENIENT_PATH.relative_to(REPO_ROOT)}")
    print("Run src/study2_open/judge_gate_assessment.py to score against human ground truth.")


if __name__ == "__main__":
    main()
