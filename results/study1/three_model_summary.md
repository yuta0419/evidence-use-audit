# Study 1 — 3モデル比較まとめ（C_default, n=589）

条件: `C_default` = question + native options only（履歴・persona・shared context なし）。
temp=0。parser は Gate1 修正後の `parse_letter`（3階層規則）。`max_tokens`/`num_predict`=256。

| モデル | 系列 | 役割 |
|--------|------|------|
| llama3.1:8b | ローカル小型 | strict 定義の構成モデル（2モデル AND） |
| qwen2.5:7b | ローカル小型 | strict 定義の構成モデル（2モデル AND） |
| gpt-4o-mini | 商用 API | 独立参考測定（strict 定義には組み込まない） |

データ源:
- llama / qwen / 2モデル bucket: `results/study1/gate1_per_item.csv`, `gate1_summary.json`
- gpt-4o-mini: `results/study1/gpt4o_mini_no_history_589.csv`, `gpt4o_mini_no_history_589_summary.json`

---

## 表1. 全体（589件）— モデル単体の正答率

| モデル | 正解 | 不正解 | parse invalid | 正答率 |
|--------|-----:|-------:|--------------:|-------:|
| llama3.1:8b | 197 | 387 | 5 | **33.4%** |
| qwen2.5:7b | 257 | 331 | 1 | **43.6%** |
| gpt-4o-mini | 208 | 381 | 0 | **35.3%** |

※ 4択 MCQ の単体ランダム期待値は 25%。3モデルともこれを上回る。

---

## 表2. 全体（589件）— llama + qwen の item-level bucket（Gate1 主結果）

strict の定義は **llama と qwen の AND**（両方とも temp=0 で gold を外す）。GPT-4o-mini は含まない。

| bucket | 件数 | 割合 | 定義 |
|--------|-----:|-----:|------|
| strict_default_error | 276 | 46.9% | 両モデルとも外す |
| loose_default_error | 161 | 27.3% | 片方のみ外す |
| default_solved | 146 | 24.8% | 両モデルとも正解 |
| t0_parse_invalid | 6 | 1.0% | いずれかが parse 不能 |
| **合計** | **589** | **100%** | |

補足:
- 両モデル同時正解 24.8% のランダム期待値（独立・4択）は **6.25%**（0.25²）。単体 25% とは比較対象が異なる。
- loose 161件のうち llama 側が外す: 110件（68.3%）。qwen 側が外す: 51件。

---

## 表3. strict pool（276件）上での各モデル正答率

strict pool = llama + qwen の AND で凍結した母集団。

| モデル | 正解 | 正答率 | 備考 |
|--------|-----:|-------:|------|
| llama3.1:8b | 0 / 276 | 0.0% | strict 定義上、定義どおり 0% |
| qwen2.5:7b | 0 / 276 | 0.0% | strict 定義上、定義どおり 0% |
| gpt-4o-mini | 31 / 276 | **11.2%** | 独立参考。strict を再定義しない |
| gemma2:27b（M3） | 70 / 276 | 25.4% | 別系列・strict pool のみ実行（参考） |

---

## 表4. canonical_type 別 — モデル単体正答率（%）

| canonical_type | n | llama3.1:8b | qwen2.5:7b | gpt-4o-mini | strict%（llama+qwen） |
|----------------|--:|------------:|-----------:|------------:|----------------------:|
| idea_suggestion | 93 | 4.3 | 11.8 | 8.6 | 86.0 |
| scenario_generalization | 57 | 21.1 | 15.8 | 12.3 | 66.7 |
| user_shared_fact_recall | 129 | 30.2 | 31.0 | 18.6 | 56.6 |
| preference_aligned_recommendation | 55 | 29.1 | 40.0 | 30.9 | 50.9 |
| latest_preference_acknowledgement | 17 | 29.4 | 47.1 | 29.4 | 47.1 |
| preference_evolution_tracking | 139 | 43.9 | 66.9 | 54.7 | 22.3 |
| preference_update_reason_recall | 99 | 60.6 | 74.7 | 71.7 | 18.2 |
| **ALL** | **589** | **33.4** | **43.6** | **35.3** | **46.9** |

- `latest_preference_acknowledgement`（n=17）は small_n。点推定のみ。
- type 別の難易度順序（idea_suggestion が最難、preference_update_reason_recall が最易）は 3モデルで一貫（descriptive）。

---

## 読み取り（claim boundary 内）

1. **主結果は表2の strict 46.9%**（両小型モデルが C_default で外す割合）。GPT-4o-mini は strict 定義を変えない独立参照。
2. 表1・表4は「単体でどれだけ当たるか」の参考。default_solved（両方同時正解）と混同しない。
3. 表3は strict pool の頑健性の補助証拠。GPT-4o-mini でも 88.8% は未解決、M3 でも 74.6% が残存。
4. 「履歴なしで正当に解けた」ではなく、L1 screen 上の default-solvable 成分の存在を示す結果（`docs/研究計画書0621.md` §7）。

---

*生成日: 2026-06-23。QC 記録: `docs/QC_notes_gpt4o_mini_no_history_0623.md`*
