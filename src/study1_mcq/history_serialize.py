"""Conversation history serialization for matched-scaffold C_full.

v1_content_only (frozen): join raw turn content with newlines only.
No turn index, no added role prefix — content already carries User:/Assistant:.
"""

import json
from pathlib import Path

HISTORY_SERIALIZER_VERSION = "v1_content_only"

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTEXTS_PATH = REPO_ROOT / "data" / "personamem_32k" / "shared_contexts_32k.jsonl"


def load_contexts(path: Path = CONTEXTS_PATH) -> dict:
    contexts: dict = {}
    with open(path) as f:
        for line in f:
            contexts.update(json.loads(line))
    return contexts


def history_turns(contexts: dict, shared_context_id: str, end_index: int) -> list[dict]:
    full = contexts[shared_context_id]
    return full[: min(end_index + 1, len(full))]


def serialize_history_v1(contexts: dict, shared_context_id: str, end_index: int) -> str:
    turns = history_turns(contexts, shared_context_id, end_index)
    return "\n".join(turn["content"] for turn in turns)
