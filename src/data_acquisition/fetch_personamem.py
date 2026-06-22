"""Fetch PersonaMem-v1 32k split from HuggingFace and save to data/.

Saves data/personamem_32k/questions_32k.csv and shared_contexts_32k.jsonl
verbatim, with no row-count assumption.
"""

import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "bowen-upenn/PersonaMem-v1"
FILES = ["questions_32k.csv", "shared_contexts_32k.jsonl"]
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "personamem_32k"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        src = hf_hub_download(REPO_ID, filename, repo_type="dataset")
        dst = OUT_DIR / filename
        shutil.copyfile(src, dst)
        print(f"saved {dst}")


if __name__ == "__main__":
    main()
