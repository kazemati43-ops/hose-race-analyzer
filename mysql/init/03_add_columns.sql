USE horse_race_db;
ALTER TABLE race_event ADD COLUMN lap_time VARCHAR(255);
ALTER TABLE race_result ADD COLUMN passing_order VARCHAR(50);
