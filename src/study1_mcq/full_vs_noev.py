"""Matched-scaffold C_full vs C_noev runner (gpt-4o-mini and local ollama).

C_full and C_noev differ only by history_block presence. Single script,
--condition {full,noev}. Checkpointed JSONL per item; manifest frozen at run start.

Smoke gate: use --smoke 10 and stop for human review before full 589×3×2 run.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from src.study1_mcq.canonical_types import to_canonical
from src.study1_mcq.history_serialize import HISTORY_SERIALIZER_VERSION, load_contexts
from src.study1_mcq.matched_scaffold import (
    build_prompts_for_item,
    build_user_prompt,
    build_shuffle_layout,
    canonical_option_texts,
    display_letter_to_canonical,
)
from src.study1_mcq.prompting import DEFAULT_NUM_PREDICT, gold_letter, parse_letter

SCRIPT_VERSION = "full_vs_noev_v1_0623"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = REPO_ROOT / "data" / "personamem_32k" / "questions_32k.csv"
CONTEXTS_PATH = REPO_ROOT / "data" / "personamem_32k" / "shared_contexts_32k.jsonl"

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

DEFAULT_OPENAI_MODEL = "gpt-4o-mini-2024-07-18"
OLLAMA_MODELS = {"llama": "llama3.1:8b", "qwen": "qwen2.5:7b"}

N_SHUFFLES = 3
TEMPERATURE = 0.0
TOP_P = 1.0
SEED = 623
MAX_RETRIES = 6
RETRY_BASE_SEC = 2.0

SMOKE_ITEM_SEED = 623


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_output_base(model: str, backend: str) -> Path:
    if backend == "openai" and "gpt-4o-mini" in model:
        return REPO_ROOT / "results" / "full_vs_noev_gpt4omini_32k"
    slug = model.replace(":", "_").replace(".", "").replace("-", "_")
    return REPO_ROOT / "results" / f"full_vs_noev_matched_{slug}_32k"


def per_item_path(out_base: Path, condition: str) -> Path:
    return out_base / condition / "per_item.jsonl"


def manifest_path(out_base: Path) -> Path:
    return out_base / "manifest.json"


def load_done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    with open(path) as f:
        for line in f:
            if line.strip():
                done.add(json.loads(line)["item_id"])
    return done


def smoke_item_ids(df: pd.DataFrame, n: int) -> list[str]:
    rng = __import__("random").Random(SMOKE_ITEM_SEED)
    ids = sorted(df["question_id"].astype(str).tolist())
    return rng.sample(ids, k=min(n, len(ids)))


def majority_canonical(choices: list[str | None]) -> tuple[str | None, str]:
    valid = [c for c in choices if c is not None]
    if not valid:
        return None, "invalid"
    top, count = Counter(valid).most_common(1)[0]
    if count >= 2:
        return top, "valid"
    return None, "split"


def call_openai_with_retry(
    model: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    seed: int,
) -> tuple[str, dict]:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "seed": seed,
                    "max_tokens": DEFAULT_NUM_PREDICT,
                },
                timeout=300,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return raw, usage
        except Exception as exc:
            last_err = exc
            time.sleep(RETRY_BASE_SEC * (2**attempt))
    raise RuntimeError(f"OpenAI call failed after {MAX_RETRIES} retries") from last_err


def call_ollama_with_retry(
    model: str,
    system_prompt: str,
    user_prompt: str,
    seed: int,
) -> tuple[str, dict]:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": TEMPERATURE,
                        "top_p": TOP_P,
                        "num_predict": DEFAULT_NUM_PREDICT,
                        "seed": seed,
                    },
                },
                timeout=300,
            )
            if resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            data = resp.json()
            raw = data["message"]["content"]
            return raw, {}
        except Exception as exc:
            last_err = exc
            time.sleep(RETRY_BASE_SEC * (2**attempt))
    raise RuntimeError(f"Ollama call failed after {MAX_RETRIES} retries") from last_err


def run_shuffle_call(
    backend: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str | None,
    seed: int,
) -> tuple[str, dict]:
    if backend == "openai":
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for openai backend")
        return call_openai_with_retry(model, system_prompt, user_prompt, api_key, seed)
    if backend == "ollama":
        return call_ollama_with_retry(model, system_prompt, user_prompt, seed)
    raise ValueError(f"unknown backend: {backend!r}")


def process_item(
    row: pd.Series,
    *,
    condition: str,
    contexts: dict,
    backend: str,
    model: str,
    api_key: str | None,
    seed: int,
) -> tuple[dict, list[dict]]:
    item_id = str(row["question_id"])
    question = row["user_question_or_message"]
    native_options = ast.literal_eval(row["all_options"])
    gold = gold_letter(row["correct_answer"])
    canonical_type = to_canonical(row["question_type"])
    shared_context_id = row["shared_context_id"]
    end_index = int(row["end_index_in_shared_context"])

    prompt_triples = build_prompts_for_item(
        condition=condition,
        question=question,
        native_options=native_options,
        item_id=item_id,
        seed=seed,
        n_shuffles=N_SHUFFLES,
        contexts=contexts,
        shared_context_id=shared_context_id,
        end_index=end_index,
    )

    shuffle_records: list[dict] = []
    usage_records: list[dict] = []
    canonical_choices: list[str | None] = []

    for layout, system_prompt, user_prompt in prompt_triples:
        raw, usage = run_shuffle_call(
            backend,
            model,
            system_prompt,
            user_prompt,
            api_key,
            seed + layout.shuffle_idx,
        )
        usage_records.append(usage)
        parsed_display = parse_letter(raw)
        canonical_choice = None
        if parsed_display is not None:
            canonical_choice = display_letter_to_canonical(parsed_display, layout.display_order)
        canonical_choices.append(canonical_choice)

        shuffle_records.append(
            {
                "shuffle_idx": layout.shuffle_idx,
                "display_order": layout.display_order,
                "raw_output": raw,
                "parsed_letter": parsed_display.upper() if parsed_display else None,
                "canonical_choice": canonical_choice,
                "is_gold": canonical_choice == gold if canonical_choice else False,
                "parse_status": "valid" if parsed_display is not None else "invalid",
            }
        )

    maj_canonical, maj_status = majority_canonical(canonical_choices)
    record = {
        "item_id": item_id,
        "question_type": canonical_type,
        "persona_id": str(row["persona_id"]),
        "condition": condition,
        "gold_key": gold,
        "shuffles": shuffle_records,
        "majority_canonical": maj_canonical,
        "majority_is_gold": maj_canonical == gold if maj_canonical else False,
        "parse_status_majority": maj_status,
    }
    return record, usage_records


def write_manifest(
    out_base: Path,
    *,
    model: str,
    backend: str,
    conditions: list[str],
    seed: int,
    snapshot_checked_at: str,
) -> None:
    manifest = {
        "script_version": SCRIPT_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "split": "32k",
        "n_items_target": 589,
        "k_options": 4,
        "model": model,
        "model_backend": backend,
        "openai_snapshot_pin": model if backend == "openai" else None,
        "snapshot_checked_at_utc": snapshot_checked_at if backend == "openai" else None,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "seed": seed,
        "n_shuffles": N_SHUFFLES,
        "history_serializer": HISTORY_SERIALIZER_VERSION,
        "conditions_run": conditions,
        "inputs": {
            "questions_32k.csv": {
                "path": str(QUESTIONS_PATH.relative_to(REPO_ROOT)),
                "sha256": file_sha256(QUESTIONS_PATH),
            },
            "shared_contexts_32k.jsonl": {
                "path": str(CONTEXTS_PATH.relative_to(REPO_ROOT)),
                "sha256": file_sha256(CONTEXTS_PATH),
            },
        },
        "parser": "prompting.parse_letter (Gate1 frozen)",
        "output_schema": "per_item.jsonl",
    }
    out_base.mkdir(parents=True, exist_ok=True)
    manifest_path(out_base).write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_smoke_prompt_dump(
    row: pd.Series,
    contexts: dict,
    out_path: Path,
    seed: int,
) -> None:
    item_id = str(row["question_id"])
    question = row["user_question_or_message"]
    native_options = ast.literal_eval(row["all_options"])
    canonical_texts = canonical_option_texts(native_options)
    layout = build_shuffle_layout(item_id, 0, seed, canonical_texts)

    from src.study1_mcq.history_serialize import serialize_history_v1

    serialized = serialize_history_v1(
        contexts,
        row["shared_context_id"],
        int(row["end_index_in_shared_context"]),
    )
    full_user = build_user_prompt(
        condition="full",
        question=question,
        layout=layout,
        serialized_history=serialized,
    )
    noev_user = build_user_prompt(
        condition="noev",
        question=question,
        layout=layout,
        serialized_history="",
    )

    from src.study1_mcq.matched_scaffold import SYSTEM_PROMPT

    dump = {
        "item_id": item_id,
        "system_prompt": SYSTEM_PROMPT,
        "full_user_prompt": full_user,
        "noev_user_prompt": noev_user,
        "history_serializer": HISTORY_SERIALIZER_VERSION,
        "serialized_history_chars": len(serialized),
        "note": "Verify: noev omits history_block entirely; otherwise identical.",
    }
    out_path.write_text(json.dumps(dump, ensure_ascii=False, indent=2))


def run(args: argparse.Namespace) -> dict:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY") if args.model_backend == "openai" else None
    if args.model_backend == "openai" and not api_key:
        raise SystemExit("OPENAI_API_KEY not set. Stopping before any API call.")

    snapshot_checked_at = datetime.now(timezone.utc).isoformat()
    out_base = Path(args.output_dir) if args.output_dir else default_output_base(args.model, args.model_backend)
    conditions = args.conditions
    write_manifest(
        out_base,
        model=args.model,
        backend=args.model_backend,
        conditions=conditions,
        seed=args.seed,
        snapshot_checked_at=snapshot_checked_at,
    )

    df = pd.read_csv(QUESTIONS_PATH)
    contexts = load_contexts()

    if args.item_ids:
        target_ids = set(args.item_ids)
        df = df[df["question_id"].astype(str).isin(target_ids)]
    elif args.smoke:
        smoke_ids = smoke_item_ids(df, args.smoke)
        df = df[df["question_id"].astype(str).isin(smoke_ids)]
        print(f"smoke mode: {len(smoke_ids)} items")

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    parse_valid_shuffles = 0
    total_shuffles = 0
    smoke_prompt_path = out_base / "smoke_prompt_pair.json"

    for condition in conditions:
        out_path = per_item_path(out_base, condition)
        done = load_done_ids(out_path)
        n_cond = len(df)

        for i, (_, row) in enumerate(df.iterrows(), start=1):
            item_id = str(row["question_id"])
            if item_id in done:
                continue

            if args.smoke and condition == conditions[0] and not smoke_prompt_path.exists():
                build_smoke_prompt_dump(row, contexts, smoke_prompt_path, args.seed)

            record, usages = process_item(
                row,
                condition=condition,
                contexts=contexts,
                backend=args.model_backend,
                model=args.model,
                api_key=api_key,
                seed=args.seed,
            )
            append_record(out_path, record)

            for sh in record["shuffles"]:
                total_shuffles += 1
                if sh["parse_status"] == "valid":
                    parse_valid_shuffles += 1
            for u in usages:
                for k in total_usage:
                    total_usage[k] += int(u.get(k, 0) or 0)

            print(f"  [{condition}] {i}/{n_cond} item_id={item_id[:8]}... majority={record['majority_canonical']}")

    return {
        "out_base": str(out_base),
        "parse_valid_rate": parse_valid_shuffles / total_shuffles if total_shuffles else 0.0,
        "total_shuffles": total_shuffles,
        "usage": total_usage,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Matched-scaffold C_full vs C_noev runner")
    p.add_argument("--condition", choices=["full", "noev", "both"], default="both")
    p.add_argument("--model-backend", choices=["openai", "ollama"], default="openai")
    p.add_argument("--model", default=DEFAULT_OPENAI_MODEL)
    p.add_argument("--ollama-alias", choices=["llama", "qwen"], help="shortcut for --model-backend ollama")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--smoke", type=int, default=0, metavar="N", help="run N items only (smoke gate)")
    p.add_argument("--item-ids", nargs="+", help="explicit item ids")
    p.add_argument("--output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.ollama_alias:
        args.model_backend = "ollama"
        args.model = OLLAMA_MODELS[args.ollama_alias]
    if args.condition == "both":
        args.conditions = ["full", "noev"]
    else:
        args.conditions = [args.condition]

    summary = run(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
