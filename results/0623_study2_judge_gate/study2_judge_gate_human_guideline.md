# Study 2 Phase A Human Adjudication Guideline  
## LongMemEval Determinacy and Judge Validation Gate

- version: 0623
- target file: `results/0623_study2_judge_gate/judge_gate_human_sheet.csv`
- purpose: judge validation before Study 2a / Study 2b
- status: prereg-like adjudication guideline

---

## 0. 目的

この人手判定の目的は、LongMemEval open-ended QA において、LLM judge の判定を Study 2a / Study 2b の behavioral 実験に使ってよいかを確認することである。

このフェーズでは、モデルの evidence-only sufficiency や evidence contingency をまだ測らない。  
あくまで、judge が正解・不正解を安定して判定できるかを、人手判定と照合する。

したがって、このフェーズの主な問いは以下である。

> LongMemEval のどの item type / response type において、judge-mediated scoring は信頼できるか。

---

## 1. このフェーズでやること / やらないこと

### やること

- `judge_gate_human_sheet.csv` を人手で確認する
- judge の `correct` / `incorrect` 判定が人手判定と一致するかを見る
- false positive / false negative を分類する
- type 別に judge が安定するかを見る
- Study 2a に進める item type / response type を決める

### やらないこと

- llama / qwen などの実モデル応答を評価しない
- evidence-only sufficiency 実験をまだ実施しない
- evidence removal / evidence change 実験をまだ実施しない
- judge の判定をそのまま正解扱いしない
- raw agreement だけで gate pass を決めない

---

## 2. 判定対象

この sheet には、LongMemEval のサンプル item に対して、judge に評価させた応答が含まれている。

想定される response type は主に以下である。

| response type | 期待ラベル | 目的 |
|---|---|---|
| gold / oracle answer | correct | judge が正答を正しく認めるか |
| negative control r1 | incorrect | 値・日付・固有名詞などを崩した応答を落とせるか |
| negative control r2 | incorrect | generic / deflection / evidence-missing な応答を落とせるか |

このフェーズでは、judge が oracle answer を正解とし、negative control を不正解とできるかを確認する。

---

## 3. 基本方針

判定は **false positive に厳しく** 行う。

理由は、Study 2a / Study 2b では judge がモデル応答を正解扱いすることで behavioral claim が成立するためである。  
本当は evidence に基づく正答ではない応答を judge が `correct` としてしまうと、evidence use を過大評価する。

したがって、以下を最優先で検出する。

> judge が意味的に近いだけの応答、曖昧な応答、evidence に支えられていない応答を `correct` にしていないか。

false negative も記録するが、false positive よりは致命度が低い。  
false negative は judge が厳しすぎる方向の誤りであり、主に sufficiency を過小評価するリスクである。  
一方、false positive は evidence use を過大評価するため、Study 2 の防御線として特に重要である。

---

## 4. 判定順序

各 row では、以下の順で確認する。

### Step 1: item metadata を見る

まず以下を確認する。

- `item_id`
- `question`
- `answer`
- `item_type`
- `evidence_turns` / `has_answer` turn
- `response_type`
- `expected_label`

この時点で、何を判定すべき row なのかを理解する。

---

### Step 2: evidence と gold answer の関係を見る

次に、gold answer が evidence から一意に支持されるかを見る。

確認すること：

- evidence turn に gold answer を支える情報が含まれているか
- evidence turn だけで answer が決まるか
- answer が複数 turn の統合を必要としていないか
- answer が抽象的 generalization になっていないか
- date arithmetic / temporal reasoning が evidence に明示されているか

ここで、そもそも人手でも正誤判定が難しい場合は `human_judgeable = no` または `uncertain` とする。

---

### Step 3: candidate response を読む

次に、judge が評価した応答を読む。

確認すること：

- response が gold answer と同じ意味か
- response が必要な entity / value / date / relation を含んでいるか
- response が曖昧すぎないか
- response が部分的にしか答えていないか
- response が generic deflection ではないか
- response が evidence にない情報を補っていないか

---

### Step 4: 人手ラベルを付ける

人手で、response が正解か不正解かを判定する。

使用ラベル：

- `correct`
- `incorrect`
- `ambiguous`

原則として、`ambiguous` は後続の behavioral claim には使わない。

---

### Step 5: judge 判定との一致を見る

judge label と human label を比較する。

| judge | human | error type |
|---|---|---|
| correct | correct | agreement |
| incorrect | incorrect | agreement |
| correct | incorrect | false_positive |
| incorrect | correct | false_negative |
| correct / incorrect | ambiguous | ambiguous_human |
| ambiguous / invalid | correct / incorrect | judge_invalid_or_uncertain |

特に `false_positive` を厳しく見る。

---

## 5. 各列の判定基準

### 5.1 `human_judgeable`

この row が人手で正誤判定可能か。

- `yes`：evidence と response を見れば正誤を判定できる
- `no`：gold answer / evidence / response が曖昧で判定不能
- `uncertain`：判断に迷う

`human_judgeable=no` の row は、judge validation の denominator から除外するか、別 bucket として扱う。

主な `no` の理由：

- answer が抽象的すぎる
- evidence span に必要情報がない
- temporal reasoning の計算根拠が明示されていない
- multiple sessions の統合が必要
- gold answer と response の同値性が判断不能
- response が部分的すぎる

---

### 5.2 `human_label`

人手による正誤判定。

使用ラベル：

- `correct`
- `incorrect`
- `ambiguous`

#### `correct`

以下を満たす場合に `correct` とする。

- response が question に直接答えている
- gold answer と意味的に一致している
- 必要な entity / value / date / relation が合っている
- evidence から支持される
- 余計な推測や矛盾を含まない

#### `incorrect`

以下の場合は `incorrect` とする。

- entity / value / date / relation が違う
- gold answer の一部しか答えていない
- generic deflection である
- evidence にない情報を補っている
- gold answer と矛盾している
- question に答えていない
- negative control として意図的に崩された応答であり、gold と一致しない

#### `ambiguous`

以下の場合は `ambiguous` とする。

- response が部分的に正しいが完全には判断できない
- gold answer が曖昧
- evidence が不十分
- paraphrase として許容できるか迷う
- 人手でも correct / incorrect を安定して決めにくい

`ambiguous` は原則として gate pass の根拠にしない。

---

### 5.3 `human_error_type`

judge と人手のズレを分類する。

使用ラベル：

- `agreement`
- `false_positive`
- `false_negative`
- `ambiguous_human`
- `judge_invalid_or_uncertain`
- `uninterpretable`

#### `false_positive`

judge が `correct` としたが、人手では `incorrect` の場合。

これは最重要エラーである。  
特に以下の場合は必ず `false_positive` とする。

- negative control を judge が correct とした
- 値や日付が違うのに correct とした
- entity が違うのに correct とした
- generic answer を correct とした
- evidence にない推測を correct とした
- semantic similarity だけで正解扱いしている

#### `false_negative`

judge が `incorrect` としたが、人手では `correct` の場合。

主な原因：

- judge が gold answer の paraphrase を認めなかった
- answer が抽象的で judge が厳しく判定した
- preference generalization を literal quote でないため落とした
- temporal reasoning の正答を judge が見落とした

false negative は記録するが、false positive より致命度は低い。

---

### 5.4 `human_failure_reason`

ズレや判定不能の理由を書く。

推奨ラベル：

- `semantic-near-miss`
- `wrong-value`
- `wrong-date`
- `wrong-entity`
- `generic-deflection`
- `partial-answer`
- `unsupported-by-evidence`
- `requires-date-arithmetic`
- `requires-multi-turn-integration`
- `preference-generalization`
- `gold-answer-abstract`
- `evidence-span-insufficient`
- `judge-too-strict`
- `judge-too-lenient`
- `ambiguous-equivalence`
- `uninterpretable`

複数ある場合は `;` で併記する。

例：

```text
false_positive; wrong-date; judge-too-lenient
```

```text
false_negative; preference-generalization; judge-too-strict
```

```text
ambiguous_human; requires-date-arithmetic; evidence-span-insufficient
```

---

### 5.5 `human_notes`

後で type 別分析をするために、短く理由を書く。

良い例：

```text
Gold answer is supported by the evidence turn; judge correctly accepts the oracle answer.
```

```text
Negative control changes the date, but judge still marked it correct. This is a false positive.
```

```text
The response is a reasonable paraphrase of the gold answer; judge is too strict.
```

```text
Temporal reasoning requires date arithmetic not explicit in the evidence span.
```

```text
Preference answer is a synthesized generalization, not a literal fact in the evidence.
```

---

## 6. response type 別の注意

### 6.1 gold / oracle answer

期待ラベルは `correct`。

ただし、以下の場合は人手で `ambiguous` または `incorrect` にしてよい。

- oracle answer 自体が question に対して曖昧
- evidence turn から gold answer が支持されていない
- gold answer が複数 turn の統合を必要とする
- gold answer が過度に抽象的な generalization
- date arithmetic が必要だが evidence に計算可能な情報が十分にない

gold answer でも、常に無条件で correct にしない。

---

### 6.2 negative control r1

期待ラベルは `incorrect`。

r1 は、値・日付・固有名詞などを変更した崩し応答である。

以下を確認する。

- 変更された値が gold と異なるか
- 変更後の response が question に対して誤答になっているか
- judge がその違いを見抜けているか

もし r1 が偶然 gold と同値になっている場合は、`ambiguous` または `uninterpretable` とし、negative control の生成ミスとして記録する。

---

### 6.3 negative control r2

期待ラベルは `incorrect`。

r2 は generic deflection / evidence-missing / non-answer のような応答である。

以下を確認する。

- response が question に直接答えていないか
- gold answer を含んでいないか
- judge が generic な応答を correct としていないか

judge が r2 を correct とした場合は、原則として `false_positive` とする。

---

## 7. item type 別の注意

### 7.1 single-session-user

最も Study 2a に進めやすい候補。

期待される特徴：

- evidence が単一 session に局在しやすい
- answer が具体的な fact / value であることが多い
- judgeability が比較的高い

この type で judge-human agreement が高く、false positive が少なければ、Study 2a の主対象にできる。

---

### 7.2 single-session-preference

注意が必要。

想定される問題：

- gold answer が具体的な fact ではなく、preference generalization になりやすい
- evidence span に literal quote がなくても、全体の雰囲気から gold が作られていることがある
- judge が strict すぎると false negative が出やすい
- judge が lenient すぎると抽象的に近い応答を correct にしやすい

この type は、agreement が高い場合のみ Study 2a に含める。  
false positive / false negative が集中する場合は constraint finding として報告し、behavioral claim から除外する。

---

### 7.3 temporal-reasoning

注意が必要。

想定される問題：

- evidence span に日付や順序はあるが、answer には date arithmetic が必要
- judge が計算を誤る
- negative control の日付違いを judge が見逃す
- evidence span だけでは正答が判断できない場合がある

この type で judge error が集中する場合は、Study 2a から除外し、temporal reasoning は judgeability constraint として報告する。

---

### 7.4 multi-session

determinacy filter で多くが落ちる想定。

想定される問題：

- evidence が複数 session に分散
- single-source localization に向かない
- answer が複数 turn の統合を必要とする
- judgeability が item ごとに大きく揺れる

filter を通過したものだけを見る。  
ただし、基本的には constraint finding として扱う。

---

### 7.5 knowledge-update

このフェーズでは除外済み。

理由：

- 古値 / 新値が競合する
- single-source localization に反する
- recency / update 判断が別の confound になる

判定対象に出てきた場合は、データ混入として記録する。

---

## 8. Gate pass / fail の判断

人手判定後、以下を集計する。

### 8.1 overall metrics

- total rows
- human-judgeable rows
- raw agreement
- false positives
- false negatives
- ambiguous rows
- uninterpretable rows

### 8.2 type-level metrics

type ごとに以下を出す。

- n
- raw agreement
- FP count
- FN count
- ambiguous count
- judgeable count

### 8.3 response-type metrics

response type ごとに以下を出す。

- n
- raw agreement
- FP count
- FN count
- ambiguous count

---

## 9. Gate decision rule

### 9.1 全体 gate

原則として、以下を満たせば judge gate は暫定 pass とする。

```text
raw agreement >= 0.80
and false positives are rare
and false positives are not concentrated in a target type
and enough judgeable items remain for Study 2a
```

ただし、raw agreement が 0.80 を超えていても、false positive が特定 type / response type に集中する場合は、その type / response type を behavioral claim から除外する。

### 9.2 type-level gate

type ごとに次を決める。

- `pass_to_study2a`
- `exclude_from_behavioral_claim`
- `constraint_finding_only`
- `needs_prompt_revision`

#### pass_to_study2a

以下を満たす場合。

- judgeable item が十分ある
- agreement が高い
- false positive がほぼない
- gold / oracle answer を安定して correct にできる
- negative control を安定して incorrect にできる

#### exclude_from_behavioral_claim

以下の場合。

- false positive が多い
- judge が negative control を落とせない
- human_judgeable=no が多い
- answer equivalence が曖昧
- evidence span が不十分

#### constraint_finding_only

以下の場合。

- judge / human ともに判定が難しい
- type の構造上、single-source evidence に向かない
- temporal arithmetic / preference generalization など、format-specific constraint が見える

#### needs_prompt_revision

以下の場合。

- judge のミスが prompt の曖昧さに由来していそう
- 判定基準を明確にすれば改善しそう
- ただし prompt revision を行う場合は、revision 前後の結果を混同しない

---

## 10. 最終集計で出すもの

人手判定後に、以下を報告する。

```text
Overall:
- human-judgeable rows: ...
- raw agreement: ...
- false positives: ...
- false negatives: ...
- ambiguous: ...

By item type:
- single-session-user: ...
- single-session-preference: ...
- temporal-reasoning: ...
- multi-session: ...

By response type:
- oracle/gold: ...
- negative control r1: ...
- negative control r2: ...

Gate decision:
- pass_to_study2a: ...
- exclude_from_behavioral_claim: ...
- constraint_finding_only: ...
- needs_prompt_revision: ...
```

特に、以下は本文または補足で必ず説明する。

- false positive の発生箇所
- false negative の発生箇所
- temporal-reasoning の date arithmetic 問題
- single-session-preference の generalization 問題
- multi-session が filter で落ちる理由

---

## 11. 次フェーズへの接続

この gate の結果に基づき、Study 2a の対象を決める。

### Study 2a に進める条件

- type-level gate を通過している
- judge が gold / oracle answer を正しく認める
- judge が negative control を正しく落とせる
- false positive が少ない
- human_judgeable な item が十分残る

### Study 2a に進めない場合

それは失敗ではない。

以下のような constraint finding として報告する。

- open-ended memory QA では answer equivalence が曖昧
- temporal reasoning は judgeability が低い
- preference generalization は literal evidence 判定に向かない
- multi-session item は single-source evidence audit に向かない

本研究の問いは、単にモデルが正答するかではなく、

> 正答が evidence use としてどこまで検証可能か

である。  
したがって、judge gate で落ちる type があること自体も重要な結果である。

---

## 12. 最重要ルール

judge validation gate を通る前に、judge-mediated behavioral result を作らない。

raw agreement だけで安心しない。  
false positive を最優先で確認する。  
type ごとに pass / fail を分ける。  
ambiguous な row は無理に correct / incorrect に押し込まない。

迷ったら、behavioral claim には使わない。