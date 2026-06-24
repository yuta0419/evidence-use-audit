"""Tests for the Study 2a matched-scaffold context-block builder (src/study2_open/sufficiency_scaffold.py).

Pure-function tests: no network, no API key, no LongMemEval data dependency
required beyond a hand-built fixture item.
"""

from src.study2_open.sufficiency_scaffold import (
    build_context_text,
    build_user_prompt,
    full_session_text_from_item,
    parse_answer,
)

FIXTURE_ITEM = {
    "question_id": "fixture0001",
    "question": "What is the name of my cat?",
    "haystack_sessions": [
        [
            {"role": "user", "content": "I got a new desk lamp today.", "has_answer": False},
            {"role": "assistant", "content": "Nice! What color is it?", "has_answer": False},
            {"role": "user", "content": "My cat's name is Luna.", "has_answer": True},
        ]
    ],
}


def test_noev_context_is_empty():
    assert build_context_text(FIXTURE_ITEM, "noev", [2]) == ""


def test_oracle_context_is_only_the_evidence_turn():
    text = build_context_text(FIXTURE_ITEM, "oracle", [2])
    assert text == "user: My cat's name is Luna."


def test_full_context_includes_every_turn_in_order():
    text = full_session_text_from_item(FIXTURE_ITEM)
    lines = text.split("\n")
    assert len(lines) == 3
    assert lines[0] == "user: I got a new desk lamp today."
    assert lines[-1] == "user: My cat's name is Luna."


def test_noev_user_prompt_omits_context_block_entirely():
    prompt = build_user_prompt(condition="noev", question=FIXTURE_ITEM["question"], context_text="")
    assert "context" not in prompt.lower()
    assert prompt.startswith("Question:")


def test_oracle_and_full_share_template_differing_only_in_context_text():
    oracle_text = build_context_text(FIXTURE_ITEM, "oracle", [2])
    full_text = full_session_text_from_item(FIXTURE_ITEM)
    oracle_prompt = build_user_prompt(condition="oracle", question=FIXTURE_ITEM["question"], context_text=oracle_text)
    full_prompt = build_user_prompt(condition="full", question=FIXTURE_ITEM["question"], context_text=full_text)
    oracle_template = oracle_prompt.replace(oracle_text, "{CTX}")
    full_template = full_prompt.replace(full_text, "{CTX}")
    assert oracle_template == full_template


def test_parse_answer_valid_line():
    assert parse_answer("Answer: Luna") == ("Luna", "valid")


def test_parse_answer_case_insensitive_and_multiline():
    raw = "Some preamble\nANSWER: Luna the cat\n"
    assert parse_answer(raw) == ("Luna the cat", "valid")


def test_parse_answer_empty():
    assert parse_answer("") == (None, "empty")
    assert parse_answer("   ") == (None, "empty")


def test_parse_answer_unparsed_but_not_discarded():
    answer, status = parse_answer("I think it might be Luna.")
    assert answer is None
    assert status == "unparsed"
