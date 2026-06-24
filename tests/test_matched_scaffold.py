"""Tests for matched-scaffold option shuffle and gold mapping."""

import ast

import pandas as pd

from src.study1_mcq.matched_scaffold import (
    build_shuffle_layout,
    canonical_option_texts,
    display_letter_to_canonical,
    strip_native_prefix,
)
from src.study1_mcq.prompting import gold_letter, parse_letter

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
QUESTIONS_PATH = REPO_ROOT / "data" / "personamem_32k" / "questions_32k.csv"


def test_strip_native_prefix():
    assert strip_native_prefix("(a) hello") == "hello"
    assert strip_native_prefix("(C) World") == "World"


def test_display_to_canonical_roundtrip():
    layout = build_shuffle_layout("item-1", 0, 623, ["t0", "t1", "t2", "t3"])
    for display in "abcd":
        canonical = display_letter_to_canonical(display, layout.display_order)
        pos = ord(display) - ord("a")
        assert canonical == chr(ord("a") + layout.display_order[pos])


def test_parse_letter_accepts_uppercase_answer_line():
    assert parse_letter("Answer: C") == "c"
    assert parse_letter("Answer: B") == "b"


def test_gold_maps_through_shuffle():
    df = pd.read_csv(QUESTIONS_PATH)
    row = df.iloc[0]
    native = ast.literal_eval(row["all_options"])
    texts = canonical_option_texts(native)
    gold = gold_letter(row["correct_answer"])
    layout = build_shuffle_layout(str(row["question_id"]), 0, 623, texts)
    for pos, letter in enumerate("abcd"):
        if chr(ord("a") + layout.display_order[pos]) == gold:
            assert display_letter_to_canonical(letter, layout.display_order) == gold
            break
    else:
        raise AssertionError("gold letter not found in layout")
