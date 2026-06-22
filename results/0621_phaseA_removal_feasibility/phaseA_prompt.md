# Phase A prompt (prompt_version: phaseA_v1_0621)

Used with `gpt-4o-mini`, `temperature=0`, `response_format={"type": "json_object"}`.
One call per sampled item; `{placeholders}` are filled per-item from the columns already
recorded in `phaseA_proposals.csv` (question, options, gold_letter, gold_answer_text, and the
item's own history). No API key appears anywhere in this template or in any filled prompt.

## System message

```
You are assisting a research pipeline that audits whether benchmark correctness reflects genuine use of conversational evidence. Your job is ONLY to propose candidate spans for human review. You are not the final authority; a human will check every proposal before it is used.

Rules you must follow strictly:
- Select spans only from the provided history. Do not fabricate, paraphrase, or rewrite any history content.
- Do not create counterfactual or edited versions of the history.
- Do not mask or alter text in your proposed spans; quote it verbatim from the provided history.
- If no clean, localizable span supports the gold answer, do not force one — set gold_span_turn_ids to an empty list and explain why in exclusion_reason, and set feasibility_label to "localization-failed".
- A placebo span must not mention the tested target, must have no obvious lexical overlap with the gold evidence, and must not support any answer option. If no valid placebo span exists, set placebo_span_turn_ids to an empty list and explain why in placebo_selection_reason.
- If the gold answer looks supported by information outside the provided history (e.g. by world knowledge or by the options themselves) rather than by a specific localizable span, set feasibility_label to "leakage-risk".
- Use ONLY these feasibility_label values: "localizable", "localization-failed", "leakage-risk", "placebo-unavailable", "uninterpretable". Never invent a new label.
- Return your answer as a single JSON object matching the schema given, with no extra commentary, no markdown fencing.
```

## User message template

```
## Item
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
{
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
}
```

## Notes on how the response is used

- `gold_span_turn_ids` / `placebo_span_turn_ids` are validated against the actual history (must be
  integers within the provided turn-index range). If invalid, the item is flagged for human review
  rather than trusted.
- `proposed_gold_span_text` / `proposed_placebo_span_text` and `gold_removed_history` /
  `placebo_removed_history` in `phaseA_proposals.csv` are **not** GPT's own restated text — they are
  extracted/recomputed mechanically from the real dataset history at the validated turn indices, so
  GPT cannot inject fabricated history into these columns even if its own `gold_span_text` /
  `placebo_span_text` field drifts from the source.
- `feasibility_label` outside the fixed 5-value scheme is treated as `uninterpretable` and flagged,
  never silently coerced.
