# QC notes — GPT-4o mini no-history (C_default) reference run (2026-06-23)

独立参考測定。`strict_default_error`(llama3.1:8b + qwen2.5:7b の AND、CLAUDE.md #4)の定義は
不変。GPT-4o miniはここに組み込まれない。本ファイルは新たな確定文書ではなく、QC記録。

## 実行条件

- model: `gpt-4o-mini`(OpenAI API)
- temp=0 のみ(stability run なし。村山先生判断ではなく今回のスコープ限定 — 必要なら別途追加可)
- max_tokens=256(Gate1修正後の `NUM_PREDICT` と同じ値。num_predict truncationバグの再発防止)
- parser: `prompting.parse_letter`(Gate1修正後と同一の3階層規則)
- raw_output を per-item に保存(`results/study1/gpt4o_mini_no_history_589.csv`)
- 対象: PersonaMem 32k 589件全件。C_default(question + native options only、履歴なし)

## 結果

sanity gate: 合計589 PASS。parse_invalid=0(GPT-4o miniは常に解析可能な単一letterを返した)。

| | llama3.1:8b | qwen2.5:7b | gpt-4o-mini |
|---|---:|---:|---:|
| 全体solved率 | 33.4% | 43.6% | **35.3%**(208/589) |

### strict_default_error pool(276件、llama+qwen AND で両方外す)上でのGPT-4o-mini

| | M3(gemma2:27b, num_predict=256, 新parser) | GPT-4o-mini(今回) |
|---|---:|---:|
| 解答率 | 25.4%(70/276) | **11.2%(31/276)** |
| 残存(両モデル+M3/GPT外部でも未解決) | 74.6%(206/276) | **88.8%(245/276)** |

GPT-4o-miniはgemma2:27bよりもさらに strict pool を解けていない。第三・第四の独立モデル
(ローカル小型2種 + ローカル中型1種 + 商用1種)で見ても strict は頑健に残存する。
ただし依然「単一の商用モデル検証」であり「強モデル一般」への一般化はしない
(CLAUDE.md の既存claim boundaryを維持)。

### type別 solved率の3モデル比較(descriptive)

| canonical_type | n | llama | qwen | gpt-4o-mini |
|---|---:|---:|---:|---:|
| idea_suggestion | 93 | 4.3% | 11.8% | 8.6% |
| scenario_generalization | 57 | 21.1% | 15.8% | 12.3% |
| user_shared_fact_recall | 129 | 30.2% | 31.0% | 18.6% |
| preference_aligned_recommendation | 55 | 29.1% | 40.0% | 30.9% |
| latest_preference_acknowledgement | 17 | 29.4% | 47.1% | 29.4% |
| preference_evolution_tracking | 139 | 43.9% | 66.9% | 54.7% |
| preference_update_reason_recall | 99 | 60.6% | 74.7% | 71.7% |

**idea_suggestion が3モデル共通で最も困難、preference_update_reason_recall が3モデル共通で
最も易しい** — type別異質性の順序は3モデルで一貫している。これは Gate1 の type 異質性所見
（CLAUDE.md #8 の範囲内: 「解けない」までで「evidenceを要求する」とは言わない）が
モデル依存のアーティファクトではなく、item構造自体の性質である可能性を支持する descriptive な
追加証拠。因果や「evidence要求」への踏み込みはしない。

## 位置づけ

- strict の定義（llama+qwen AND）は不変。GPT-4o miniをstrict_3として組み込んでいない
  (CLAUDE.md #4)。
- M3(gemma2:27b)とは異なり、GPT-4o miniは strict pool だけでなく **589件全体**に対して
  実行した独立参考測定（M3は strict pool のみ）。
- 出力: `results/study1/gpt4o_mini_no_history_589.csv`,
  `results/study1/gpt4o_mini_no_history_589_summary.json`。
