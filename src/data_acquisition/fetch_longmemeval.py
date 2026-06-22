"""Fetch LongMemEval (cleaned) from HuggingFace and save to data/.

xiaowu0162/longmemeval-cleaned ships three splits (s_cleaned, m_cleaned,
oracle); all three are saved verbatim under data/longmemeval/.
"""

import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "xiaowu0162/longmemeval-cleaned"
FILES = [
    "longmemeval_s_cleaned.json",
    "longmemeval_m_cleaned.json",
    "longmemeval_oracle.json",
]
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "longmemeval"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        src = hf_hub_download(REPO_ID, filename, repo_type="dataset")
        dst = OUT_DIR / filename
        shutil.copyfile(src, dst)
        print(f"saved {dst}")


if __name__ == "__main__":
    main()
