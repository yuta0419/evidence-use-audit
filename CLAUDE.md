# CLAUDE.md

このリポジトリは personalization benchmark の evidence-use audit 研究用。
確定仕様は [`docs/設計ブロック_0621.md`](docs/設計ブロック_0621.md)（prereg 相当）と
[`docs/研究計画書0621.md`](docs/研究計画書0621.md)（上位文書）。矛盾があれば上記2文書が優先する。

これは1からの新run実験である。過去フェーズの数値（旧 strict 266/589 等）の再現は目的としない。
仕様にないことはやらない。気を利かせた拡張・推測補完はしない。重厚な構成にしない。

## 不変条件（load-bearing。違反する実装は将来のセッションでも破棄する）

1. 段階的に組む。Study 2 の behavioral 実装（2a/2b）を、judge validation gate を通す前に作らない。
2. judge validation gate は behavioral 実証の「前」に置く。gate 未通過の層は behavioral claim から除外。
3. determinacy filter は Study 2a/2b の母集団選別の「前」に置く。
4. M3（第3モデル）を strict の定義に組み込まない。strict は2モデルのANDで固定。strict_3 を作らない。
5. strict プールは一度確定したら凍結。後続の検証は別指標として report する。
6. 5990（全split）を headline / 主結果にしない。主実証は 32k = 589。5990 は coverage extension のみ。
7. cluster=20（全split が同一20persona）。persona 単位の推論統計を載せない。差は descriptive のみ。
8. 因果方向に踏み込まない。strict = "question + options で解けない" までで、"evidence を要求する" とは書かない。
9. `C_default` = question + native options only（persona profile / shared context / retrieved memory /
   evidence snippet を一切入れない）。
10. 新run前提。sanity gate は件数の固定値（266 等）を要求しない。合計・整合・invalid 数のみ検証し、
    strict 件数は出た値を記録する。旧baseline（strict 266/589）は docs に記録として残し、新run値と並記する。
11. モデルを呼ぶ実行は必ず raw_output（生テキスト）を per-item に保存する。pred_letter だけを残して
    raw_output を捨てない。保存されていない raw_output は事後に新規モデル呼び出しなしで復元できない
    （2026-06-22, Gate1 new run の parse_invalid 11件調査で発覚した欠陥。詳細は
    `results/study1/parse_invalid_diagnosis_summary.json`）。
12. parser のルールを事後に緩めて、特定の invalid/error item を都合よく回収しない。ルールを変更する
    場合は変更内容を明文化し、その変更が母集団全体（影響を受けない既存件のbucketも含む）に与える
    影響を確認してから適用する。確認できない場合はルールを変更しない。
13. APIキーをコード・ログ・出力に含めない。`.env` は Git管理しない。

## ディレクトリ構造（この通り。増やさない）

```
repo/
  README.md
  CLAUDE.md
  docs/            # 確定文書
  data/            # 取得データ。.gitignore 対象
  src/
    data_acquisition/
    study1_mcq/    # 段階2
    study2_open/   # 段階3
  results/
  tests/
```

## 段階構成

- 段階1: データ取得・構造検証（`src/data_acquisition/`）
- 段階2: Study 1 — PersonaMem MCQ default-solvability（`src/study1_mcq/`）
- 段階3: Study 2 — LongMemEval open-ended sufficiency/contingency audit（`src/study2_open/`）

各段階は前段階が完了するまで着手しない。

## 環境

- Python は `uv` で管理する（pip / poetry / conda は使わない）。
- 依存追加は `uv add`。
- 依存は最小限。`datasets`（HuggingFace）と標準ライブラリ中心。重いフレームワークを足さない。
