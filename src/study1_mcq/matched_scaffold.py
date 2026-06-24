"""Matched-scaffold prompt, option shuffle, and letter mapping for C_full / C_noev."""

import hashlib
import random
import re
from dataclasses import dataclass

from src.study1_mcq.history_serialize import serialize_history_v1

_NATIVE_PREFIX_RE = re.compile(r"^\([a-dA-D]\)\s*")
DISPLAY_LETTERS = ("A", "B", "C", "D")

SYSTEM_PROMPT = """You are answering a multiple-choice question. Read the information provided and
select the single best option. Respond with exactly one line in this format:
Answer: <LETTER>
where <LETTER> is one of A, B, C, D. Output only that line. Do not explain."""

HISTORY_BLOCK_TEMPLATE = """The following is the prior conversation history with this user:
{serialized_history}

"""

USER_PROMPT_TEMPLATE = """{history_block}Question:
{question}

Options:
A. {option_A}
B. {option_B}
C. {option_C}
D. {option_D}

Answer with a single letter (A, B, C, or D)."""


def strip_native_prefix(option: str) -> str:
    return _NATIVE_PREFIX_RE.sub("", option.strip(), count=1)


def canonical_option_texts(native_options: list[str]) -> list[str]:
    return [strip_native_prefix(o) for o in native_options]


def stable_shuffle_seed(item_id: str, shuffle_idx: int, seed: int) -> int:
    digest = hashlib.sha256(f"{item_id}:{shuffle_idx}:{seed}".encode()).hexdigest()
    return int(digest[:16], 16) ^ seed


def display_order_for_shuffle(item_id: str, shuffle_idx: int, seed: int) -> list[int]:
    rng = random.Random(stable_shuffle_seed(item_id, shuffle_idx, seed))
    order = [0, 1, 2, 3]
    rng.shuffle(order)
    return order


def display_letter_to_canonical(display_letter: str, display_order: list[int]) -> str:
    pos = ord(display_letter.lower()) - ord("a")
    if pos not in range(4):
        raise ValueError(f"display letter out of range: {display_letter!r}")
    canonical_idx = display_order[pos]
    return chr(ord("a") + canonical_idx)


@dataclass
class ShuffleLayout:
    shuffle_idx: int
    display_order: list[int]
    option_A: str
    option_B: str
    option_C: str
    option_D: str


def build_shuffle_layout(
    item_id: str,
    shuffle_idx: int,
    seed: int,
    canonical_texts: list[str],
) -> ShuffleLayout:
    order = display_order_for_shuffle(item_id, shuffle_idx, seed)
    display_texts = [canonical_texts[i] for i in order]
    return ShuffleLayout(
        shuffle_idx=shuffle_idx,
        display_order=order,
        option_A=display_texts[0],
        option_B=display_texts[1],
        option_C=display_texts[2],
        option_D=display_texts[3],
    )


def build_user_prompt(
    *,
    condition: str,
    question: str,
    layout: ShuffleLayout,
    serialized_history: str = "",
) -> str:
    history_block = ""
    if condition == "full":
        history_block = HISTORY_BLOCK_TEMPLATE.format(serialized_history=serialized_history)
    elif condition != "noev":
        raise ValueError(f"unknown condition: {condition!r}")

    return USER_PROMPT_TEMPLATE.format(
        history_block=history_block,
        question=question,
        option_A=layout.option_A,
        option_B=layout.option_B,
        option_C=layout.option_C,
        option_D=layout.option_D,
    )


def build_prompts_for_item(
    *,
    condition: str,
    question: str,
    native_options: list[str],
    item_id: str,
    seed: int,
    n_shuffles: int,
    contexts: dict,
    shared_context_id: str,
    end_index: int,
) -> list[tuple[ShuffleLayout, str, str]]:
    canonical_texts = canonical_option_texts(native_options)
    serialized_history = ""
    if condition == "full":
        serialized_history = serialize_history_v1(contexts, shared_context_id, end_index)

    out: list[tuple[ShuffleLayout, str, str]] = []
    for shuffle_idx in range(n_shuffles):
        layout = build_shuffle_layout(item_id, shuffle_idx, seed, canonical_texts)
        user_prompt = build_user_prompt(
            condition=condition,
            question=question,
            layout=layout,
            serialized_history=serialized_history,
        )
        out.append((layout, SYSTEM_PROMPT, user_prompt))
    return out
