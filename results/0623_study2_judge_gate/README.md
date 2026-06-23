# Study 2 judge validation gate (0623)

## What this is

This is a **gate**, not a behavioral experiment. It answers two feasibility
questions before any evidence-use audit is run on LongMemEval:

1. Does a determinacy-filtered, single-source-localizable item pool survive at
   all (`determinacy_filter.csv`)?
2. Is the LLM judge trustworthy — does it accept gold answers and, crucially,
   reject evidence-independent answers (`judge_verdicts.csv`,
   `judge_gate_summary.json`)?

No sufficiency experiment, no model-answering experiment, and no behavioral audit
were run here (CLAUDE.md #1, #2, #3; docs/設計ブロック_0621.md §4-§5.1).

## Negative controls are rule-built, not LLM-generated

`negative_control_response` in `judge_gate_sample.csv` is built mechanically by
`src/study2_open/negative_control.py`: either a deterministic value substitution
(r1: year/weekday/month/ordinal-day/integer, shifted by a fixed rule) or a fixed
generic-deflection template that splices in the verbatim question text (r2). No
LLM was used to write any negative control, to avoid reintroducing the provenance
circularity already avoided in PersonaMem Phase A removal.

## Human adjudication is required before any sufficiency experiment

The judge verdicts in `judge_verdicts.csv` and the provisional signal in
`judge_gate_summary.json` are computed against the *intended* control labels
(positive=correct, negative=incorrect) — they are a provisional sanity signal,
not the real gate result. The human, not the judge, is the authority. Fill in
`judge_gate_human_sheet.csv` (human_positive_is_correct,
human_negative_is_correct, human_notes, human_determinacy_ok,
human_localizable_ok) before treating any item/type as gate-passing.

## What must NOT start yet

The next phase (Study 2a evidence-only sufficiency, and Study 2b evidence
contingency) must NOT start until:
  - `judge_gate_human_sheet.csv` is filled in, and
  - the judge gate is assessed against the human verdicts (raw agreement, false
    positive rate, false negative rate, per-type FP concentration — see
    docs/設計ブロック_0621.md §4.2).

False positives (the judge rating an evidence-independent negative_control
"correct") are the highest-priority defect to check, since they would let
evidence-independent answers pass as if they used evidence.
