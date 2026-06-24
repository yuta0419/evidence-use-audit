# Study 2a — LongMemEval evidence-only sufficiency (0623, revised)

**Revision note (2026-06-23): this replaces the first draft of this summary,
which led with "C_oracle 20/20 = 1.000" as a headline. That framing was
wrong and was corrected after review (see "Why this is not a 1.000 headline"
below). The corrected framing leads with the eligibility funnel and the
floor, treats the ceiling as selection-conditioned, and separates one
floor-leak item out of the sufficiency pool. Numbers: see
`results/0623_study2a_sufficiency/gpt_4o_mini/study2a_sufficiency_numbers_v2.json`.**

## Why this is not a 1.000 headline

The population this experiment runs on was built by two successive
selection steps that both select *for* the property being measured:

1. **Determinacy filter** (rule-based, `src/study2_open/determinacy_filter.py`):
   keeps only items with a positive, content-bearing target and evidence
   localizable to a single session/turn. 170/422 non-KU items pass.
2. **Judge-gate human adjudication** (`results/0623_study2_judge_gate/`):
   of a 30-item sample of that 170, items are kept only if a human confirms
   the gold answer is actually verifiable from the localized evidence span.
   23/30 pass; 7/30 are excluded (3 single-session-preference for
   evidence-localization insufficiency, 3 temporal-reasoning for unexposed
   date arithmetic, 1 single-session-assistant — dc439ea3 — for a
   has_answer-flag/extraction discrepancy).

Both filters select for "this item's answer is determined by a localizable
span of evidence" — which is close to the definition of evidence
sufficiency itself. Measuring "can the localized span reproduce the answer"
on a population already filtered for "the localized span determines the
answer" is close to re-confirming the selection, not an independent test.
**This is named explicitly, not hidden**: the natural falsifier class for
this design is temporal-reasoning (items where C_oracle *should* fail
because the evidence span structurally cannot expose date arithmetic) —
and the funnel removes that class *before* the sufficiency measurement runs
(0/3 temporal-reasoning items were ever usable; see judge gate). A 1.000
oracle-correct rate on a pool where the main known failure mode was removed
by construction is not informative on its own.

**What the numbers below report instead**: the funnel itself (how
selective the eligibility criteria are — this is the finding), the floor
(does evidence-independent default-solvability or memorization explain the
result instead of evidence use — this is falsifiable and partially fails,
see below), and the ceiling explicitly labeled as selection-conditioned, not
as a free-standing accuracy claim.

## 1. The funnel (the primary number to cite)

| stage | n | of |
|---|---|---|
| non-KU oracle pool | 422 | — |
| rule-based determinacy filter passes | 170 | /422 |
| judge-gate sample (seed=619) | 30 | /170 |
| **human-confirmed usable** | **23** | **/30** |
| — main sufficiency-audit pool (user 11 + assistant 9) | 20 | of the 23 |
| — preference, exploratory/type-unstable | 3 | of the 23 |
| excluded (preference localization-insufficient 3, temporal-reasoning 3, extraction-issue 1) | 7 | /30 |

**Caveat that must travel with this table**: 30 is a *sample* of the 170
determinacy-passing pool, not a full audit of it. 23/30 (or 20/30 main-pool)
is a sample-level eligibility estimate; it is not rescaled to "23/170" or
"⋯/422" anywhere in this writeup, and should not be cited that way — we do
not know the usable fraction of the full 170 without auditing it.

This funnel is the headline finding: **a sufficiency-auditable subset of
LongMemEval exists, but it is narrow and selection-conditioned** (roughly
two-thirds of a determinacy-passing sample survive human review, and the
type composition is uneven — see §4).

## 2. Floor: is the result evidence-independent or memorized? (the second number to cite)

C_noev (no context at all) correct rate is the falsifiable check for
"default-solvable without evidence" / "memorized QA pair." On the 20-item
main pool, exactly 1 item is solvable at C_noev: `28bcfaac` ("...website you
recommended for free [music theory] lessons?" → "MusicTheory.net"). This
item is **excluded from the sufficiency pool, not averaged into the floor
denominator** (see §3) — counting it in either direction would either hide
a real leak or unfairly deflate the rest of the pool's floor.

**With that one item separated out: floor = 0/19 = 0.000.** None of the
remaining 19 main-pool items are answerable without evidence. Combined with
the fact that the one floor hit is plausibly general/well-known-resource
knowledge (not memorization of this specific synthetic conversation), this
is the strongest result in this experiment: it is evidence *against* the
commercial-model-memorized-the-benchmark explanation for the rest of the
pool, on this small sample. It does not rule out contamination in general
(one model, n=19); Phase 5 (deferred 8B cross-check) is the next line of
defense for that question.

## 3. Sufficiency pool (n=19, main pool minus the floor-leak item)

| | k/n | rate |
|---|---|---|
| C_noev correct (floor) | 0/19 | 0.000 |
| C_oracle correct | 19/19 | 1.000 (selection-conditioned ceiling — see §0) |
| C_full correct | 19/19 | 1.000 |

### Source-level reviewed framing (the wording to publish)

After source-level human review of all TIER1 rows (§5), 18 of the 19 main
oracle rows pass cleanly; one (`c14c00dd`) is usable but mildly source-
ambiguous (see below). The safest published statement keeps the headline and
adds a strict-clean sensitivity that drops the ambiguous item:

> After removing the floor-leak item, the main single-session sufficiency
> pool shows a clean no-evidence floor and a perfect oracle-span ceiling
> under the reviewed packet: **C_noev = 0/19 and C_oracle = 19/19**. A
> strict-clean sensitivity excluding one mildly source-ambiguous item
> preserves the pattern: **C_noev = 0/18 and C_oracle = 18/18**.

The result does not depend on the ambiguous item: dropping it changes
neither the floor (still 0) nor the ceiling (still all-correct).

### The one source-ambiguous item: `c14c00dd`

Question "What brand of shampoo do I currently use?", gold `Trader Joe's`,
evidence "a lavender scented shampoo that I picked up on a whim at Trader
Joe's." The evidence states *where the shampoo was bought*, not explicitly
that the brand *is* Trader Joe's — so reading the gold answer out of the
evidence requires a mild store→brand inference. The item is kept in the
primary n=19 but dropped in the n=18 strict-clean sensitivity. Required
caveat for any writeup:

> One item involves mild source ambiguity because the evidence states that
> the shampoo was picked up at Trader Joe's, while the question asks for the
> brand.

### C_full == C_oracle is a null/diagnostic contrast — and weaker than it looks

**C_full == C_oracle is reported as a null result for the span-narrowing
question, not as a second positive.** The only live contrast in this
experiment is oracle/full (19/19) vs. noev (0/19) — i.e. "some evidence
helps", not "the minimal span specifically helps over the full session."

Source-level review further weakened the "C_full exactly recovers gold"
reading: for `c14c00dd`, the C_full candidate is "You currently use a
lavender scented shampoo" — which **omits `Trader Joe's` entirely** yet was
judged correct (flagged `FLAG_JUDGE_LENIENCY_UNDERANSWER_SOURCE_LEVEL`). So
at least one C_full "correct" is a partial-answer judge-leniency pass, not a
full gold recovery. **Do not make a strong "full context exactly recovers
the gold answer for every item" claim.** The robust signal is C_noev vs.
C_oracle, not C_full vs. C_oracle.

`28bcfaac` (floor-leak, excluded above): noev=correct, oracle=correct,
full=correct — source-level review confirms the exclusion
(`PASS_FOR_EXCLUSION_SOURCE_LEVEL`): the answer is a public, generic resource
(MusicTheory.net), so this is world-knowledge convergence, correctly kept out
of the sufficiency headline.

## 4. Type heterogeneity: preference-exploratory pool (n=3) — a genuinely different, informative pattern

| | k/n | rate |
|---|---|---|
| C_noev correct | 0/3 | 0.000 |
| C_oracle correct | 2/3 | 0.667 |
| C_full correct | 0/3 | 0.000 |

This is the opposite pattern from the main pool, and it is informative
precisely because it diverges:

- **C_full < C_oracle here (a live, non-null contrast)**: for `07b6f563`
  and `a89d7624`, C_full answers drift into plausible, on-topic, but
  evidence-unsupported elaboration (e.g. for a Denver trip question, C_full
  suggests "Denver Art Museum, Botanic Gardens" — real attractions, but not
  what the localized preference evidence — interest in the live-music
  scene — actually supports), while C_oracle's narrower context keeps the
  answer anchored to the specific preference. Full-session context measurably
  *hurts* for this type, where it was a no-op for the main pool.
- **`38146c39` fails all three conditions**, including C_oracle. The gold
  target for this item is a meta-level preference description ("the user
  would prefer ingredient suggestions that build on turbinado sugar"), but
  when actually asked the question ("any advice for my cookies?"), the
  auditor model gives a literal, actionable suggestion (sea salt, vanilla
  extract) — which does not restate the gold's meta-preference framing even
  with the correct evidence in hand. This is a second, independent
  structural problem with the preference type beyond the gate-stage finding
  (non-literal gold answers vs. localized verbatim evidence): the
  **question/answer format itself mismatches** for this type, regardless of
  context condition.

n=3 is too small for a rate claim; this is reported as a qualitative
type-contrast finding, not a second sufficiency number.

Source-level review of the 2 preference oracle-correct rows confirms they are
only `WEAK_PASS_SOURCE_LEVEL`: `07b6f563` aligns with the evidence (iPhone 13
Pro screen protector / wallet case), but `a89d7624`'s candidate ("explore the
music scene, visit local venues, check out festivals") is generic and does
**not** name the specific evidence (Brandon Flowers / The Killers / Red
Rocks). Correctness here turns on matching recommendation *scope*, not exact
factual recall — qualitatively different from the main pool. These two items
stay exploratory and are never merged into the main n=19/n=18 headline.

## 5. Adjudication sheet (human review required before any of the above is treated as confirmed)

`results/0623_study2a_sufficiency/gpt_4o_mini/study2a_adjudication_sheet.csv`
— 69 rows (23 items × 3 conditions), judge labels + empty human columns.
**Review priority is not limited to the floor-leak cell.** Per the concern
that a 1.000 ceiling could itself be judge leniency, `review_priority` is
set to `TIER1_oracle_correct_ceiling_check` for **all 21 C_oracle="correct"
rows** (19 main pool + 2 preference), plus `TIER1_floor_leak_world_knowledge`
for the 3 rows of `28bcfaac`. The ceiling claim in §3 is not treated as
confirmed until this tier is reviewed.

### Sheet-level review completed (2026-06-23) — not yet a full source-level check

A first human pass was done directly on `study2a_adjudication_sheet.csv`:
`results/0623_study2a_sufficiency/gpt_4o_mini/judge_scores/study2a_adjudication_sheet_reviewed_sheet_level.csv`
and `..._review_summary.md`. Verdict counts: `PROVISIONAL_PASS` 19 (the
non-floor-leak TIER1 oracle-correct main-pool rows), `PASS_FOR_EXCLUSION` 3
(28bcfaac, all conditions — confirms the floor-leak exclusion in §2-3),
`PROVISIONAL_WEAK_PASS` 2 (the preference oracle-correct rows — flagged
weaker because correctness there depends on matching recommendation scope,
not exact factual recall), `CONSISTENT_WITH_FLOOR_ZERO` 19,
`CONSISTENT_WITH_FULL_CEILING` 19, `CONSISTENT_WITH_PREFERENCE_DRIFT_OR_FORMAT_FAIL` 7.

**This sheet-level pass did not include the original question, gold answer,
or evidence span** — only item_id/condition/candidate_response/judge_verdict/
judge_rationale were available, so it verified internal consistency of the
judge's verdicts and rationales, not independent source-grounded
correctness. The required caveat, to travel with any paper/slide use of
these numbers:

> The present adjudication sheet-level check verifies the consistency of
> judge verdicts and rationales, but full independent human adjudication
> requires the original question, gold answer, and evidence span.

### Source-level TIER1 review completed (2026-06-24)

The source-level re-check has since been done against the actual
question/gold/evidence, not just the judge's rationale:
`results/0623_study2a_sufficiency/gpt_4o_mini/study2a_tier1_source_level_packet_reviewed.csv`
and `..._source_level_review_summary.md`. TIER1 verdict counts:
`PASS_SOURCE_LEVEL` 18 (main oracle rows), `FLAG_AMBIGUOUS_BUT_USABLE_SOURCE_LEVEL`
1 (`c14c00dd` oracle — the source-ambiguity item handled by the §3
sensitivity), `WEAK_PASS_SOURCE_LEVEL` 2 (preference oracle rows, §4),
`PASS_FOR_EXCLUSION_SOURCE_LEVEL` 3 (`28bcfaac`), plus a diagnostic flag on
`c14c00dd`'s C_full row (`FLAG_JUDGE_LENIENCY_UNDERANSWER_SOURCE_LEVEL`, §3).

**Outcome: the §3 main result survives source-level review** — 18/19 main
oracle rows pass cleanly, the one flagged item does not change the floor or
ceiling (strict-clean sensitivity 0/18, 18/18), and the only material new
finding is that the C_full=C_oracle equivalence is weaker than the raw
numbers suggest (one full pass is partial-answer judge leniency), which is
why C_noev vs. C_oracle — not C_full — is treated as the robust contrast.
This source-level pass is one careful human review, not multi-rater
adjudication; it does not retire the general judge-mediated caveat (results
remain bounded by the judge gate).

## 5b. Phase 5 — 8B contamination cross-check (llama3.1:8b, qwen2.5:7b; C_oracle/C_noev only)

Run on the same sufficiency pool (n=19, main pool minus the 28bcfaac
floor-leak; C_full not run for either model per the brief's deferred-
robustness scope — long-context failure would confound). Numbers:
`results/0623_study2a_sufficiency/phase5_8b_crosscheck_numbers.json`.

| model | C_noev correct | C_oracle correct |
|---|---|---|
| llama3.1:8b | 2/19 (0.105) | 19/19 (1.000) |
| qwen2.5:7b | 2/19 (0.105) | 18/19 (0.947) |
| (gpt-4o-mini, for reference) | 0/19 (0.000) | 19/19 (1.000) |

**Output-format note**: both 8B models frequently answer without the
requested `Answer: ` prefix (llama oracle parse_status="valid" only 10%,
qwen only 15%) — e.g. llama returns `"Luna."` directly. This is an
instruction-following gap, not a correctness problem: `raw_output` is
preserved per CLAUDE.md #11, and `candidate_response_for()` in
`study2a_judge_score.py` already falls back to `raw_output` whenever
`parsed_answer` is empty, so the judge still saw and scored the real
answer text in every case (the parser rule itself was not loosened to
manufacture this fallback — it was already the designed behavior).

**The contamination finding (this is the useful result from Phase 5):**
each model leaks on a *different* item.

- gpt-4o-mini leaks on `28bcfaac` only ("MusicTheory.net" with zero context).
- llama3.1:8b leaks on `16c90bf4` ("Pilsner" for a lamb-stew beer pairing)
  and `86b68151` ("IKEA" for a cheap bookshelf) — **and also reproduces the
  28bcfaac leak** ("MusicTheory.net" verbatim with zero context).
- qwen2.5:7b leaks on the same `16c90bf4`/`86b68151` pair as llama, but
  **does not** leak on `28bcfaac` (answers incorrectly at C_noev there).

No single item leaks at C_noev for all three models, and the two leaking
pairs (`{28bcfaac}` vs `{16c90bf4, 86b68151}`) are disjoint across model
families except for 28bcfaac's partial 2/3 overlap. This is the pattern
expected from **independent models converging on the single most
generic/stereotypical plausible answer** to an open-ended question (a
well-known free resource; "pilsner/lager" as the default beer-pairing
guess; "IKEA" as the default cheap-furniture guess) — not from a shared
memorized benchmark QA pair, which would be expected to leak identically
across unrelated model families trained on different data. This is
evidence *against* shared-contamination explaining the ceiling, on top of
the within-model floor check in §2; it does not prove no contamination for
any single model.

**One likely judge error surfaced by this cross-check**: qwen's one
C_oracle failure (`2bf43736`) answered "Chapter 4 of Book 1 in the second
part of Adolphe Tanqueray's Spiritual Life treatise..." — this appears to
faithfully preserve the evidence's own (admittedly awkward) nested phrasing
("the chapter in the second part of [the treatise]... is Chapter 4 of Book
1"), but the judge's rationale reads it as a contradiction ("the evidence
states Chapter 4 is in Book 1, not the second part"), which looks like a
misparse of the nested structure rather than a genuine answer error. Flagged
for human review rather than silently corrected — found via Phase 5 testing,
outside the original 30-item judge-gate sample, so it is a new data point on
judge reliability, not yet folded into the gate's own FP/FN counts.

## 6. Positioning (what this is allowed to say in the paper)

This is **not** "Study 2a proves evidence-use sufficiency in LongMemEval."
It is the **positive side of a format × type contrast** with Study 1's
PersonaMem removal-feasibility result: in PersonaMem Phase A
(`results/0621_phaseA_removal_feasibility/`), only 3 of 18 sampled
strict-bucket items survived full human adjudication for a clean
gold-span + neutral-placebo removal design
(`human_final_include`: yes=3, no=15) — a neutral placebo could not even be
constructed for most items, because evidence and target are too entangled
with the rest of the persona context. In LongMemEval single-session
factual/user/assistant items, by contrast, passing an eligibility funnel
(determinacy filter + judge-gate human adjudication) yields a small but
genuinely sufficiency-auditable subset (20/30 of a sample, with the floor
falsifier removed at 0/19). The honest claim is: **eligibility is a binding
constraint in both benchmarks, but LongMemEval single-session items can
clear it at a non-trivial rate where PersonaMem mostly cannot.** This
connects directly to 研究計画書0621.md §C2/C3 (format × type heterogeneity)
and should be presented there, with the funnel and floor as the cited
numbers — not the 1.000 ceiling alone.

## Claim boundary (unchanged in spirit, restated precisely)

- **Can say**: a sufficiency-auditable subset of LongMemEval single-session
  items exists and clears a non-trivial fraction of a judge-gate-sampled
  eligibility funnel (20/30, or 23/30 including the unstable preference
  type); within that subset, after removing the one world-knowledge
  floor-leak item, the no-evidence floor is clean and the oracle-span ceiling
  is perfect under source-level review (C_noev 0/19, C_oracle 19/19), and a
  strict-clean sensitivity dropping the one source-ambiguous item preserves
  the pattern (0/18, 18/18).
- **Can additionally say (Phase 5, §5b)**: two independent open-weight
  models (llama3.1:8b, qwen2.5:7b) replicate the near-ceiling C_oracle result
  (19/19 and 18/19) and each leak on a *different* C_noev item than
  gpt-4o-mini does, with no item leaking across all three models — a pattern
  consistent with independent generic-guess convergence rather than a
  shared memorized benchmark pair. This is partial, not conclusive, evidence
  against shared contamination.
- **Cannot say**: that the 1.000 oracle/full ceiling is an unconditional
  accuracy number (it is selection-conditioned by construction, §0); that
  span-narrowing helps in general (null result on the main pool, §3); that
  this generalizes beyond single-session user/assistant items (preference
  behaves qualitatively differently, §4; multi-session/temporal-reasoning
  were never in scope); that contamination is fully ruled out for any single
  model (Phase 5 is a cross-model pattern check on n=19, not a per-model
  proof); that C_full exactly recovers the gold answer for every item (at
  least one C_full pass is partial-answer judge leniency — c14c00dd, §3); that
  the judge itself is error-free (the c14c00dd C_full under-answer was
  accepted, §3, and a likely qwen-oracle misparse surfaced in Phase 5, §5b);
  that the source-level ceiling check is multi-rater (it is one careful human
  pass, §5).
