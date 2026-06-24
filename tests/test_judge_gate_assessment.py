"""Tests for the symmetric FP/FN scoring used by src/study2_open/judge_gate_assessment.py.

Regression guard for the 2026-06-23 fix: an earlier version of this scoring
only counted a false positive when the *negative* control was judged
"correct", and a false negative only when the *positive* control was judged
"incorrect". That missed the case found when scoring the lenient judge
variant: the *positive* control judged "correct" when human ground truth
said it was actually "incorrect" (see
docs/QC_notes_study2_judge_gate_human_adjudication_0623.md). These tests
build a tiny synthetic sample/human-sheet/verdicts fixture so the scoring
function is exercised directly, independent of the real 30-item gate data.
"""

import csv

import pytest

from src.study2_open.judge_gate_assessment import score_against_human_truth


@pytest.fixture
def fixture_paths(tmp_path, monkeypatch):
    sample_path = tmp_path / "judge_gate_sample.csv"
    human_path = tmp_path / "judge_gate_human_sheet.csv"
    verdicts_path = tmp_path / "judge_verdicts.csv"

    with open(sample_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "question_type"])
        w.writeheader()
        w.writerow({"question_id": "q1", "question_type": "typeA"})
        w.writerow({"question_id": "q2", "question_type": "typeA"})

    with open(human_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "human_positive_is_correct", "human_negative_is_correct"])
        w.writeheader()
        # q1: positive control is NOT actually verifiable from evidence (human says no).
        w.writerow({"question_id": "q1", "human_positive_is_correct": "no", "human_negative_is_correct": "no"})
        # q2: a normal, well-behaved item.
        w.writerow({"question_id": "q2", "human_positive_is_correct": "yes", "human_negative_is_correct": "no"})

    with open(verdicts_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["question_id", "control_type", "judge_verdict"])
        w.writeheader()
        # q1: judge over-accepts the positive control human says is incorrect -> should count as FP.
        w.writerow({"question_id": "q1", "control_type": "positive", "judge_verdict": "correct"})
        w.writerow({"question_id": "q1", "control_type": "negative", "judge_verdict": "incorrect"})
        # q2: judge agrees with human on both.
        w.writerow({"question_id": "q2", "control_type": "positive", "judge_verdict": "correct"})
        w.writerow({"question_id": "q2", "control_type": "negative", "judge_verdict": "incorrect"})

    monkeypatch.setattr("src.study2_open.judge_gate_assessment.SAMPLE_PATH", sample_path)
    monkeypatch.setattr("src.study2_open.judge_gate_assessment.HUMAN_SHEET_PATH", human_path)
    return verdicts_path


def test_positive_control_overacceptance_counts_as_false_positive(fixture_paths):
    result = score_against_human_truth(fixture_paths)
    assert result["overall"]["n_judgments"] == 4
    assert result["overall"]["false_positive_count"] == 1
    assert result["overall"]["false_negative_count"] == 0
    assert result["overall"]["raw_agreement"] == 0.75


def test_per_type_breakdown_matches_overall_for_single_type(fixture_paths):
    result = score_against_human_truth(fixture_paths)
    assert result["by_type"]["typeA"]["false_positive_count"] == 1
    assert result["by_type"]["typeA"]["n_items"] == 2
