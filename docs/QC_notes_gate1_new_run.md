# QC notes — Gate 1 new run (2026-06-22)

このファイルは新run固有の品質管理記録。`設計ブロック_0621.md` / `研究計画書0621.md` は
確定版（prereg相当）のため変更しない。新runで生じた事象はここに記録する。

## parse_invalid（11/589）

New run replicated the main findings, with strict rate close to the original run
(strict 273/589 = 46.3% new run vs strict 266/589 = 45.2% original run).
Unlike the original run, the new run produced 11 parse-invalid cases. These are
treated as a separate QC bucket and excluded from the primary strict/loose/solved
denominator unless re-parsing shows the intended answer is recoverable under a
pre-specified parser rule.

### 追加調査（2026-06-22、診断専用・bucket非変更）

上記の暫定記述を以下で補足する。11件すべて再診断したところ、原因は単一ではなく混在していた：

- 4/11: 真の refusal（`num_predict=120` まで生成を伸ばしても letter を一度も出さない。
  model_output_invalid）
- 6/11: 前置き・refusal的文言の後に最終的に letter を選んでいる（explanation_with_letter）。
  ただしそのうち5件は元の `num_predict=16` の生成には letter が含まれておらず、
  生成を伸ばさない限り再parseでは回収不可能（config_truncation）。
  letter が元の生成内に既に存在し、parser（先頭トークンのみ走査）が見落としていたのは
  **1件のみ**（`bb7cf8c9-546c-4876-92de-7cddedadc66c`、parser_bug_possible）。
- 1/11: `num_predict=120` でも文が完結せず判定不能（inconclusive）。

11件は llama3.1:8b 側のみで発生（qwen2.5:7b は0件）。type別では
preference_update_reason_recall に6/11が集中。persona別では6 persona（9,11,13,16,17,19）に
集中し、うち5 personaはちょうど2件ずつ — 同一 shared_context 由来の類似item間で
モデル挙動が一致したため（実際に persona 9 の2件、persona 16 の2件は raw_output が完全に同一）。

**ブロッキング事象：** 「parserルールを変更する場合は578件（invalid以外の全件）にも同規則を
適用しbucketが変わらないか確認する」という事前要件を満たせない。578件についても元の
`raw_output` は保存されておらず（後述のQC欠陥と同根）、確認のための再parseが不可能。
規則変更には589件全体の再run（新規モデル呼び出し）が必要になり、それは今回のdiagnosticの
スコープ外。

**結論（このQCノート時点）：** strict/loose/solved の bucket・denominator・gate1_summary.json・
strict_pool.csv は変更しない。11件は `t0_parse_invalid` として既存設計のまま分離する。
denominator（valid-only 578 か all-item 589 か）の最終確定は user 判断に委ねる。

詳細データ: `results/study1/parse_invalid_diagnosis.csv`,
`results/study1/parse_invalid_diagnosis_summary.json`。

## QC欠陥: raw_output 未保存（プロセス改善）

Gate1 new run（および M3 検証）は、モデル呼び出しの `pred_letter` のみを保存し、`raw_output`
（生テキスト）を保存していなかった。これにより上記の11件調査では新規の診断呼び出し
（llama3.1:8b・temp=0・既存 prompt/parser を流用、bucketには反映しない）が必要になった。
今後の全run（Study 2 含む）は raw_output を必ず per-item に保存する
（CLAUDE.md 不変条件 #11 として追加済み）。`src/study1_mcq/gate1.py` /
`src/study1_mcq/m3_validation.py` は今後の実行に向けて raw_output 列を保存するよう修正済み
（既存の確定済み結果ファイルは遡って書き換えていない）。
