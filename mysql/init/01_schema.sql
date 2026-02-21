CREATE DATABASE IF NOT EXISTS horse_race_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE horse_race_db;

-- 競走馬マスタ：不変
CREATE TABLE horse (
    horse_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    sex VARCHAR(10),
    birth_year INT,
    sire VARCHAR(100),
    dam VARCHAR(100),
    damsire VARCHAR(100),
    sire_line_id VARCHAR(50),
    damsire_line_id VARCHAR(50),
    breeder_id VARCHAR(50)
);

-- 血統系統マスタ
CREATE TABLE pedigree_line (
    line_id VARCHAR(50) PRIMARY KEY,
    line_name VARCHAR(100) NOT NULL
);

-- 生産牧場マスタ
CREATE TABLE breeder (
    breeder_id VARCHAR(50) PRIMARY KEY,
    breeder_name VARCHAR(100) NOT NULL
);

-- レース概念
CREATE TABLE race_master (
    race_master_id VARCHAR(50) PRIMARY KEY,
    grade VARCHAR(20)
);

-- 期間別ルール
CREATE TABLE race_definition_history (
    def_id VARCHAR(50) PRIMARY KEY,
    race_master_id VARCHAR(50) NOT NULL,
    race_name VARCHAR(100),
    start_year INT,
    end_year INT,
    min_age INT,
    max_age INT,
    sex_condition VARCHAR(50),
    weight_type_id VARCHAR(50)
);

-- 斤量方式マスタ
CREATE TABLE weight_type (
    weight_type_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

-- 競馬場マスタ
CREATE TABLE racecourse (
    course_id VARCHAR(50) PRIMARY KEY,
    course_name VARCHAR(50) NOT NULL
);

-- 開催実体
CREATE TABLE race_event (
    race_event_id VARCHAR(50) PRIMARY KEY,
    race_master_id VARCHAR(50) NOT NULL,
    race_date DATE,
    race_year INT,
    course_id VARCHAR(50),
    distance INT,
    surface VARCHAR(20),
    track_condition VARCHAR(20)
);

-- レース結果
CREATE TABLE race_result (
    race_event_id VARCHAR(50) NOT NULL,
    horse_id VARCHAR(50) NOT NULL,
    `rank` INT,
    frame INT,
    odds DECIMAL(5,2),
    popularity INT,
    carried_weight DECIMAL(4,1),
    horse_weight INT,
    last_3f INT,
    time DECIMAL(6,1),
    jockey VARCHAR(100),
    trainer VARCHAR(100),
    PRIMARY KEY (race_event_id, horse_id)
);
