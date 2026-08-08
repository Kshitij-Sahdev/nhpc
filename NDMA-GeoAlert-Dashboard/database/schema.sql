CREATE TABLE IF NOT EXISTS states (
    state_id INT PRIMARY KEY AUTO_INCREMENT,
    state_name VARCHAR(100) NOT NULL UNIQUE,
    feed_slug VARCHAR(100) NOT NULL UNIQUE,
    is_selected BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS districts (
    district_code INT PRIMARY KEY,
    district_name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS project_sites (
    project_id INT PRIMARY KEY,
    project_name VARCHAR(100) NOT NULL,
    lat DOUBLE,
    lng DOUBLE
);

CREATE TABLE IF NOT EXISTS gnd_sites (
    site_id INT PRIMARY KEY AUTO_INCREMENT,
    site_name VARCHAR(100) NOT NULL,
    project_id INT,
    lat DOUBLE,
    lng DOUBLE,

    FOREIGN KEY (project_id)
        REFERENCES project_sites(project_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    alert_identifier VARCHAR(100) NOT NULL UNIQUE,
    state_id INT NOT NULL,
	
    event VARCHAR(255),
    headline_en TEXT,
	
    urgency VARCHAR(50),
    severity VARCHAR(50),
    certainty VARCHAR(50),
	
    effective DATETIME,
    onset DATETIME,
    expires DATETIME,
	
    polygons JSON,
	
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	
    FOREIGN KEY (state_id)
        REFERENCES states(state_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alert_districts (
    alert_id BIGINT NOT NULL,
    district_code INT NOT NULL,
    PRIMARY KEY (
        alert_id,
        district_code
    ),
    FOREIGN KEY (alert_id)
        REFERENCES alerts(alert_id)
        ON DELETE CASCADE,
    FOREIGN KEY (district_code)
        REFERENCES districts(district_code)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS warnings (
    warning_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    alert_id BIGINT NOT NULL,

    site_type ENUM('PROJECT', 'GND') NOT NULL,
    site_name VARCHAR(255) NOT NULL,
    project_id INT,

    warning_type ENUM(
        'INSIDE_ALERT_POLYGON',
        'NEAR_ALERT_POLYGON'
    ) NOT NULL,

    distance_km DOUBLE NOT NULL,

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (alert_id)
        REFERENCES alerts(alert_id)
        ON DELETE CASCADE,
    FOREIGN KEY (project_id)
        REFERENCES project_sites(project_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feed_cache (
    feed_slug VARCHAR(100) PRIMARY KEY,
    etag VARCHAR(255),

    last_modified VARCHAR(255),

    updated_at TIMESTAMP
    DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL
);

-- CREATE INDEX idx_alert_effective ON alerts(effective);

-- CREATE INDEX idx_alert_expires ON alerts(expires);

-- CREATE INDEX idx_alert_state ON alerts(state_id);

-- CREATE INDEX idx_state_selected ON states(is_selected);