"""Canonical question_type mapping for PersonaMem-v1 32k.

The 32k questions_32k.csv `question_type` column uses raw PersonaMem labels.
docs/設計ブロック_0621.md §3.2 reports the same 7 types under different
("canonical") names. The mapping below was confirmed by exact n-count
correspondence against that table (re-verified against the live 32k file,
not assumed):

  raw                                            | n   | canonical
  track_full_preference_evolution                | 139 | preference_evolution_tracking
  recall_user_shared_facts                       | 129 | user_shared_fact_recall
  recalling_the_reasons_behind_previous_updates  |  99 | preference_update_reason_recall
  suggest_new_ideas                              |  93 | idea_suggestion
  generalizing_to_new_scenarios                  |  57 | scenario_generalization
  provide_preference_aligned_recommendations     |  55 | preference_aligned_recommendation
  recalling_facts_mentioned_by_the_user          |  17 | latest_preference_acknowledgement

Only the 32k split is in scope (CLAUDE.md #6); no cross-split reconciliation
is needed.
"""

RAW_TO_CANONICAL = {
    "track_full_preference_evolution": "preference_evolution_tracking",
    "recall_user_shared_facts": "user_shared_fact_recall",
    "recalling_the_reasons_behind_previous_updates": "preference_update_reason_recall",
    "suggest_new_ideas": "idea_suggestion",
    "generalizing_to_new_scenarios": "scenario_generalization",
    "provide_preference_aligned_recommendations": "preference_aligned_recommendation",
    "recalling_facts_mentioned_by_the_user": "latest_preference_acknowledgement",
}


def to_canonical(raw_type: str) -> str:
    if raw_type not in RAW_TO_CANONICAL:
        raise ValueError(
            f"unmapped question_type: {raw_type!r}. "
            "This mapping was built from observed 32k counts; an unseen "
            "raw type means the data no longer matches the confirmed mapping "
            "and must be re-checked, not guessed."
        )
    return RAW_TO_CANONICAL[raw_type]
