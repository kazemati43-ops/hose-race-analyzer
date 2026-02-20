# 処理設計 × データベース設計 対応表（フェーズA）

本ドキュメントは、既存の **競馬予想AI データ基盤設計（要件反映版）** と、
フロント／バックエンドの処理設計（フェーズA）を突合し、
「どの処理が、どのテーブルの事実データを使うか」を明示する対応表である。

---

## 1. 分析要求受付・セッション生成

| 処理内容      | 対応テーブル                  | 備考                         |
| --------- | ----------------------- | -------------------------- |
| レース指定     | race_master             | レース概念の特定                   |
| 分析対象年確定   | race_event              | race_master_id + race_year |
| 条件履歴参照    | race_definition_history | 年ごとの条件差異吸収                 |
| 分析セッション生成 | （未定義）analysis_session   | フォローアップ対応用（追加候補）           |

---

## 2. 分析スコープ確定（MCP相当）

| 処理内容      | 対応テーブル                                 |
| --------- | -------------------------------------- |
| レース格判定    | race_master.grade                      |
| 斤量方式判定    | race_definition_history.weight_type_id |
| ハンデ戦抽出・除外 | weight_type                            |

---

## 3. 過去10年データ取得（RAG）

### 3.1 レース開催実体

| 処理内容   | 対応テーブル                 |
| ------ | ---------------------- |
| 過去開催取得 | race_event             |
| 競馬場・条件 | racecourse, race_event |

### 3.2 出走馬・結果

| 処理内容 | 対応テーブル                     |
| ---- | -------------------------- |
| 全出走馬 | race_result                |
| 着順   | race_result.rank           |
| 枠    | race_result.frame          |
| 人気   | race_result.popularity     |
| オッズ  | race_result.odds           |
| 馬体重  | race_result.horse_weight   |
| 上がり  | race_result.last_3f        |
| 斤量   | race_result.carried_weight |

---

## 4. 馬属性参照（不変情報）

| 処理内容 | 対応テーブル                                |
| ---- | ------------------------------------- |
| 性別   | horse.sex                             |
| 年齢算出 | horse.birth_year + race_year          |
| 父    | horse.sire                            |
| 母父   | horse.damsire                         |
| 父系統  | horse.sire_line_id → pedigree_line    |
| 母父系統 | horse.damsire_line_id → pedigree_line |
| 生産牧場 | horse.breeder_id → breeder            |

※ 脚質・距離適性・コース適性などの派生値はDBに保持せず、処理で算出する。

---

## 5. 単条件・複合条件評価

| 分析軸    | 参照元                          |
| ------ | ---------------------------- |
| 枠      | race_result.frame            |
| 人気帯    | race_result.popularity       |
| オッズ帯   | race_result.odds             |
| 馬体重帯   | race_result.horse_weight     |
| 上がり順位  | race_result.last_3f          |
| 馬齢     | horse.birth_year + race_year |
| 性別     | horse.sex                    |
| 前走格    | race_event + race_result（直近） |
| ローテ    | race_event.race_date 差分      |
| 距離経験   | race_event.distance          |
| コース経験  | racecourse                   |
| 父系・母父系 | pedigree_line                |
| 牧場     | breeder                      |

---

## 6. 今年の出馬表への当てはめ

| 処理内容   | 対応テーブル                             |
| ------ | ---------------------------------- |
| 出走馬一覧  | race_result（rank未確定）または race_entry |
| 馬属性    | horse                              |
| 条件適合判定 | 上記JOIN結果                           |

---

## 7. 検証処理（嘘防止）

| 検証内容     | 参照元                     |
| -------- | ----------------------- |
| 母数再計算    | race_result             |
| 割合・中央値整合 | 集計SQL                   |
| 条件逸脱検出   | race_definition_history |
| ハンデ戦混入   | weight_type             |

---

## 8. 結果保存・フォローアップ

| 処理内容      | 対応テーブル                |
| --------- | --------------------- |
| 分析結果保存    | （未定義）analysis_result  |
| セッション管理   | （未定義）analysis_session |
| フォローアップ説明 | 上記テーブル参照              |

---

## 9. 総括

* 既存のデータ基盤設計は、フェーズA処理設計と完全に整合
* DBに保持するのは事実データのみ
* 傾向・脚質・適性などはすべて処理で算出
* 追加が必要なのは分析セッション／結果管理用テーブルのみ

本対応表は、実装フェーズにおけるDBアクセス設計の正とする。
