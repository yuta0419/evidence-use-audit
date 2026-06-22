# QC notes — Gate 1 corrected re-run (2026-06-22)

`QC_notes_gate1_new_run.md` で発見した2つの欠陥（num_predict=16 truncation、
leading-token parserの"A"冠詞誤検出）を修正し、Gate1を再runした記録。
設計ブロック_0621.md / 研究計画書0621.md は変更しない。

## 修正内容

1. **num_predict**: 16 → 256。`src/study1_mcq/prompting.py` の `call_ollama`/`query` で
   引数化(ハードコード廃止)。primary(temp=0)・stability(temp=0.2×5)・M3すべて同じ値を使用
   (`gate1.py NUM_PREDICT`, `m3_validation.py NUM_PREDICT`)。
2. **parser**: 先頭トークンのみ走査する `parse_letter_v1_leading_token`(旧)を、以下の
   事前固定3階層規則に置換(`parse_letter`、CLAUDE.md #12):
   - (i) "Answer: X" 等の明示的回答文
   - (ii) その行に単一letterしかない行
   - (iii) 応答全体の最終トークンが孤立した単一letterである場合
   - いずれの階層でも複数候補(distinct letter)が出たら invalid（強制的に1つを選ばない）
   - 旧parserは `parse_letter_v1_leading_token` として診断・比較用に保持
3. **raw_output永続化**: 全モデル呼び出しでraw_outputをper-itemに保存するよう
   `gate1.py`/`m3_validation.py` を修正済み(CLAUDE.md #11)。

## 検証: 新旧parser差分(同一raw_outputに両方適用)

589件×2モデル=1178callのraw_outputに `parse_letter_v1_leading_token` と新 `parse_letter` を
両方適用して比較した結果、**差は7件のみ**:

- 6件(llama): v1=invalid → v2=有効なletter。num_predict=16では生成されなかった内容が、
  256まで伸ばしたことで現れ、新parserのtier ii/iiiで回収できた
  (`QC_notes_gate1_new_run.md` で診断した6件の `explanation_with_letter` と同一item)。
- 1件(qwen, item `b4a5fcbd`): raw_outputが `"a, b, c, d"`(全選択肢の列挙、未回答)。
  旧parserは先頭トークン"a"を誤って「選択」と判定していたが、これは複数letterの列挙であり
  単一回答ではない。

### 追加で発見した新parserの実装バグ(列挙ガード漏れ)とその修正

上記の `b4a5fcbd` ケースを精査した結果、tier iiiが「応答全体が単なるletterの列挙
(`"a, b, c, d"`)」を検知できず、機械的に最後のトークン("d")を回答とみなしてしまう
実装漏れを発見した。これは「複数候補があれば invalid」という事前規則(規則4)に反する。

**母集団全体への影響を確認した上で修正**: 1178件のraw_outputすべてに対し
「応答全体が2つ以上のdistinct letterのみで構成される」パターンの有無を確認したところ、
**該当は1178件中1件のみ**(`b4a5fcbd` のqwen応答)。これを確認した上で、tier (i) の直後に
列挙ガードを追加(`prompting.py`)。新規モデル呼び出しなしで、既存raw_outputから該当1件のみ
`qwen_t0_pred` を `d` → invalid に更新し、bucketを `strict_default_error` → `t0_parse_invalid`
に修正した(`gate1_per_item.csv` を直接パッチ、`gate1_summary.json` を再生成)。

## 3者比較(旧baseline / 前回new run(バグ込み) / 今回(修正後))

| | 旧baseline(docs) | 前回new run(num_predict=16, 旧parser) | 今回(num_predict=256, 新parser) |
|---|---:|---:|---:|
| strict_default_error | 266 (45.2%) | 273 (46.3%) | **276 (46.9%)** |
| loose_default_error | 166 (28.2%) | 161 (27.3%) | 161 (27.3%) |
| default_solved | 157 (26.7%) | 144 (24.4%) | 146 (24.8%) |
| t0_parse_invalid | 0 (docsに記載なし) | 11 (1.9%) | **6 (1.0%)** |

sanity gate: 合計589=589 PASS、per-model↔item-level bucket整合性 矛盾0 PASS。

**意外な所見**: 2つのバグを修正しても strict は 273→276 とむしろ微増し、ゼロにはならない
(invalidは11→6に減ったが0にはならない)。これは「バグを直せば旧baselineの266に近づく」という
単純な予想とは異なる。truncation解消によりllamaの「真の最終回答」が明らかになった結果、
一部は元のtruncated/誤検出状態よりむしろ不正解だったため。

## predicted-letter分布の検証(冠詞バグが"a"超過の主因だったか)

| | 前回(バグ込み) | 今回(修正後) |
|---|---:|---:|
| llamaの予測中"a"の割合 | 61.4% | **61.6%(ほぼ不変)** |
| loose_default_errorでllamaが外す割合 | 110/161 (68.3%) | **110/161 (68.3%、不変)** |

**結論: "A"冠詞誤検出バグは実データではほぼ発火していなかった(589件中1178callで影響は
たった1件)。llamaの"a"への強い偏り(61%超)は、parserバグの artifact ではなく、llama3.1:8b
自体の genuine な position bias(選択肢順序バイアス)である可能性が高い。**
事前の仮説(「冠詞バグがa超過の主因」)は、より厳密な検証によって否定された。これは
仮説検証の結果であり、都合の良い結論への誘導ではない。

## type異質性の再現性(バグではなく本物の所見か)

| | 前回(バグ込み) | 今回(修正後) |
|---|---:|---:|
| strict%レンジ | 17.2%〜86.0%(約69pt) | 18.2%〜86.0%(約67.8pt) |
| type-marginal sd(k=7) | 24.2 | 23.8 |
| persona-marginal sd(k=20) | 9.6 | 9.7 |

type-marginal sd > persona-marginal sd は修正前後で変わらず、レンジもほぼ同じ。
**type別異質性はバグの artifact ではなく、頑健な所見と言える。**

## M3外部検証(新strict pool, 276件)

num_predict=256・新parser使用。`m3_solve_rate_on_strict = 0.254(70/276)`、parse_invalid=3。
前回(バグ込み, strict 273件)の `0.238(65/273)` とほぼ同水準。残存(主): 74.6%(206/276)が
27Bでも未解決。修正の有無でM3所見の方向性は変わらない。詳細は `results/study1/m3_summary.json`。

## ファイル構成

- `results/study1/archive_v1_truncation_and_article_bug/`: 修正前(num_predict=16, 旧parser)の
  全結果を保全(gate1_per_item.csv, gate1_summary.json, strict_pool.csv, m3_on_strict.csv,
  m3_summary.json, table_A/B/C.csv, parse_invalid_diagnosis*)。
- `results/study1/`: 修正後(num_predict=256, 新parser, raw_output保存)の現行結果。
