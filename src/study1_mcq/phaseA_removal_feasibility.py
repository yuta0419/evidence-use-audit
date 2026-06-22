"""Phase A — Removal Feasibility Proposal Generation.

Generates candidate removal/placebo intervention packs for human
adjudication. This is proposal generation only — no behavioral evaluation
(no llama/qwen runs) happens here, and GPT-4o mini output is never treated
as final. Final inclusion is decided by human adjudication
(`phaseA_human_adjudication_sheet.csv`); Phase B may not start until that is
done.

Scope and safety:
  - Only the sampled Phase A items (15-20) are ever sent to the OpenAI API.
    The full strict pool (276) and the full dataset (589) are never sent.
  - History text shown to GPT/saved to CSV is always extracted mechanically
    from the dataset's own turns — GPT's own restated span text is never
    trusted as the source of truth, to prevent silently laundering a
    hallucinated span into the removed-history columns.
  - OPENAI_API_KEY is read from the environment (optionally via .env, never
    committed). If absent, this script stops before making any API call.
"""

import ast
import csv
import json
import os
import random
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from src.study1_mcq.canonical_types import to_canonical
from src.study1_mcq.prompting import gold_letter

REPO_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = REPO_ROOT / "data" / "personamem_32k" / "questions_32k.csv"
CONTEXTS_PATH = REPO_ROOT / "data" / "personamem_32k" / "shared_contexts_32k.jsonl"
GATE1_NEW_PATH = REPO_ROOT / "results" / "study1" / "gate1_per_item.csv"
GATE1_OLD_PATH = REPO_ROOT / "results" / "study1" / "archive_v1_truncation_and_article_bug" / "gate1_per_item.csv"

OUT_DIR = REPO_ROOT / "results" / "0621_phaseA_removal_feasibility"
PROPOSALS_PATH = OUT_DIR / "phaseA_proposals.csv"
ADJUDICATION_PATH = OUT_DIR / "phaseA_human_adjudication_sheet.csv"
SUMMARY_PATH = OUT_DIR / "phaseA_summary.json"
PROMPT_PATH = OUT_DIR / "phaseA_prompt.md"
README_PATH = OUT_DIR / "phaseA_README.md"

PRIORITY_TYPES = ["preference_evolution_tracking", "preference_update_reason_recall", "user_shared_fact_recall"]
RECENCY_EXCLUDED_TYPES = ["latest_preference_acknowledgement"]
SAMPLE_SIZE = 18
SEED = 621

GPT_MODEL = "gpt-4o-mini"
PROMPT_VERSION = "phaseA_v1_0621"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

ALLOWED_LABELS = {"localizable", "localization-failed", "leakage-risk", "placebo-unavailable", "uninterpretable"}

SYSTEM_PROMPT = """You are assisting a research pipeline that audits whether benchmark correctness reflects genuine use of conversational evidence. Your job is ONLY to propose candidate spans for human review. You are not the final authority; a human will check every proposal before it is used.

Rules you must follow strictly:
- Select spans only from the provided history. Do not fabricate, paraphrase, or rewrite any history content.
- Do not create counterfactual or edited versions of the history.
- Do not mask or alter text in your proposed spans; quote it verbatim from the provided history.
- If no clean, localizable span supports the gold answer, do not force one — set gold_span_turn_ids to an empty list and explain why in exclusion_reason, and set feasibility_label to "localization-failed".
- A placebo span must not mention the tested target, must have no obvious lexical overlap with the gold evidence, and must not support any answer option. If no valid placebo span exists, set placebo_span_turn_ids to an empty list and explain why in placebo_selection_reason.
- If the gold answer looks supported by information outside the provided history (e.g. by world knowledge or by the options themselves) rather than by a specific localizable span, set feasibility_label to "leakage-risk".
- Use ONLY these feasibility_label values: "localizable", "localization-failed", "leakage-risk", "placebo-unavailable", "uninterpretable". Never invent a new label.
- Return your answer as a single JSON object matching the schema given, with no extra commentary, no markdown fencing.
"""

USER_PROMPT_TEMPLATE = """## Item
Question: {question}

Options:
{options_text}

Gold answer: ({gold_letter}) {gold_text}

## Full history available to the model when this question was asked (numbered turns)
{history_text}

## Task
1. Identify the target being tested (the specific preference/fact/reason the question is probing).
2. Propose a gold evidence span: the minimal set of turn indices (integers from the numbered history above) that support the gold answer. Quote the span text verbatim from those turns.
3. Propose a placebo span: turn indices of comparable size to the gold span (same number of turns if possible, otherwise similar total character length) that do NOT mention the target, have no lexical overlap with the gold evidence, and do not support any option.
4. Assign feasibility_label using only: "localizable", "localization-failed", "leakage-risk", "placebo-unavailable", "uninterpretable".

Return exactly this JSON shape and nothing else:
{{
  "target_description": "...",
  "gold_span_turn_ids": [0],
  "gold_span_text": "...",
  "gold_span_rationale": "...",
  "placebo_span_turn_ids": [0],
  "placebo_span_text": "...",
  "placebo_selection_reason": "...",
  "feasibility_label": "...",
  "exclusion_reason": "...",
  "notes": "..."
}}
"""


def load_contexts() -> dict:
    contexts = {}
    with open(CONTEXTS_PATH) as f:
        for line in f:
            contexts.update(json.loads(line))
    return contexts


def history_turns(contexts: dict, shared_context_id: str, end_index: int) -> list[tuple[int, dict]]:
    full = contexts[shared_context_id]
    return [(i, full[i]) for i in range(min(end_index + 1, len(full)))]


def format_history(turns: list[tuple[int, dict]]) -> str:
    return "\n".join(f"[{idx}] {turn['role']}: {turn['content']}" for idx, turn in turns)


def remove_turn_ids(turns: list[tuple[int, dict]], turn_ids: set[int]) -> str:
    kept = [(idx, turn) for idx, turn in turns if idx not in turn_ids]
    return format_history(kept)


def build_candidate_pool() -> tuple[pd.DataFrame, dict]:
    new_run = pd.read_csv(GATE1_NEW_PATH)
    old_run = pd.read_csv(GATE1_OLD_PATH)

    new_strict = new_run[new_run["item_default_bucket"] == "strict_default_error"].copy()

    recency_excluded = new_strict[new_strict["question_type"].isin(RECENCY_EXCLUDED_TYPES)]
    priority_pool = new_strict[new_strict["question_type"].isin(PRIORITY_TYPES)].copy()

    rng = random.Random(SEED)
    pool_ids = sorted(priority_pool["item_id"].tolist())  # deterministic order before sampling
    sampled_ids = rng.sample(pool_ids, k=min(SAMPLE_SIZE, len(pool_ids)))
    sampled = priority_pool[priority_pool["item_id"].isin(sampled_ids)].copy()

    old_bucket_by_id = old_run.set_index("item_id")["item_default_bucket"].to_dict()
    sampled["strict_bucket_old_run"] = sampled["item_id"].map(old_bucket_by_id)
    sampled["strict_bucket_new_run"] = sampled["item_default_bucket"]

    meta = {
        "priority_pool_size": len(priority_pool),
        "priority_pool_by_type": priority_pool["question_type"].value_counts().to_dict(),
        "recency_excluded_count": len(recency_excluded),
        "recency_excluded_ids": recency_excluded["item_id"].tolist(),
        "recency_excluded_reason": (
            "latest_preference_acknowledgement items are confounded by update/recency and are "
            "treated as exclusion candidates at Phase A, not sampled into the priority pool."
        ),
        "sampled_ids": sorted(sampled_ids),
    }
    return sampled, meta


def call_gpt4o_mini(prompt_user: str, api_key: str) -> tuple[dict | None, str]:
    resp = requests.post(
        OPENAI_CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": GPT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_user},
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


def _validate_span(turn_ids_raw, turns: list[tuple[int, dict]]) -> tuple[list[int] | None, str | None]:
    if not isinstance(turn_ids_raw, list):
        return None, "turn_ids not a list"
    valid_indices = {idx for idx, _ in turns}
    try:
        ids = [int(x) for x in turn_ids_raw]
    except (TypeError, ValueError):
        return None, "turn_ids not all integers"
    if not ids:
        return [], None
    if not all(i in valid_indices for i in ids):
        return None, "turn_ids out of range of provided history"
    return ids, None


def process_item(q_row: pd.Series, contexts: dict, options: list[str], gold: str, gold_text: str, api_key: str) -> dict:
    turns = history_turns(contexts, q_row["shared_context_id"], int(q_row["end_index_in_shared_context"]))
    history_text = format_history(turns)

    prompt_user = USER_PROMPT_TEMPLATE.format(
        question=q_row["user_question_or_message"],
        options_text="\n".join(options),
        gold_letter=gold,
        gold_text=gold_text,
        history_text=history_text,
    )

    gpt_json, raw_text = call_gpt4o_mini(prompt_user, api_key)

    result = {
        "target_description": "",
        "proposed_gold_span_turn_ids": "",
        "proposed_gold_span_text": "",
        "gold_span_utterance_count": "",
        "gold_span_char_length": "",
        "gold_span_rationale": "",
        "gold_removed_history": "",
        "proposed_placebo_span_turn_ids": "",
        "proposed_placebo_span_text": "",
        "placebo_utterance_count": "",
        "placebo_char_length": "",
        "placebo_selection_reason": "",
        "placebo_removed_history": "",
        "proposal_feasibility_label": "uninterpretable",
        "proposal_exclusion_reason": "",
        "gpt4o_mini_raw_response": raw_text,
        "phaseA_notes": "",
    }

    if gpt_json is None:
        result["proposal_exclusion_reason"] = "GPT response was not valid JSON"
        return result

    label = gpt_json.get("feasibility_label", "")
    if label not in ALLOWED_LABELS:
        result["proposal_exclusion_reason"] = f"GPT returned a label outside the fixed scheme: {label!r}"
        result["phaseA_notes"] = gpt_json.get("notes", "")
        return result
    result["proposal_feasibility_label"] = label
    result["target_description"] = gpt_json.get("target_description", "")
    result["gold_span_rationale"] = gpt_json.get("gold_span_rationale", "")
    result["placebo_selection_reason"] = gpt_json.get("placebo_selection_reason", "")
    result["proposal_exclusion_reason"] = gpt_json.get("exclusion_reason", "")
    result["phaseA_notes"] = gpt_json.get("notes", "")

    gold_ids, gold_err = _validate_span(gpt_json.get("gold_span_turn_ids", []), turns)
    if gold_err:
        result["phaseA_notes"] = (result["phaseA_notes"] + f" | gold span invalid: {gold_err}").strip(" |")
    elif gold_ids:
        gold_turns = [(i, t) for i, t in turns if i in set(gold_ids)]
        gold_span_text = format_history(gold_turns)
        result["proposed_gold_span_turn_ids"] = json.dumps(gold_ids)
        result["proposed_gold_span_text"] = gold_span_text
        result["gold_span_utterance_count"] = len(gold_ids)
        result["gold_span_char_length"] = len(gold_span_text)
        result["gold_removed_history"] = remove_turn_ids(turns, set(gold_ids))

    placebo_ids, placebo_err = _validate_span(gpt_json.get("placebo_span_turn_ids", []), turns)
    if placebo_err:
        result["phaseA_notes"] = (result["phaseA_notes"] + f" | placebo span invalid: {placebo_err}").strip(" |")
    elif placebo_ids:
        placebo_turns = [(i, t) for i, t in turns if i in set(placebo_ids)]
        placebo_span_text = format_history(placebo_turns)
        result["proposed_placebo_span_turn_ids"] = json.dumps(placebo_ids)
        result["proposed_placebo_span_text"] = placebo_span_text
        result["placebo_utterance_count"] = len(placebo_ids)
        result["placebo_char_length"] = len(placebo_span_text)
        result["placebo_removed_history"] = remove_turn_ids(turns, set(placebo_ids))
    elif placebo_ids == [] and not placebo_err:
        result["proposal_feasibility_label"] = (
            "placebo-unavailable" if result["proposal_feasibility_label"] == "localizable" else result["proposal_feasibility_label"]
        )

    return result


PROPOSAL_COLUMNS = [
    "item_id", "persona_id", "canonical_type", "question", "options", "gold_letter", "gold_answer_text",
    "strict_bucket_old_run", "strict_bucket_new_run",
    "target_description",
    "proposed_gold_span_turn_ids", "proposed_gold_span_text", "gold_span_utterance_count",
    "gold_span_char_length", "gold_span_rationale", "gold_removed_history",
    "proposed_placebo_span_turn_ids", "proposed_placebo_span_text", "placebo_utterance_count",
    "placebo_char_length", "placebo_selection_reason", "placebo_removed_history",
    "proposal_feasibility_label", "proposal_exclusion_reason", "gpt4o_mini_raw_response", "phaseA_notes",
]

HUMAN_COLUMNS = [
    "human_target_determinate", "human_gold_span_correct", "human_gold_span_sufficient",
    "human_gold_span_minimal", "human_placebo_neutral", "human_placebo_comparable_length",
    "human_placebo_valid", "human_remove_operation_valid", "human_final_include",
    "human_exclusion_reason", "human_notes",
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")

    sampled, pool_meta = build_candidate_pool()
    questions = pd.read_csv(QUESTIONS_PATH).set_index("question_id")
    contexts = load_contexts() if api_key else {}

    rows = []
    sent_item_ids = []
    skipped_missing_key = False

    for _, srow in sampled.iterrows():
        q_row = questions.loc[srow["item_id"]]
        options = ast.literal_eval(q_row["all_options"])
        gold = gold_letter(q_row["correct_answer"])
        gold_text = next(o for o in options if o.strip().lower().startswith(f"({gold})"))
        canonical_type = to_canonical(q_row["question_type"])

        base = {
            "item_id": srow["item_id"],
            "persona_id": srow["persona_id"],
            "canonical_type": canonical_type,
            "question": q_row["user_question_or_message"],
            "options": json.dumps(options, ensure_ascii=False),
            "gold_letter": gold,
            "gold_answer_text": gold_text,
            "strict_bucket_old_run": srow["strict_bucket_old_run"],
            "strict_bucket_new_run": srow["strict_bucket_new_run"],
        }

        if not api_key:
            skipped_missing_key = True
            empty = {col: "" for col in PROPOSAL_COLUMNS if col not in base}
            empty["proposal_exclusion_reason"] = "SKIPPED: OPENAI_API_KEY not set; no API call made"
            empty["phaseA_notes"] = "Phase A stopped before GPT-4o mini call (API key missing). See phaseA_summary.json."
            rows.append({**base, **empty})
            continue

        sent_item_ids.append(srow["item_id"])
        proposal = process_item(q_row, contexts, options, gold, gold_text, api_key)
        rows.append({**base, **proposal})

    proposals_df = pd.DataFrame(rows, columns=PROPOSAL_COLUMNS)
    proposals_df.to_csv(PROPOSALS_PATH, index=False, quoting=csv.QUOTE_ALL)

    adjudication_df = proposals_df.copy()
    for col in HUMAN_COLUMNS:
        adjudication_df[col] = ""
    adjudication_df.to_csv(ADJUDICATION_PATH, index=False, quoting=csv.QUOTE_ALL)

    summary = {
        "number_of_input_items": int(pool_meta["priority_pool_size"]),
        "number_of_proposal_rows_generated": len(proposals_df),
        "number_with_proposed_gold_span": int((proposals_df["proposed_gold_span_turn_ids"] != "").sum()),
        "number_with_proposed_placebo_span": int((proposals_df["proposed_placebo_span_turn_ids"] != "").sum()),
        "number_marked_placebo_unavailable": int((proposals_df["proposal_feasibility_label"] == "placebo-unavailable").sum()),
        "number_with_missing_history": 0,
        "number_requiring_scheme_definition": 0,
        "sampled_item_ids": pool_meta["sampled_ids"],
        "sent_item_ids": sent_item_ids,
        "gpt_model_used": GPT_MODEL if api_key else None,
        "prompt_version": PROMPT_VERSION,
        "date": str(date.today()),
        "random_seed": SEED,
        "api_key_source": "environment variable OPENAI_API_KEY (optionally loaded from local .env via python-dotenv)",
        "external_send_count": len(sent_item_ids),
        "api_key_missing": skipped_missing_key,
        "priority_pool_by_canonical_type": pool_meta["priority_pool_by_type"],
        "recency_excluded_count": pool_meta["recency_excluded_count"],
        "recency_excluded_ids": pool_meta["recency_excluded_ids"],
        "recency_excluded_reason": pool_meta["recency_excluded_reason"],
        "strict_pool_source": {
            "new_run": str(GATE1_NEW_PATH.relative_to(REPO_ROOT)),
            "old_run": str(GATE1_OLD_PATH.relative_to(REPO_ROOT)),
            "used_for_sampling": "new_run (corrected, num_predict=256, 3-tier parser) — see docs/QC_notes_gate1_rerun_0622.md",
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str))

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
