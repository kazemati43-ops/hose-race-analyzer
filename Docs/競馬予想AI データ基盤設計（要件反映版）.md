# 競馬予想AI データ基盤設計（要件反映版）

## 設計方針

* レースは「概念（master）」と「開催実体（event）」を分離
* 変更され得る条件は履歴管理
* 馬は不変データのみマスタ化
* 可変データは結果テーブルへ集約
* 分類値は正規化（系統・牧場・斤量方式など）

---

## 🐎 horse（競走馬マスタ：不変）

* horse_id（PK）
* name
* sex
* birth_year
* sire
* dam
* damsire
* sire_line_id
* damsire_line_id
* breeder_id

---

## 🧬 pedigree_line（血統系統マスタ）

* line_id（PK）
* line_name（ミスプロ系・サンデー系など）

---

## 🏭 breeder（生産牧場マスタ）

* breeder_id（PK）
* breeder_name

---

## 🏆 race_master（レース概念）

* race_master_id（PK）
* grade（G1/G2/G3）

---

## 📜 race_definition_history（期間別ルール）

* def_id（PK）
* race_master_id
* race_name
* start_year
* end_year
* min_age
* max_age
* sex_condition
* weight_type_id

---

## ⚖ weight_type（斤量方式マスタ）

* weight_type_id（PK）
* name（定量・別定・ハンデ）

---

## 🏟 racecourse（競馬場マスタ）

* course_id（PK）
* course_name（東京・阪神・大井など）

---

## 📅 race_event（開催実体）

* race_event_id（PK）
* race_master_id
* race_date
* race_year
* course_id
* distance
* surface
* track_condition

---

## 📊 race_result（レース結果）

* race_event_id
* horse_id
* rank
* frame
* odds
* popularity
* carried_weight
* horse_weight
* last_3f
* time
* jockey
* trainer

（論理主キー：race_event_id + horse_id）

---

## 分析ルール

* 傾向分析は race_master 単位で集計
* ハンデ戦は weight_type_id で除外・抽出可能
* 条件変更は race_definition_history で吸収

---

## この設計で満たす要件

* 年代比較可能
* 名称変更・条件変更に耐性
* 中央・地方混在対応
* 血統・牧場分析対応
* 斤量ロジック破綻なし
* 将来拡張容易
