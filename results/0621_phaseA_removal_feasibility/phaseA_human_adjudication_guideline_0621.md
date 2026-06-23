# Phase A Human Adjudication Guideline 0621

## 0. 目的

この文書は、Phase A で GPT-4o mini が提案した gold evidence span / placebo span を、人手で判定するためのガイドラインである。

Phase A の目的は、Phase B の removal sensitivity 実験に進める item を選別することである。

GPT-4o mini は候補 span を提案しただけであり、最終判定者ではない。  
Phase B に進めるのは、人手で以下が確認できた item のみとする。

1. target が履歴から一意に決まる  
2. gold span が本当に gold answer を支えている  
3. gold span が answer を決めるのに十分である  
4. placebo span が target と無関係である  
5. removal 操作が妥当である  
6. leakage-risk が高くない  

---

## 1. 基本方針

判定は **厳しめ** に行う。

理由は、Phase A で弱い gold span や不完全な placebo を通すと、Phase B の結果が解釈不能になるためである。

特に避けたい失敗は以下である。

- topic が近いだけの span を gold evidence として通す
- target がそもそも一意に決まらない item を通す
- placebo が実は target と近い情報を含んでいる
- gold removal でも答えが変わらなかったときに、本当は localization が悪かっただけなのに `no sensitivity` と誤読する
- placebo removal で答えが変わったときに、本当は placebo が neutral でなかっただけなのに `non-specific sensitivity` と誤読する
- options / question wording から gold が推測できる item を evidence-use item として通す

最重要ルール：

> 迷ったら通さない。  
> Phase B の分母は小さくなってもよい。弱い gold span や怪しい placebo を通して、後で結果が解釈不能になる方が危険である。

---

## 2. 判定順序

一人判定では、GPT の rationale に引きずられる危険がある。  
そのため、各 item では必ず以下の順で読む。

### Step 1: GPT rationale を読む前に、自分で gold 根拠を探す

最初に見るもの：

- question
- options
- gold answer
- full history

この段階では、以下を読まない。

- `gold_span_rationale`
- `proposed_gold_span_text`
- `placebo_selection_reason`
- `gpt4o_mini_raw_response`

まず自分で判断する。

- gold answer を支える履歴上の根拠はあるか
- それはどの turn か
- その根拠だけで gold answer が他の選択肢より明確に支持されるか
- gold answer が履歴から一意に決まるか
- options / question wording だけで gold が推測できないか

この時点で target が一意に決まらない場合は、`human_target_determinate=no` とし、原則として `human_final_include=no` とする。

---

### Step 2: GPT proposed gold span と照合する

自分で見つけた根拠と、GPT が提案した以下を比べる。

- `proposed_gold_span_turn_ids`
- `proposed_gold_span_text`
- `gold_span_rationale`

確認すること：

- GPT span が同じ根拠を指しているか
- GPT span が gold answer を本当に決定しているか
- GPT span が広すぎないか
- GPT span が重要な turn を取り逃がしていないか
- GPT span が話題的に近いだけで、gold answer を決めていない可能性がないか

---

### Step 3: placebo span を確認する

以下を確認する。

- `proposed_placebo_span_turn_ids`
- `proposed_placebo_span_text`
- `placebo_selection_reason`
- `placebo_removed_history`

placebo は、gold evidence と同程度の長さで、かつ target と無関係でなければならない。

placebo 判定は特に厳しく行う。  
target と少しでも近い場合は `human_placebo_neutral=no` とする。

---

### Step 4: removal 操作を確認する

以下を確認する。

- `gold_removed_history`
- `placebo_removed_history`

Phase A 実装では、GPT の引用文ではなく dataset の turn_id から機械的に removal している。  
これは重要な性質であり、Phase B でも維持する。

判定では、以下を見る。

- 削除された turn が proposed turn_ids と一致しているか
- 削除後の履歴が極端に壊れていないか
- gold removal と placebo removal の削除量が大きく違いすぎないか

---

### Step 5: final include を決める

最終的に、以下をすべて満たす場合のみ `human_final_include=yes` とする。

```text
human_final_include = yes
iff
  human_target_determinate = yes
  and human_gold_span_correct = yes
  and human_gold_span_sufficient = yes
  and human_placebo_neutral = yes
  and human_placebo_valid = yes
  and human_remove_operation_valid = yes
  and leakage-risk ではない
```

どれか一つでも満たさない場合は `human_final_include=no` とする。

---

## 3. 表示上の注意：二重 role prefix

Phase A の summary で、history content がすでに `User:` / `Assistant:` を含んでおり、さらに `format_history` が role を付けるため、以下のような二重 prefix が表示される場合がある。

```text
[3] user: User: ...
[4] assistant: Assistant: ...
```

これはデータ表示上の問題であり、mechanical removal 自体には影響しない。

したがって、`human_remove_operation_valid` の判定で、二重 prefix だけを理由に `no` にしない。

Phase B では、モデルに入力する ablated history から prefix の二重化を取り除く予定である。  
そのため、adjudication では二重 prefix は表示上のノイズとして扱う。

---

## 4. 各列の判定基準

### 4.1 `human_target_determinate`

gold answer が履歴中の情報によって一意に決まるか。

- `yes`：履歴を読めば、gold answer が他選択肢より明確に妥当
- `no`：履歴を読んでも複数選択肢があり得る
- `uncertain`：判断が難しい、または answer option 自体が曖昧

`human_target_determinate=no` の item は、原則として `human_final_include=no` とする。

理由：target が一意に決まらない item では、「gold span を削れば応答が変わるはず」という Phase B の前提が成立しない。

例：

- yes：履歴に「ユーザーは静かなカフェを好む」とあり、gold が「静かなカフェ」
- no：履歴に「外食が好き」としかなく、gold が「イタリアン」
- uncertain：履歴の発話が曖昧で、複数の解釈が可能

---

### 4.2 `human_gold_span_correct`

proposed gold span が、本当に gold answer を支えているか。

判定は厳しめにする。

- `yes`：span 単独で gold answer を強く支持し、他選択肢より gold が明確に選べる
- `no`：span は関連しているだけ、または gold を決定しない
- `uncertain`：支持しているように見えるが、他の情報も必要

重要：

> 「話題が近い」だけでは `yes` にしない。  
> gold answer を決める根拠になっている必要がある。

---

### 4.3 `human_gold_span_sufficient`

proposed gold span だけで gold answer を復元できるか。

- `yes`：span だけを読めば gold answer を選べる
- `no`：span だけでは gold answer が決まらない
- `uncertain`：span は有用だが、他の履歴情報も必要そう

`human_gold_span_correct=yes` でも、`human_gold_span_sufficient=no` はあり得る。

例：

- correct=yes, sufficient=yes  
  span に明確な好み・事実・理由が書かれている

- correct=yes, sufficient=no  
  span は gold と関係するが、他の turn と合わせないと gold が決まらない

`sufficient=no` の item は、`human_final_include=no` とし、`human_exclusion_reason` に `gold-span-insufficient` を記録する。

これは単なる脱落ではなく、最終集計で別建てにする。

解釈：

> gold answer は履歴中の情報に支えられているが、単一 span では決まらず、複数 turn の統合を要する item である。  
> したがって、single-span removal による Phase B には適さない。

この件数が多い場合、それ自体が「single-span localization が成立しない item が多い」という構造的所見になる。

---

### 4.4 `human_gold_span_minimal`

gold span が必要以上に広すぎないか。

- `yes`：必要な turn にほぼ絞られている
- `no`：履歴の大部分を含む、または不要な turn が多すぎる
- `uncertain`：少し広いが、除外するほどではない

`minimal` は final include の絶対必須条件ではない。

ただし、span が広すぎる場合は Phase B の removal が履歴全体の削除に近くなるため、`human_final_include=no` を検討する。

目安：

- 1〜3 turn 程度で gold を支えるなら `yes`
- 少し広いが gold evidence を含むなら `uncertain`
- 履歴の大部分を削るなら `no`

---

### 4.5 `human_placebo_neutral`

placebo span が target と無関係か。

判定は非常に厳しめにする。

以下のどれかに当てはまる場合は `no`。

1. target preference / fact / reason に直接言及している
2. gold span と重要語彙が重なる
3. いずれかの answer option を支持している
4. target と同じ好み領域に触れている
5. target と別軸でも、ユーザーの選好判断に影響し得る情報を含む

特に、同じ好み領域に触れている placebo は `no` とする。

例：

- target が「コーヒーの好み」  
  placebo が「紅茶の好み」  
  → 同じ飲み物・嗜好領域なので `no`

- target が「静かな作業場所が好き」  
  placebo が「人混みが苦手」  
  → 関連する環境 preference なので `no`

- target が「辛い料理が好き」  
  placebo が「昨日映画を見た」  
  → target と無関係なら `yes`

---

### 4.6 `human_placebo_comparable_length`

placebo span が gold span と同程度の長さか。

- `yes`：utterance 数または文字数が近い
- `no`：明らかに長すぎる / 短すぎる
- `uncertain`：多少違うが許容範囲

長さが完全一致する必要はない。

ただし、gold span が1 turnなのに placebo が5 turnある、などは `no`。

---

### 4.7 `human_placebo_valid`

placebo span が Phase B の統制として使えるか。

- `yes`：neutral で、長さも比較可能で、削除しても履歴構造が壊れない
- `no`：neutral でない、長さが極端、削除すると履歴が不自然になる
- `uncertain`：使えそうだが不安が残る

原則：

```text
human_placebo_valid = yes
iff
  human_placebo_neutral = yes
  and human_placebo_comparable_length is yes or acceptable uncertain
```

`human_placebo_valid=no` の item は `human_final_include=no` とする。

---

### 4.8 `human_remove_operation_valid`

gold span / placebo span を削除する操作が妥当か。

- `yes`：turn_id に基づく削除で、履歴が自然に残る
- `no`：削除により会話構造が壊れる、文脈が不自然すぎる
- `uncertain`：多少不自然だが、実験には使える可能性がある

注意：

- Phase A 実装では、GPT の引用文ではなく dataset の turn_id から mechanical removal している。
- この性質は良いので Phase B でも維持する。
- 二重 role prefix は表示上の問題なので、これだけを理由に `no` にしない。

---

### 4.9 `human_final_include`

Phase B に進めるか。

原則：

```text
human_final_include = yes
iff
  human_target_determinate = yes
  and human_gold_span_correct = yes
  and human_gold_span_sufficient = yes
  and human_placebo_neutral = yes
  and human_placebo_valid = yes
  and human_remove_operation_valid = yes
  and leakage-risk ではない
```

以下の場合は `no`。

- target が履歴から一意に決まらない
- gold span が関連しているだけで決定打ではない
- gold span だけでは answer が決まらない
- placebo が target と少しでも近い
- placebo がいずれかの option を支持している
- removal 操作が不自然
- leakage risk が高い
- item 自体が曖昧
- parse / formatting / data issue で解釈不能

---

## 5. leakage-risk の扱い

GPT proposal が `localizable` でも、以下の場合は `human_final_include=no` とする。

- gold answer が options だけから推測できる
- question wording から gold が推測できる
- world knowledge / commonsense だけで gold が推測できる
- gold span を見なくても、明らかにその選択肢が自然
- answer option に理由が埋め込まれている
- gold span より options 側の手がかりの方が強い

この場合、`human_exclusion_reason` に `leakage-risk` と書く。

leakage-risk は `human_target_determinate` や `human_gold_span_correct` とは別概念である。

したがって、仮に各列が `yes` に見えても、leakage-risk が高い場合は `human_final_include=no` とする。

---

## 6. correct=yes / sufficient=no の扱い

`human_gold_span_correct=yes` だが `human_gold_span_sufficient=no` の item は、Phase B には進めない。

この場合、`human_exclusion_reason` は原則として以下にする。

```text
gold-span-insufficient
```

必要なら補足を加える。

```text
gold-span-insufficient; requires multiple turns
```

このケースは、単なる失敗ではなく重要な構造的所見である。

意味：

> gold answer は履歴中の情報と整合しているが、単一の削除可能 span では answer を決定できない。  
> したがって、single-span removal による evidence contingency 検証には適さない。

最終集計では、`gold-span-wrong` とは分けて数える。

- `gold-span-wrong`：GPT が間違った根拠を提案した
- `gold-span-insufficient`：根拠は関連するが、単一 span としては不十分
- `target-underdetermined`：そもそも gold answer が履歴から一意に決まらない

---

## 7. human_exclusion_reason の推奨ラベル

除外する場合は、できるだけ以下のラベルを使う。

- `target-underdetermined`
- `gold-span-wrong`
- `gold-span-insufficient`
- `gold-span-too-broad`
- `placebo-not-neutral`
- `placebo-not-comparable`
- `placebo-unavailable`
- `remove-operation-invalid`
- `leakage-risk`
- `uninterpretable`

複数ある場合は、主理由を最初に書き、必要なら `;` で併記する。

例：

```text
placebo-not-neutral; same preference domain as target
```

```text
gold-span-insufficient; requires multiple turns
```

```text
leakage-risk; option wording already reveals preference
```

---

## 8. human_notes の書き方

`human_notes` には、後で Phase B の結果を読むときに必要な情報を書く。

良い例：

```text
Gold span explicitly states user prefers quiet cafes. Placebo is about unrelated movie discussion.
```

```text
Gold span is topically related but does not distinguish option B from option C.
```

```text
Placebo mentions another food preference; not neutral enough for removal control.
```

```text
Target is not determinate: both options A and C are compatible with the history.
```

```text
Gold span is relevant but insufficient; answer requires combining turns 4 and 9.
```

---

## 9. 最終集計で出すもの

adjudication 後に、以下を集計する。

```text
human_final_include=yes: k件

type breakdown:
- user_shared_fact_recall: x件
- preference_update_reason_recall: y件
- preference_evolution_tracking: z件

exclusion reasons:
- target-underdetermined: ...
- gold-span-wrong: ...
- gold-span-insufficient: ...
- gold-span-too-broad: ...
- placebo-not-neutral: ...
- placebo-not-comparable: ...
- placebo-unavailable: ...
- remove-operation-invalid: ...
- leakage-risk: ...
- uninterpretable: ...
```

特に、以下は別建てで報告する。

- `target-underdetermined`
- `gold-span-insufficient`
- `placebo-not-neutral`
- `leakage-risk`

これらは単なる脱落ではなく、既存 benchmark item が intervention-ready でない理由を示す構造的所見である。

---

## 10. Phase B への分岐

人手判定後の `human_final_include=yes` 件数で、Phase B の扱いを決める。

- `human_final_include=yes` が10件以上  
  → removal sensitivity 実験として Phase B を実施

- 5〜9件  
  → 小規模 feasibility pilot として Phase B を実施

- 5件未満  
  → Phase B は無理に走らせず、evidence localization / intervention eligibility の構造的所見として報告

どの場合でも失敗ではない。

本研究の問いは、

> 正答は履歴中の根拠利用としてどこまで検証可能か

である。

したがって、Phase B に進めない item が多い場合も、「既存 benchmark item は intervention-ready ではない」という所見になる。

---

## 11. 判定作業の推奨ワークフロー

1. CSV を開く
2. 1 item ずつ、まず question / options / gold / full history だけを読む
3. 自分で gold 根拠を探す
4. `human_target_determinate` を記入
5. GPT proposed gold span を確認
6. `human_gold_span_correct` / `human_gold_span_sufficient` / `human_gold_span_minimal` を記入
7. placebo span を確認
8. `human_placebo_neutral` / `human_placebo_comparable_length` / `human_placebo_valid` を記入
9. removed histories を確認
10. `human_remove_operation_valid` を記入
11. leakage-risk を確認
12. `human_final_include` を決める
13. `human_exclusion_reason` と `human_notes` を記入する

---

## 12. 最終ルール

Phase B に進める item は、少なくてよい。

重要なのは数を増やすことではなく、Phase B の解釈可能性を守ることである。

> target が一意で、gold span が十分で、placebo が本当に neutral で、leakage-risk が低い item だけを通す。

この条件を満たさない item は、Phase B に進めず、構造的な除外理由として記録する。