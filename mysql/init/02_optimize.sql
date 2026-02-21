-- データベースの物理最適化と分析用ビューの作成

USE horse_race_db;

-- 1. 検索速度向上のためのインデックス付与
-- 既に race_result の PK は (race_event_id, horse_id) のため、race_event_id 単体または複合での検索は高速。
-- horse_id 単体での検索（過去走履歴など）、および騎手・調教師での集計を高速化する。
CREATE INDEX idx_horse_id ON race_result(horse_id);
CREATE INDEX idx_jockey ON race_result(jockey);
CREATE INDEX idx_trainer ON race_result(trainer);
CREATE INDEX idx_race_date ON race_event(race_date);

-- 2. 分析用ビューの作成
-- 上がり3F偏差値と、簡単なPCI（ペースチェンジ指数）の計算をサポートするビュー
-- PCI = (走破タイム - 上がり3Fタイム) / 上がり3Fタイム * 100 
-- （※実際のPCIはもう少し複雑な補正が入る場合がありますが、ここでは簡易的な基礎指標として定義）

CREATE OR REPLACE VIEW v_race_result_analytics AS
SELECT 
    rr.race_event_id,
    rr.horse_id,
    rr.`rank`,
    rr.time AS finish_time,
    rr.last_3f,
    re.distance,
    re.race_date,
    -- 上がり3F偏差値の計算（レース内での相対評価）
    -- タイムが小さい（速い）ほど偏差値が高くなるように計算： 50 + (平均 - 自身) / 標準偏差 * 10
    -- 標準偏差が0またはNULL（全員同じタイム、あるいは1頭立て等）の場合は50とする
    CASE 
        WHEN STDDEV_SAMP(rr.last_3f) OVER(PARTITION BY rr.race_event_id) > 0 THEN
            ROUND(50 + (AVG(rr.last_3f) OVER(PARTITION BY rr.race_event_id) - rr.last_3f) / STDDEV_SAMP(rr.last_3f) OVER(PARTITION BY rr.race_event_id) * 10, 1)
        ELSE 50.0
    END AS last_3f_deviation,
    
    -- PCI（簡易版）の計算
    -- (走破タイム - 上がり3F(秒数変換)) / 上がり3F(秒数変換) * 100
    -- ※ last_3f は 345 のようなデータであれば 34.5秒だが、ここではCSVの取り込み仕様上 FLOATの秒数と想定（事前処理依存）
    -- もし last_3f がINT型で 345(34.5秒) として入っている場合は /10 する必要がある
    CASE
        WHEN rr.last_3f > 0 AND rr.time > (rr.last_3f / 10.0) THEN
            ROUND(((rr.time - (rr.last_3f / 10.0)) / (rr.last_3f / 10.0)) * 100, 1)
        ELSE NULL
    END AS pci_base
FROM 
    race_result rr
JOIN 
    race_event re ON rr.race_event_id = re.race_event_id;
