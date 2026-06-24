# QC notes: Study 2 judge gate — human adjudication outcome (0623)

## Status

`results/0623_study2_judge_gate/judge_gate_human_sheet.csv` is now human-confirmed
(2026-06-23). The 30-item sample was AI-drafted item-by-item (question /
evidence_text / positive_control_response / negative_control_response / judge
verdict inspected per row; draft preserved at
`judge_gate_human_sheet_DRAFT.csv` for provenance) and the draft's conclusions
were reviewed and confirmed by the human in conversation. The human, not the
AI, is the authority per CLAUDE.md and
`results/0623_study2_judge_gate/README.md`; this file records that the
confirmation happened and what it changed.

## Headline finding: type-level gate, not a single overall number

Computed against **human ground truth** (not the provisional intended-label
signal in `judge_gate_summary.json`), the judge is highly reliable where the
underlying evidence-construction works:

| question_type | n items (sampled) | n judgments | raw agreement | FP | FN |
|---|---|---|---|---|---|
| single-session-user | 11 | 22 | 1.000 | 0 | 0 |
| single-session-assistant | 10 | 20 | 1.000 | 0 | 0 |
| single-session-preference | 6 | 12 | 0.917 | 1 | 0 |
| temporal-reasoning | 3 | 6 | 1.000 | 0 | 0 |
| **overall** | 30 | 60 | 0.983 | 1 | 0 |

Full numbers: `results/0623_study2_judge_gate/judge_gate_human_assessment_summary.json`.

Note this supersedes the earlier provisional FN=7 in `judge_gate_summary.json`.
That number was computed against *intended* labels (assume positive_control
always verifiable, negative_control never verifiable). Human review found
that for 7 items the positive_control_response (the dataset's own gold
`answer` field) is genuinely **not verifiable from the localized
evidence_text alone** — the judge correctly said "incorrect" given what it
was shown. That is not a judge defect; it is an evidence-construction /
localization defect in those 7 items. Re-scoring against human ground truth
removes those 7 "false negatives" and leaves exactly the 1 real judge error
(see below).

## Population decision for Study 2a

Decision recorded in `results/0623_study2_judge_gate/study2a_population_decision.json`.

- **Main confirmatory pool (n=20)**: single-session-user (11) + single-session-assistant
  (9, excludes dc439ea3 — see below). Judge agreement on this subset is 22/22 +
  18/18 = 40/40 = 100% in the 30-item sample. This is the pool Study 2a Phase 1
  targets.
- **single-session-preference (n=3 of 6 sampled): exploratory / constraint-only,
  not part of the main confirmatory claim.** 3 of 6 sampled preference items
  (50%) failed human adjudication because the gold `answer` field is a
  *synthesized preference summary* (e.g. "the user would prefer responses
  that...") rather than a literal fact, and the localized
  `has_answer`-flagged turn(s) used by `evidence_text_from_item()` do not
  carry enough of the specific detail the summary references. This is a
  structural property of how this gate constructs evidence for the
  preference type, observed at 50% of a small sample (n=6) — not yet a claim
  about the full 30-item determinacy-passing preference pool. If Study 2a
  later includes the 3 surviving preference items, results must be reported
  separately from the main pool and the type's instability must be stated
  alongside any positive result, per docs/設計ブロック_0621.md's
  preference-generalization / gold-answer-abstraction / evidence-span-
  insufficiency guidance.
- **temporal-reasoning (n=3 sampled): excluded by design**, consistent with
  the original Study 2a brief (date arithmetic relative to an unstated
  "today" is not exposed by the evidence_text construction; usable=0 for this
  type was already the working assumption).
- **dc439ea3 (single-session-assistant): excluded — extraction issue, not
  fixed.** See below.

This replaces the brief's prior assumption of usable=25 (user 11 / assistant 9
/ preference 5). The corrected basis is **main pool = 20** (user 11 +
assistant 9), with preference reduced to 3 exploratory items, not 5.

## dc439ea3: has_answer flag points at the wrong turn (data issue, recorded not patched)

Question: "...which traditional game did you say was often performed by
skilled dancers at powwows?" Gold answer: "Hoop Dance".

Direct inspection of `data/longmemeval/longmemeval_oracle.json` for this
question_id (single session, `answer_ultrachat_459954`):

- **Turn 1 (assistant)** contains the literal answer text verbatim: a
  numbered list of traditional powwow games ending in *"7. Hoop Dance - This
  traditional dance involves intricate movements with multiple hoops, and is
  often performed by skilled dancers at powwows."* This turn's `has_answer`
  field is `False`.
- **Turn 6 (user)** is the only turn flagged `has_answer: True` in this
  session. Its content ("I'll definitely look into those powwows and try to
  attend one soon. Do you have any tips for what to wear or bring to a
  powwow?") does not mention Hoop Dance or any traditional game at all.

`src/study2_open/determinacy_filter.py:evidence_text_from_item()` only
extracts `has_answer`-flagged turns, so it surfaced turn 6 (irrelevant) and
omitted turn 1 (the actual answer). This is consistent with the judge
correctly marking both the positive and negative control "incorrect": neither
response is supported by what it was shown, because what it was shown is not
where the answer lives.

**This is recorded as a known oracle-split / extraction-pipeline discrepancy
for this single item, not fixed.** Per CLAUDE.md #12, parser/extraction rules
are not loosened post hoc to recover one convenient item without checking the
effect on the full population. Whether this is an isolated annotation error
in `longmemeval_oracle.json` or a systematic pattern (e.g. `has_answer` placed
on the eliciting user turn rather than the informative assistant turn for
some fraction of `single-session-assistant` items) is an open question,
deferred — not investigated at the full-population scale here. dc439ea3 is
excluded from the Study 2a main pool on this basis.

## Addendum (2026-06-23): lenient judge variant tested and rejected as primary

The original Study 2a brief assumed a "strict primary / lenient secondary"
judge design. Phase 0 found no such toggle in the actual gate
(`judge_prompt_v1` has a single correct/incorrect verdict). Rather than
silently dropping the lenient idea or redesigning the existing frozen judge,
a separate lenient variant was built (`judge_prompt_v2_lenient`, in
`src/study2_open/judge_gate_lenient.py`) and run on the **same frozen
30-item sample** (`judge_gate_sample.csv`, seed=619) — the population was
not redrawn.

The lenient verdicts were scored against the **same human ground truth**
already recorded in `judge_gate_human_sheet.csv`. No fresh human re-label was
collected: `human_positive_is_correct` / `human_negative_is_correct` answer
"is this response actually correct given the evidence", a fact independent
of which judge prompt is being evaluated, so the existing human-confirmed
sheet is a valid reference for scoring any judge configuration.

### Scoring bug found and fixed

The first version of the lenient-vs-human scoring (and, in principle, the
original strict-vs-human scoring) only checked for a false positive when the
**negative** control was judged "correct", and a false negative only when
the **positive** control was judged "incorrect". This missed the case of the
**positive** control being judged "correct" when human ground truth says it
is actually "incorrect" — exactly the failure mode the lenient judge turned
out to exhibit. Fixed in `src/study2_open/judge_gate_assessment.py`
(`score_against_human_truth`): FP/FN are now symmetric — FP = judge says
"correct" when human truth says "incorrect" for *either* control type; FN =
judge says "incorrect" when human truth says "correct". Strict's numbers are
unchanged by the fix (it had no errors in that direction); lenient's are not.
Regression-tested in `tests/test_judge_gate_assessment.py`.

### Result: lenient is measurably worse, not just differently calibrated

| | strict (judge_prompt_v1) | lenient (judge_prompt_v2_lenient) |
|---|---|---|
| overall agreement (n=60) | 0.983 | 0.900 |
| overall FP | 1 | 6 |
| overall FN | 0 | 0 |
| single-session-user | 1.000 / FP=0 | 1.000 / FP=0 |
| single-session-assistant | 1.000 / FP=0 | 1.000 / FP=0 |
| single-session-preference | 0.917 / FP=1 | 0.750 / FP=3 |
| temporal-reasoning | 1.000 / FP=0 | 0.500 / FP=3 |

Full numbers: `results/0623_study2_judge_gate/judge_gate_lenient_assessment_summary.json`.

Inspecting the 6 lenient false positives directly:

- **3 of 3 single-session-preference exclusions (06878be2, 35a27287,
  75f70248) flip to "correct" under lenient grading**, even though the
  localized evidence still does not contain the specific detail (a cat's
  name, "this weekend", a recent deep clean) the synthesized gold answer
  references. The lenient judge's rationale for each is a generic
  "this conveys the user's preference" — i.e. it stopped checking whether
  the *specific* claimed detail is actually in the evidence and started
  accepting topical relevance instead. This would have silently
  re-included exactly the items the strict/human pass correctly excluded
  for insufficient evidence localization — laundering the type's
  instability rather than surfacing it.
- **2 of 3 temporal-reasoning items produce a new error each, and one of
  them (gpt4_7bc6cf22) flips *both* controls to "correct".** The lenient
  judge's rationale for the negative control ("14 days ago... counting
  today as the last day") **invents an assumed "today" date not present in
  the evidence** to justify accepting a fabricated value — the opposite of
  "do not use outside knowledge to fill gaps," which the lenient prompt
  explicitly instructs against. This is the lenient judge hallucinating
  grounding it does not have, on exactly the type the gate's own evidence
  construction cannot expose (date arithmetic).

**Decision: judge_prompt_v1 (strict) remains the sole judge for Study 2a
Phase 4.** The lenient variant is not adopted as a secondary signal. This is
recorded as a constraint finding, not discarded: it demonstrates that
relaxing evidence-grounding tolerance reintroduces false positives
concentrated in exactly the two already-flagged-fragile types
(single-session-preference's non-literal gold answers, temporal-reasoning's
unexposed date arithmetic), while leaving the main pool
(single-session-user + single-session-assistant, n=20) at 100% agreement
under both strict and lenient. That robustness of the main pool across two
different judge strictness settings is itself a positive finding for the
Study 2a headline claim.
