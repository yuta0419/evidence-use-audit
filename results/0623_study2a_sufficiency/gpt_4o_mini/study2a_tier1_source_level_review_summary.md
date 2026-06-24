# Study 2a TIER1 source-level review summary

## Scope

Reviewed `study2a_tier1_source_level_packet.csv` at source level, focusing on the pre-marked TIER1 rows:

- TIER1 oracle-correct ceiling check: 21 rows
  - main sufficiency oracle rows: 19 rows
  - preference exploratory oracle rows: 2 rows
- TIER1 floor-leak/world-knowledge rows: 3 rows
- Additional diagnostic note added for `c14c00dd` full/noev rows because the source-level issue affects the C_full diagnostic.

## Verdict counts on TIER1 rows

| source-level verdict | rows | unique items |
|---|---:|---:|
| `FLAG_AMBIGUOUS_BUT_USABLE_SOURCE_LEVEL` | 1 | 1 |
| `PASS_FOR_EXCLUSION_SOURCE_LEVEL` | 3 | 1 |
| `PASS_SOURCE_LEVEL` | 18 | 18 |
| `WEAK_PASS_SOURCE_LEVEL` | 2 | 2 |

## Main findings

### 1. Main C_oracle sufficiency mostly passes source-level review

For the main sufficiency pool oracle rows, 18/19 pass cleanly at source level.

One main item is flagged:

- `c14c00dd`: evidence says the user uses “a lavender scented shampoo” picked up at Trader Joe’s. The gold answer is `Trader Joe's`, and the question asks for the shampoo “brand.” This is likely usable, but the evidence is not maximally explicit that Trader Joe’s is the brand rather than the purchase/source location.

Recommended reporting:

- Primary with caveat: main sufficiency pool `n=19`, C_noev=0/19, C_oracle=19/19.
- Strict-clean sensitivity: excluding `c14c00dd`, `n=18`, C_noev=0/18, C_oracle=18/18.

### 2. C_full = C_oracle should remain a null/diagnostic contrast, not a strong claim

`c14c00dd` also shows judge leniency in the full condition: the full candidate says “lavender scented shampoo,” omitting `Trader Joe's`, while the question asks for the brand. This weakens any strong statement that full context exactly recovers the gold answer for every item.

Recommended wording:

> In the main pool, C_full broadly matches C_oracle, but this is only a diagnostic/null contrast; at least one item shows partial-answer judge leniency, so the stronger evidence is the C_noev vs C_oracle contrast.

### 3. Floor-leak exclusion is source-level supported

`28bcfaac` passes source-level review as an exclusion: noev/oracle/full all recover `MusicTheory.net`, and the answer is a public, generic resource. It should remain outside the sufficiency headline.

### 4. Preference rows should remain exploratory

- `07b6f563`: weak pass. Evidence supports iPhone 13 Pro, screen protector, and phone wallet case; candidate is aligned.
- `a89d7624`: weak pass. Evidence supports Denver/live-music interest, but candidate is generic and does not explicitly mention Brandon Flowers / The Killers / Red Rocks.

Recommended reporting: keep preference as exploratory diagnostic only, not merged into the main n=19 sufficiency headline.

### 5. `2bf43736` source validity

The source packet for `2bf43736` is valid: evidence, gold, and oracle candidate all match “Chapter 4 of Book 1, titled Vocal Prayer and Meditation.” If a qwen oracle failure was observed elsewhere, it is not caused by an invalid gold/evidence source packet in this file.

## Bottom line

Study 2a remains usable and fairly strong, but the safest final wording is:

> After removing the floor-leak item, the main single-session sufficiency pool shows a clean no-evidence floor and a perfect oracle-span ceiling under the reviewed packet (0/19 vs 19/19). A strict-clean sensitivity excluding one source-ambiguity item preserves the pattern (0/18 vs 18/18). Preference items are exploratory and should not be merged into the main headline.
