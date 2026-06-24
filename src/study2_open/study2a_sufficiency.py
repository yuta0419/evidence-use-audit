"""Study 2a — LongMemEval evidence-only sufficiency runner.

Matched-scaffold C_noev / C_oracle / C_full runner for the human-confirmed
Study 2a main pool (n=20: single-session-user 11 + single-session-assistant 9,
excluding dc439ea3 — see results/0623_study2_judge_gate/study2a_population_decision.json
and docs/QC_notes_study2_judge_gate_human_adjudication_0623.md). The
single-session-preference exploratory set (n=3) and any other item are not
processed unless explicitly requested via --population or --item-ids; the
main pool is never silently expanded (CLAUDE.md / Study 2a brief INVARIANT #2).

Conditions differ only in the context block (src/study2_open/sufficiency_scaffold.py);
everything else (system prompt, question rendering, output instruction,
parsing) is shared. Single generation per (model, condition, item) — this is
open-ended QA, there is no option shuffle.

Primary auditor is gpt-4o-mini (openai backend). llama3.1:8b / qwen2.5:7b
(ollama backend) are deferred-robustness only and may not run condition=full
(long-context failure would confound with the sufficiency question; brief
Phase 5).

Checkpointed JSONL per (model, condition); manifest frozen at run start.
Does not call any API on import — running main() with a real model is the
only thing that spends money. Smoke gate (--smoke N) must be human-reviewed
before a full run (brief Phase 2).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.study2_open.determinacy_filter import load_oracle
from src.study2_open.sufficiency_scaffold import (
    CONTEXT_SCAFFOLD_VERSION,
    build_context_text,
    build_user_prompt,
    parse_answer,
    SYSTEM_PROMPT,
)

SCRIPT_VERSION = "study2a_sufficiency_v1_0623"
REPO_ROOT = Path(__file__).resolve().parents[2]

GATE_DIR = REPO_ROOT / "results" / "0623_study2_judge_gate"
POPULATION_DECISION_PATH = GATE_DIR / "study2a_population_decision.json"
DETERMINACY_PATH = GATE_DIR / "determinacy_filter.csv"
JUDGE_PROMPT_PATH = GATE_DIR / "judge_prompt_v1.md"

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

MODEL_CHOICES = ("gpt-4o-mini", "llama3.1:8b", "qwen2.5:7b")
OPENAI_SNAPSHOT_PIN = "gpt-4o-mini-2024-07-18"
JUDGE_PROMPT_VERSION_REFERENCE = "judge_prompt_v1"

TEMPERATURE = 0.0
TOP_P = 1.0
SEED = 623
MAX_RETRIES = 6
RETRY_BASE_SEC = 2.0
DEFAULT_MAX_TOKENS = 256

SMOKE_ITEM_SEED = 623


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_backend(model: str) -> str:
    return "openai" if model == "gpt-4o-mini" else "ollama"


def openai_model_id(model: str) -> str:
    return OPENAI_SNAPSHOT_PIN if model == "gpt-4o-mini" else model


def default_output_base(model: str) -> Path:
    slug = model.replace(":", "_").replace(".", "").replace("-", "_")
    return REPO_ROOT / "results" / "0623_study2a_sufficiency" / slug


def per_item_path(out_base: Path, condition: str) -> Path:
    return out_base / condition / "per_item.jsonl"


def manifest_path(out_base: Path) -> Path:
    return out_base / "manifest.json"


def load_population(population: str) -> list[str]:
    decision = json.loads(POPULATION_DECISION_PATH.read_text())
    if population == "main":
        return list(decision["main_pool_item_ids"])
    if population == "preference_exploratory":
        return list(decision["preference_exploratory_item_ids"])
    raise ValueError(f"unknown population: {population!r}")


def load_evidence_turn_indices() -> dict[str, list[int]]:
    import csv

    out: dict[str, list[int]] = {}
    with open(DETERMINACY_PATH) as f:
        for row in csv.DictReader(f):
            raw = row["evidence_turn_indices"]
            out[row["question_id"]] = json.loads(raw) if raw else []
    return out


def load_done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    with open(path) as f:
        for line in f:
            if line.strip():
                done.add(json.loads(line)["item_id"])
    return done


def smoke_item_ids(all_ids: list[str], n: int) -> list[str]:
    rng = __import__("random").Random(SMOKE_ITEM_SEED)
    ids = sorted(all_ids)
    return rng.sample(ids, k=min(n, len(ids)))


def call_openai_with_retry(model: str, system_prompt: str, user_prompt: str, api_key: str, seed: int) -> tuple[str, dict]:
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
                    "max_tokens": DEFAULT_MAX_TOKENS,
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


def call_ollama_with_retry(model: str, system_prompt: str, user_prompt: str, seed: int) -> tuple[str, dict]:
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
                        "num_predict": DEFAULT_MAX_TOKENS,
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


def run_model_call(backend: str, model: str, system_prompt: str, user_prompt: str, api_key: str | None, seed: int) -> tuple[str, dict]:
    if backend == "openai":
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for openai backend")
        return call_openai_with_retry(openai_model_id(model), system_prompt, user_prompt, api_key, seed)
    if backend == "ollama":
        return call_ollama_with_retry(model, system_prompt, user_prompt, seed)
    raise ValueError(f"unknown backend: {backend!r}")


def process_item(
    item: dict,
    *,
    condition: str,
    evidence_turn_indices: list[int],
    backend: str,
    model: str,
    api_key: str | None,
    seed: int,
) -> tuple[dict, dict]:
    context_text = build_context_text(item, condition, evidence_turn_indices)
    user_prompt = build_user_prompt(condition=condition, question=item["question"], context_text=context_text)

    raw, usage = run_model_call(backend, model, SYSTEM_PROMPT, user_prompt, api_key, seed)
    parsed_answer, parse_status = parse_answer(raw)

    record = {
        "item_id": item["question_id"],
        "question_type": item["question_type"],
        "model": model,
        "condition": condition,
        "context_block_present": condition != "noev",
        "raw_output": raw,
        "parsed_answer": parsed_answer,
        "parse_status": parse_status,
        "usage": usage,
    }
    return record, usage


def write_manifest(
    out_base: Path,
    *,
    model: str,
    backend: str,
    population: str,
    item_ids: list[str],
    conditions: list[str],
    seed: int,
    snapshot_checked_at: str,
) -> None:
    manifest = {
        "script_version": SCRIPT_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "study": "study2a_sufficiency_longmemeval",
        "population": population,
        "n_items_target": len(item_ids),
        "item_ids": sorted(item_ids),
        "model": model,
        "model_backend": backend,
        "openai_snapshot_pin": openai_model_id(model) if backend == "openai" else None,
        "snapshot_checked_at_utc": snapshot_checked_at if backend == "openai" else None,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "seed": seed,
        "n_generations_per_item": 1,
        "context_scaffold_version": CONTEXT_SCAFFOLD_VERSION,
        "conditions_run": conditions,
        "judge_prompt_version_reference": JUDGE_PROMPT_VERSION_REFERENCE,
        "judge_prompt_path": str(JUDGE_PROMPT_PATH.relative_to(REPO_ROOT)),
        "judge_not_run_by_this_script": True,
        "inputs": {
            "longmemeval_oracle.json": {
                "path": "data/longmemeval/longmemeval_oracle.json",
                "sha256": file_sha256(REPO_ROOT / "data" / "longmemeval" / "longmemeval_oracle.json"),
            },
            "determinacy_filter.csv": {
                "path": str(DETERMINACY_PATH.relative_to(REPO_ROOT)),
                "sha256": file_sha256(DETERMINACY_PATH),
            },
            "study2a_population_decision.json": {
                "path": str(POPULATION_DECISION_PATH.relative_to(REPO_ROOT)),
                "sha256": file_sha256(POPULATION_DECISION_PATH),
            },
        },
        "parser": "src.study2_open.sufficiency_scaffold.parse_answer",
        "output_schema": "per_item.jsonl",
    }
    out_base.mkdir(parents=True, exist_ok=True)
    manifest_path(out_base).write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_smoke_prompt_dump(item: dict, evidence_turn_indices: list[int], out_path: Path) -> None:
    dump = {"item_id": item["question_id"], "system_prompt": SYSTEM_PROMPT, "prompts_by_condition": {}}
    for condition in ("noev", "oracle", "full"):
        context_text = build_context_text(item, condition, evidence_turn_indices)
        user_prompt = build_user_prompt(condition=condition, question=item["question"], context_text=context_text)
        dump["prompts_by_condition"][condition] = {
            "context_text_chars": len(context_text),
            "user_prompt": user_prompt,
        }
    dump["note"] = "Verify: noev omits the context block entirely; oracle/full share the same template and differ only in context_text coverage."
    out_path.write_text(json.dumps(dump, ensure_ascii=False, indent=2))


def run(args: argparse.Namespace) -> dict:
    backend = model_backend(args.model)
    if backend == "ollama" and "full" in args.conditions:
        raise SystemExit(
            f"condition=full is not allowed for ollama model {args.model!r}: deferred-robustness models "
            "(llama3.1:8b, qwen2.5:7b) are C_oracle/C_noev only (Study 2a brief INVARIANT #4; long-context "
            "failure for C_full would confound with the sufficiency question)."
        )

    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY") if backend == "openai" else None
    if backend == "openai" and not api_key:
        raise SystemExit("OPENAI_API_KEY not set. Stopping before any API call.")

    snapshot_checked_at = datetime.now(timezone.utc).isoformat()
    out_base = Path(args.output_dir) if args.output_dir else default_output_base(args.model)

    item_ids = load_population(args.population) if not args.item_ids else list(args.item_ids)
    evidence_turn_indices_by_id = load_evidence_turn_indices()

    oracle_items = {it["question_id"]: it for it in load_oracle()}
    target_items = [oracle_items[qid] for qid in item_ids]

    if args.smoke:
        smoke_ids = set(smoke_item_ids(item_ids, args.smoke))
        target_items = [it for it in target_items if it["question_id"] in smoke_ids]
        print(f"smoke mode: {len(target_items)} items")

    write_manifest(
        out_base,
        model=args.model,
        backend=backend,
        population=args.population,
        item_ids=item_ids,
        conditions=args.conditions,
        seed=args.seed,
        snapshot_checked_at=snapshot_checked_at,
    )

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    parse_valid = 0
    total_calls = 0
    smoke_prompt_path = out_base / "smoke_prompt_pair.json"

    for condition in args.conditions:
        out_path = per_item_path(out_base, condition)
        done = load_done_ids(out_path)
        n_cond = len(target_items)

        for i, item in enumerate(target_items, start=1):
            item_id = item["question_id"]
            if item_id in done:
                continue

            if args.smoke and condition == args.conditions[0] and not smoke_prompt_path.exists():
                build_smoke_prompt_dump(item, evidence_turn_indices_by_id.get(item_id, []), smoke_prompt_path)

            record, usage = process_item(
                item,
                condition=condition,
                evidence_turn_indices=evidence_turn_indices_by_id.get(item_id, []),
                backend=backend,
                model=args.model,
                api_key=api_key,
                seed=args.seed,
            )
            append_record(out_path, record)

            total_calls += 1
            if record["parse_status"] == "valid":
                parse_valid += 1
            for k in total_usage:
                total_usage[k] += int(usage.get(k, 0) or 0)

            print(f"  [{condition}] {i}/{n_cond} item_id={item_id} parse_status={record['parse_status']}")

    return {
        "out_base": str(out_base),
        "parse_valid_rate": parse_valid / total_calls if total_calls else 0.0,
        "total_calls": total_calls,
        "usage": total_usage,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Study 2a matched-scaffold C_noev/C_oracle/C_full runner")
    p.add_argument("--model", required=True, choices=MODEL_CHOICES)
    p.add_argument("--condition", choices=["noev", "oracle", "full", "all"], default="all")
    p.add_argument("--population", choices=["main", "preference_exploratory"], default="main")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--smoke", type=int, default=0, metavar="N", help="run N items only (smoke gate)")
    p.add_argument("--item-ids", nargs="+", help="explicit item ids (overrides --population)")
    p.add_argument("--output-dir", type=Path, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.conditions = ["noev", "oracle", "full"] if args.condition == "all" else [args.condition]
    summary = run(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
