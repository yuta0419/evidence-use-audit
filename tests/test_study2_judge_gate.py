"""Tests for the Study 2 (LongMemEval) determinacy filter and negative-control rule.

Gate-stage logic only (src/study2_open/). Determinacy-filter tests are skipped if
data/longmemeval has not been populated by src/data_acquisition/fetch_longmemeval.py.
Negative-control tests run unconditionally (pure functions, no data dependency).
"""

import pytest

from src.study2_open.determinacy_filter import ORACLE_PATH, build_determinacy_table, load_oracle
from src.study2_open.negative_control import build_negative_control

pytestmark_data = pytest.mark.skipif(
    not ORACLE_PATH.exists(),
    reason="data/longmemeval not present; run src/data_acquisition/fetch_longmemeval.py first",
)


@pytest.fixture(scope="module")
def determinacy_rows():
    if not ORACLE_PATH.exists():
        pytest.skip("data/longmemeval not present")
    return build_determinacy_table(load_oracle())


@pytestmark_data
def test_ku_items_all_excluded(determinacy_rows):
    ku_rows = [r for r in determinacy_rows if r["question_type"] == "knowledge-update"]
    assert ku_rows
    assert all(r["excluded_as_ku"] for r in ku_rows)
    assert all(not r["determinacy_filter_pass"] for r in ku_rows)


@pytestmark_data
def test_filter_discriminates_not_everything_passes(determinacy_rows):
    non_ku = [r for r in determinacy_rows if not r["excluded_as_ku"]]
    passing = [r for r in non_ku if r["determinacy_filter_pass"]]
    assert 0 < len(passing) < len(non_ku)


@pytestmark_data
def test_multi_session_evidence_fails_localizability(determinacy_rows):
    multi = [r for r in determinacy_rows if r["question_type"] == "multi-session"]
    assert multi
    assert all(not r["single_source_localizable_flag"] for r in multi)


@pytestmark_data
def test_single_session_assistant_all_localizable(determinacy_rows):
    rows = [r for r in determinacy_rows if r["question_type"] == "single-session-assistant"]
    assert rows
    assert all(r["single_source_localizable_flag"] for r in rows)


@pytestmark_data
def test_abstention_items_fail_target_determinacy(determinacy_rows):
    abstention_rows = [r for r in determinacy_rows if r["is_abstention"] and not r["excluded_as_ku"]]
    assert abstention_rows
    assert all(not r["target_determinacy_flag"] for r in abstention_rows)
    assert all(not r["determinacy_filter_pass"] for r in abstention_rows)


def test_negative_control_value_substitution_differs():
    result = build_negative_control("When did it happen?", "It happened in 2020.")
    assert result["negative_control_rule"] == "r1"
    assert result["negative_control_response"] != "It happened in 2020."
    assert "2021" in result["negative_control_response"]


def test_negative_control_weekday_substitution_differs():
    result = build_negative_control("What day was it?", "It was on Monday.")
    assert result["negative_control_rule"] == "r1"
    assert "Monday" not in result["negative_control_response"]
    assert result["negative_control_response"] != "It was on Monday."


def test_negative_control_avoids_modal_verb_collision():
    result = build_negative_control("What should the user do?", "The user may not prefer general suggestions.")
    assert "August" not in result["negative_control_response"]


def test_negative_control_falls_back_to_generic_deflection():
    result = build_negative_control("What is your favorite food?", "Pizza")
    assert result["negative_control_rule"] == "r2"
    assert result["negative_control_response"] != "Pizza"
    assert "favorite food" in result["negative_control_response"]


def test_negative_control_unavailable_when_inputs_empty():
    result = build_negative_control("", "")
    assert result["negative_control_rule"] == "unavailable"
    assert result["negative_control_response"] == ""


def test_negative_control_handles_non_string_answer():
    result = build_negative_control("How many items?", 4)
    assert result["negative_control_rule"] in ("r1", "r2")
    assert result["negative_control_response"] != "4"
