# judge_gate_human_sheet_DRAFT.csv — AI draft, NOT a completed gate

This file is an **AI-drafted recommendation**, produced by inspecting each of the
30 sampled items' `question` / `evidence_text` / `positive_control_response` /
`negative_control_response` against the judge's verdict (`judge_verdicts.csv`).
It is not human adjudication. Per CLAUDE.md and
`results/0623_study2_judge_gate/README.md`, **the human is the authority, not
an LLM** — this draft exists only to make the real human pass faster by
surfacing per-item rationale and flagging the cases most likely to need a
real decision.

**Do not copy this file over the real `judge_gate_human_sheet.csv` without
review.** Once reviewed/edited by a human, copy the confirmed contents into
`judge_gate_human_sheet.csv` (or have Claude Code do it) before treating the
gate as passed.

## Draft recommendation summary

- INCLUDE (draft): 23 of 30 — single-session-user 11, single-session-assistant 9,
  single-session-preference 3.
- EXCLUDE (draft): 7 of 30 — single-session-preference 3, single-session-assistant 1,
  temporal-reasoning 3 (already out of scope by type per the Study 2a brief).

## Headline finding: single-session-preference is structurally weak under this
## gate's evidence-construction method

3 of 6 sampled single-session-preference items (35a27287, 06878be2, 75f70248)
fail at the human-judgment level: their gold `answer` field is a *synthesized
preference summary* (e.g. "the user would prefer responses that..."), not a
literal quote. The gate's evidence_text construction
(`src/study2_open/determinacy_filter.py:evidence_text_from_item`) extracts only
the `has_answer`-flagged turn(s) verbatim. For these 3 items, that narrow span
does not carry enough of the specific detail (e.g. a cat's name "Luna", "the
weekend", a "recent deep clean") that the synthesized gold answer references —
so a strict judge (correctly) cannot verify the gold answer from the shown
evidence alone, and in one case (35a27287) also accepted a generic deflection
as "correct" since neither response was clearly worse against that thin
evidence.

This is a 50% failure rate within the small preference sample (n=6), not 1
isolated item — it should be treated as a property of the type under the
current evidence-construction method, not noise, unless the human reviewer
disagrees on inspection. If confirmed, it directly contradicts the Study 2a
brief's assumed usable breakdown of "preference 5" (this draft finds 3, not
5, out of 6 sampled before any further filtering).

## Other flagged item: dc439ea3 (single-session-assistant)

Gold answer "Hoop Dance" does not appear anywhere in the localized
evidence_text (a single user turn asking for powwow attire tips). This
suggests the oracle split's `has_answer` flag, or this gate's turn-index
extraction, points at the wrong turn for this item — worth a direct look at
`data/longmemeval/longmemeval_oracle.json` for this question_id before
deciding to exclude vs. fix extraction.

## Items NOT independently re-verified in depth

The 23 draft-INCLUDE items were checked for: (a) judge verdict matches
intended label, (b) evidence_text contains a verbatim statement of the
positive_control_response, (c) negative_control_response is not supported by
the same evidence_text. All 23 passed this check. A human pass is still
required per the gate's own rule (the AI is not the authority), but these are
lower-risk than the 7 flagged above.
