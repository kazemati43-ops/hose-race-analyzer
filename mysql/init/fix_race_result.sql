CREATE TABLE IF NOT EXISTS race_result (
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
