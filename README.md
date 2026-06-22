# evidence-use-audit

personalization 評価の correctness を evidence use と同一視する危険性を、answer format をまたいで
監査する framework。PersonaMem で MCQ の default-solvability を主実証、LongMemEval で open-ended の
sufficiency / contingency を judge-mediated audit する。contingency は threat analysis 扱い。

確定仕様: [`docs/設計ブロック_0621.md`](docs/設計ブロック_0621.md)（prereg 相当）,
[`docs/研究計画書0621.md`](docs/研究計画書0621.md)（上位文書）。不変条件は [`CLAUDE.md`](CLAUDE.md)。

これは1からの新run実験であり、過去フェーズの数値の再現は目的としない。

## Claim boundary

- **言える：** correctness には default-solvable component が含まれ得る（accuracy を evidence use と
  同一視できない）。default-solvability は PersonaMem 内で type 依存。strict の大半は別系列強モデルでも残存。
- **言える：** framework は format-invariant に定義でき、binding constraint が format で変わる。
- **言わない：** strict item が evidence を要求する（L1 射程限界）。
- **言わない：** framework を cross-benchmark / cross-format で validate した（定義の一般性を示すに留め、
  実証の網羅では主張しない）。
- **言わない：** contingency の positive result（2b は threat analysis）。
- **モデル一般化：** 8B×2 + 27B×1。「強モデル一般」には一般化しない。

詳細は [`docs/設計ブロック_0621.md`](docs/設計ブロック_0621.md) §7 を参照。

## 段階構成

- **段階1（本リポジトリの初期状態）**: データ取得（PersonaMem-v1 32k, LongMemEval）と構造検証。
  `src/data_acquisition/`
- **段階2**: Study 1 — PersonaMem MCQ の default-solvability 主実証。`src/study1_mcq/`
- **段階3**: Study 2 — LongMemEval open-ended の sufficiency（2a）/ contingency（2b）judge-mediated
  audit。determinacy filter と judge validation gate を behavioral 実証の前に通す。`src/study2_open/`

## 環境

```
uv sync
```

Python は `uv` で管理する（pip / poetry / conda は使わない）。
