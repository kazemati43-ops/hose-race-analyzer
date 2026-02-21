-- 1. レース結果の属性欠損チェック
SELECT 
    COUNT(*) as total_records,
    SUM(CASE WHEN `rank` IS NULL OR `rank` = 0 THEN 1 ELSE 0 END) as missing_rank,
    SUM(CASE WHEN last_3f IS NULL OR last_3f = 0 THEN 1 ELSE 0 END) as missing_last_3f,
    SUM(CASE WHEN passing_order IS NULL OR passing_order = '' THEN 1 ELSE 0 END) as missing_passing_order,
    SUM(CASE WHEN odds IS NULL OR odds = 0 THEN 1 ELSE 0 END) as missing_odds,
    SUM(CASE WHEN popularity IS NULL OR popularity = 0 THEN 1 ELSE 0 END) as missing_popularity
FROM race_result
WHERE race_event_id IN ('202105010811', '202205010811', '202305010811', '202405010811', '202505010811');

-- 2. 出走予定馬含む全頭の属性欠損チェック
SELECT 
    COUNT(*) as total_horses,
    SUM(CASE WHEN sex IS NULL OR sex = '' THEN 1 ELSE 0 END) as missing_sex,
    SUM(CASE WHEN birth_year IS NULL OR birth_year = 0 THEN 1 ELSE 0 END) as missing_birth_year,
    SUM(CASE WHEN sire IS NULL OR sire = '' THEN 1 ELSE 0 END) as missing_sire,
    SUM(CASE WHEN dam IS NULL OR dam = '' THEN 1 ELSE 0 END) as missing_dam,
    SUM(CASE WHEN damsire IS NULL OR damsire = '' THEN 1 ELSE 0 END) as missing_damsire
FROM horse;

-- 3. 未同期馬の抽出 (詳細情報がない馬のリストと全体数)
SELECT COUNT(DISTINCT r.horse_id) as unsynced_horse_count
FROM race_result r
JOIN horse h ON r.horse_id = h.horse_id
WHERE (h.sire IS NULL OR h.sire = '');

SELECT DISTINCT h.horse_id, h.name 
FROM race_result r
JOIN horse h ON r.horse_id = h.horse_id
WHERE (h.sire IS NULL OR h.sire = '')
LIMIT 15;
