"""Shared prompt construction, ollama call, and letter parsing for Study 1.

Reused by gate1.py (Step A) and m3_validation.py (Step C) so the stimulus
and parsing logic are identical across models/layers.

2026-06-22 revision: replaces the v1 leading-token-only parser, which was
found to have two compounding defects (documented in
docs/QC_notes_gate1_new_run.md and docs/QC_notes_gate1_rerun_0622.md):
  1. num_predict=16 truncated llama's "explanation then letter" responses
     before the letter was generated at all.
  2. The leading-token regex misclassified responses starting with the
     English indefinite article "A " (e.g. "A great choice would be...")
     as an intentional selection of letter 'a'.
parse_letter_v1_leading_token is kept only for diff/audit purposes (CLAUDE.md
#12: any rule change must be checked against its effect on the full
population, not applied retroactively and silently).
"""

import re
from dataclasses import dataclass

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

LETTERS = ("a", "b", "c", "d")

DEFAULT_NUM_PREDICT = 256

_LEADING_LETTER_RE = re.compile(r"^\s*\(?\s*([a-dA-D])\s*\)?[\.\):,]?\s*$|^\s*\(?\s*([a-dA-D])\s*\)?[\.\):,]?\s+\S")

_ANSWER_FORMAT_RE = re.compile(r"\banswer\b\s*(?:is)?\s*:?\s*\(?([a-dA-D])\)?\b", re.IGNORECASE)


def build_prompt(question: str, options: list[str]) -> str:
    """C_default: question + native options only. No persona/context/memory/evidence."""
    options_block = "\n".join(options)
    return (
        f"{question}\n\n"
        f"{options_block}\n\n"
        "Answer with a single letter only: a, b, c, or d."
    )


def call_ollama(model: str, prompt: str, temperature: float, num_predict: int = DEFAULT_NUM_PREDICT) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def _strip_letter_token(token: str) -> str | None:
    """Strip surrounding punctuation/parens from a single token; return the
    bare letter iff what remains is exactly one of a/b/c/d."""
    stripped = token.strip().strip("()[]{}.,:;\"'").strip()
    if len(stripped) == 1 and stripped.lower() in LETTERS:
        return stripped.lower()
    return None


def parse_letter_v1_leading_token(raw_response: str) -> str | None:
    """DEPRECATED (kept for audit/diff only). Extracts the predicted letter
    from the first non-whitespace token. Known bug: misreads the English
    indefinite article "A " at the start of a sentence as letter 'a'."""
    text = raw_response.strip()
    if not text:
        return None
    match = _LEADING_LETTER_RE.match(text)
    if not match:
        return None
    letter = (match.group(1) or match.group(2)).lower()
    return letter if letter in LETTERS else None


def parse_letter(raw_response: str) -> str | None:
    """Pre-specified 3-tier extraction rule (fixed 2026-06-22, not to be
    loosened after seeing results — CLAUDE.md #12).

    Tier (i):   an explicit "answer: X" / "answer is X" statement anywhere
                in the text.
    Tier (ii):  a line that consists of nothing but a single a/b/c/d token
                (optionally parenthesized/punctuated).
    Tier (iii): the final token of the whole response, if it is an isolated
                single a/b/c/d token.

    The first tier that produces any match decides the outcome: if all
    matches at that tier agree on one letter, that letter is returned: if
    they disagree (multiple distinct letters), or no tier ever matches, the
    result is None (parse_invalid) — no forced guess.
    """
    text = raw_response.strip()
    if not text:
        return None

    # Tier (i): explicit "answer: X" statement.
    answer_matches = {m.group(1).lower() for m in _ANSWER_FORMAT_RE.finditer(text)}
    if answer_matches:
        return answer_matches.pop() if len(answer_matches) == 1 else None

    # Bare enumeration guard (2026-06-22, found during v1/v2 diff verification on
    # the 589-item rerun, confirmed to affect exactly 1/1178 calls): a response
    # that is *only* a sequence of distinct letter tokens (e.g. "a, b, c, d") is
    # not a deliberate final answer; without this guard tier (iii) below would
    # mistake the last listed letter for the chosen one.
    words_all = text.split()
    stripped_all = [_strip_letter_token(w) for w in words_all]
    if words_all and all(stripped_all):
        return stripped_all[0] if len(set(stripped_all)) == 1 else None

    # Tier (ii): a line containing only a single letter token.
    line_letters = set()
    for line in text.split("\n"):
        words = line.strip().split()
        if len(words) == 1:
            letter = _strip_letter_token(words[0])
            if letter:
                line_letters.add(letter)
    if line_letters:
        return line_letters.pop() if len(line_letters) == 1 else None

    # Tier (iii): the final token of the entire response.
    words = text.split()
    if words:
        letter = _strip_letter_token(words[-1])
        if letter:
            return letter

    return None


def gold_letter(correct_answer: str) -> str:
    """correct_answer is formatted like '(c)'; extract the bare letter."""
    match = re.search(r"[a-dA-D]", correct_answer)
    if not match:
        raise ValueError(f"cannot extract gold letter from correct_answer: {correct_answer!r}")
    return match.group(0).lower()


@dataclass
class ModelResponse:
    pred_letter: str | None
    raw_response: str

    @property
    def parse_status(self) -> str:
        return "valid" if self.pred_letter is not None else "invalid"


def query(
    model: str,
    question: str,
    options: list[str],
    temperature: float,
    num_predict: int = DEFAULT_NUM_PREDICT,
) -> ModelResponse:
    prompt = build_prompt(question, options)
    raw = call_ollama(model, prompt, temperature, num_predict=num_predict)
    return ModelResponse(pred_letter=parse_letter(raw), raw_response=raw)
