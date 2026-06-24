"""Matched-scaffold prompt construction for Study 2a (LongMemEval evidence sufficiency).

C_noev / C_oracle / C_full differ ONLY in the context block: system prompt,
question rendering, output instruction, and parsing are shared verbatim across
all three conditions (see docs/0623 Study 2a brief, INVARIANT CONSTRAINTS #1).

  - C_noev:   no context block at all (the line is omitted, not blanked).
  - C_oracle: only the has_answer-flagged gold turn(s), reusing
              determinacy_filter.evidence_text_from_item (frozen at the judge
              gate stage; not redefined here).
  - C_full:   every turn of the item's single haystack session, serialized
              with the same "role: content" format as the oracle span so the
              only difference between conditions is how much of that format
              is shown, not the format itself.

This is open-ended QA (LongMemEval), not MCQ: there are no options and no
option shuffle (unlike src/study1_mcq/matched_scaffold.py, which this module
intentionally does not reuse).
"""

from src.study2_open.determinacy_filter import evidence_text_from_item

CONTEXT_SCAFFOLD_VERSION = "v1_role_content_join"

SYSTEM_PROMPT = """You are answering a question about a prior conversation. If conversation
context is provided below, use only that context; do not invent details it does not contain.
If no context is provided, answer using only the question itself.
Respond with exactly one line in this format:
Answer: <your answer>
Output only that line. Do not explain your reasoning."""

CONTEXT_BLOCK_TEMPLATE = """The following is the relevant conversation context:
{context_text}

"""

USER_PROMPT_TEMPLATE = """{context_block}Question:
{question}

Answer with a single concise response."""


def full_session_text_from_item(item: dict) -> str:
    """Verbatim text of every turn in the item's single haystack session.

    Single-session-only (CLAUDE.md / Study 2a population: main pool and the
    preference-exploratory set are all single-session items). Uses the same
    "role: content" join as evidence_text_from_item so C_full and C_oracle
    differ only in turn coverage, not formatting.
    """
    session = item["haystack_sessions"][0]
    return "\n".join(f"{t['role']}: {t['content']}" for t in session)


def build_context_text(item: dict, condition: str, evidence_turn_indices: list[int]) -> str:
    if condition == "noev":
        return ""
    if condition == "oracle":
        return evidence_text_from_item(item, evidence_turn_indices)
    if condition == "full":
        return full_session_text_from_item(item)
    raise ValueError(f"unknown condition: {condition!r}")


def build_user_prompt(*, condition: str, question: str, context_text: str) -> str:
    context_block = ""
    if condition != "noev":
        context_block = CONTEXT_BLOCK_TEMPLATE.format(context_text=context_text)
    elif condition not in ("noev", "oracle", "full"):
        raise ValueError(f"unknown condition: {condition!r}")
    return USER_PROMPT_TEMPLATE.format(context_block=context_block, question=question)


def parse_answer(raw_output: str) -> tuple[str | None, str]:
    """Extract the answer text following an "Answer:" line.

    Returns (answer_text_or_None, parse_status). parse_status is one of:
    "valid" (an "Answer:" line was found), "empty" (raw_output is blank),
    "unparsed" (non-empty output, no "Answer:" line found — the full
    raw_output is still preserved for judge scoring per CLAUDE.md #11; never
    discarded).
    """
    text = raw_output.strip()
    if not text:
        return None, "empty"
    for line in text.split("\n"):
        line = line.strip()
        if line.lower().startswith("answer:"):
            return line[len("answer:"):].strip(), "valid"
    return None, "unparsed"
