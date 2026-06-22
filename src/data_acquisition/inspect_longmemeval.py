"""Basic structural inspection of LongMemEval (cleaned).

Reports item count and question_type distribution per split only.
No determinacy filter, no judge logic — those belong to stage 3
(src/study2_open/).
"""

import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "longmemeval"
SPLITS = [
    "longmemeval_s_cleaned.json",
    "longmemeval_m_cleaned.json",
    "longmemeval_oracle.json",
]


def main() -> None:
    for filename in SPLITS:
        path = DATA_DIR / filename
        items = json.loads(path.read_text())
        type_counts = Counter(item["question_type"] for item in items)

        print(f"--- {filename} ---")
        print(f"item count: {len(items)}")
        for qtype, count in type_counts.most_common():
            print(f"  {qtype}: {count}")


if __name__ == "__main__":
    main()
