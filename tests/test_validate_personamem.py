"""Tests for PersonaMem-v1 32k structural validation.

Skipped if data/ has not been populated by src/data_acquisition/fetch_personamem.py.
No row count is hardcoded; checks operate over whatever rows are present.
"""

import pytest

from src.data_acquisition.validate_personamem import (
    QUESTIONS_PATH,
    check_context_boundary,
    check_context_link,
    check_gold_resolvable,
    check_nongold_extractable,
    check_option_structure,
    load_context_ids,
    load_questions,
)

pytestmark = pytest.mark.skipif(
    not QUESTIONS_PATH.exists(),
    reason="data/personamem_32k not present; run src/data_acquisition/fetch_personamem.py first",
)


@pytest.fixture(scope="module")
def df():
    return load_questions()


@pytest.fixture(scope="module")
def context_ids():
    return load_context_ids()


def test_rows_present(df):
    assert len(df) > 0


def test_option_structure(df):
    result = check_option_structure(df)
    assert result.passed, str(result)


def test_gold_resolvable(df):
    result = check_gold_resolvable(df)
    assert result.passed, str(result)


def test_nongold_extractable(df):
    result = check_nongold_extractable(df)
    assert result.passed, str(result)


def test_context_link(df, context_ids):
    result = check_context_link(df, context_ids)
    assert result.passed, str(result)


def test_context_boundary(df):
    result = check_context_boundary(df)
    assert result.passed, str(result)
