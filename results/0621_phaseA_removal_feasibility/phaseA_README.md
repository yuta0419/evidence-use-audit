# Phase A — Removal Feasibility Proposal Generation

## Purpose

Phase A prepares candidate removal/placebo intervention packs for **human adjudication**.
It does not run behavioral evaluation (no llama/qwen runs) and does not produce a final
6-class sensitivity label. It corresponds to the preparation step for L3 (evidence
contingency) in the framework's intervention ladder, instantiated as a removal-only
feasibility gate ahead of any Phase B run.

## Removal-only decision

Phase A implements **removal only**: gold-removal (delete the proposed gold evidence span
from the full history) and placebo-removal (delete a comparable-size, target-irrelevant
span). Masking, paraphrase, counterfactual edits, answer-changing rewrites, and evidence
inversion are explicitly out of scope for this feasibility gate and belong to later studies.

## Placebo selection rule

A placebo span must, as far as the proposal generator (GPT-4o mini) can judge:
- match the gold span's utterance count when possible, or similar character length otherwise
- not mention the target preference/fact/reason being tested
- have no obvious lexical overlap with the gold evidence
- not directly support any answer option
- be removable without breaking the history's structure

If GPT-4o mini cannot identify a valid placebo, the item is marked `placebo-unavailable`
rather than having a placebo manually chosen to look clean. The fixed random seed (621) is
used for: (a) which 18 items are sampled from the priority pool, and (b) any code-side
tie-break — since this is a single LLM call rather than an enumerable search, GPT itself is
instructed to follow the rule deterministically (best single candidate per the stated
constraints) rather than to simulate randomness internally.

## Target item pool

Phase A starts from the **`strict_default_error`** pool of the corrected Gate 1 run
(`results/study1/gate1_per_item.csv`, num_predict=256 + 3-tier parser — see
`docs/QC_notes_gate1_rerun_0622.md`), not the earlier bug-affected run
(`results/study1/archive_v1_truncation_and_article_bug/`). Both bucket values are recorded
per item in `phaseA_proposals.csv` (`strict_bucket_old_run`, `strict_bucket_new_run`) for
traceability — they can differ for individual items because of the num_predict/parser fix.

Reason for starting from `strict_default_error`: items unsolvable without history are the
most meaningful candidates for evidence-dependence testing; items solved under no-history
(L1) are weak targets for L3 contingency.

## Strict-pool sampling rule

1. Restrict to canonical types: `preference_evolution_tracking`,
   `preference_update_reason_recall`, `user_shared_fact_recall` (122 candidate items).
2. `latest_preference_acknowledgement` items (8 found in the strict pool) are treated as
   **exclusion candidates** at Phase A and never enter the priority sample — they are
   confounded by update/recency, per the task's design constraint. Their item IDs are logged
   in `phaseA_summary.json` (`recency_excluded_ids`).
3. Sample 18 items from the 122-item priority pool with fixed seed 621
   (`random.Random(621).sample(...)` over the sorted item-id list, so the sample is
   reproducible from the frozen pool).
4. This is a feasibility gate, not full-population processing: only the 18 sampled items —
   never the full strict pool (276) and never all 589 items — are sent externally.

## GPT-4o mini is proposal-only

GPT-4o mini proposes `target_description`, candidate gold/placebo spans (as turn indices +
rationale), and a preliminary `proposal_feasibility_label` from the fixed 5-value Phase A
scheme (`localizable` / `localization-failed` / `leakage-risk` / `placebo-unavailable` /
`uninterpretable`). It is never treated as ground truth:
- Proposed turn indices are validated against the real history; out-of-range or malformed
  indices are flagged, not trusted.
- The span text and removed-history text stored in `phaseA_proposals.csv` are recomputed
  mechanically from the actual dataset turns at the validated indices — GPT's own restated
  text is never the source of truth for these columns, to prevent hallucinated history from
  silently entering the pipeline.
- Gold consistency, gold sufficiency/minimality, and placebo neutrality are explicitly
  reserved for human adjudication (see below), not decided by the model.

The final 6-class sensitivity label (`gold-specific sensitivity` / `non-specific sensitivity`
/ `no sensitivity` / `localization failed` / `leakage-confounded` / `uninterpretable`) is
**not** assigned in Phase A — that scheme was not found defined anywhere in the current
`docs/` and, regardless, requires a behavioral Phase B run (gold-removal / placebo-removal
answer comparison) that has not happened yet.

## External sending is limited to sampled Phase A items

Only the 18 sampled item IDs were sent to the OpenAI API (`gpt-4o-mini`), each as one
chat-completion call containing that item's question, options, gold answer, and its own
truncated history (up to `end_index_in_shared_context`). The full strict pool (276 items)
and the full dataset (589 items) were never sent. The sent item IDs and the count are logged
in `phaseA_summary.json` (`sent_item_ids`, `external_send_count`).

No API key, local file paths beyond what's needed, or unrelated personal data were included
in any request. The API key is read only from `OPENAI_API_KEY` (optionally via a local
`.env`, which is git-ignored) and is never written to any code, log, prompt file, CSV, JSON,
or commit.

## Human adjudication is required before Phase B

`phaseA_human_adjudication_sheet.csv` contains every proposal field plus empty human columns
(`human_target_determinate`, `human_gold_span_correct`, `human_gold_span_sufficient`,
`human_gold_span_minimal`, `human_placebo_neutral`, `human_placebo_comparable_length`,
`human_placebo_valid`, `human_remove_operation_valid`, `human_final_include`,
`human_exclusion_reason`, `human_notes`). These are intentionally left blank — they were not
auto-filled by this script. A human reviewer fills them with `yes` / `no` / `uncertain`.

## Phase B must not be run until human adjudication is complete

Phase B (the actual gold-removal / placebo-removal behavioral run on llama/qwen) is out of
scope for Phase A and was not run. Phase B may only start on items where a human has set
`human_final_include = yes` in the adjudication sheet.
