-- Group flow begins; organizer initiates a multi-traveller application.
CREATE TABLE atlys.group_started
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Group organizer user ID' CODEC(ZSTD(1)),
    application_id String COMMENT 'Visa application ID shared across all group travellers' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for the group application' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code for visa destination' CODEC(ZSTD(1)),
    group_size UInt8 COMMENT 'Total number of travellers in the group including organizer' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- A co-traveller is added to the group application.
CREATE TABLE atlys.traveller_added
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Group organizer user ID' CODEC(ZSTD(1)),
    application_id String COMMENT 'Visa application ID shared across all group travellers' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for the group application' CODEC(ZSTD(1)),
    traveller_index UInt8 COMMENT 'Zero-based position of traveller within the group' CODEC(ZSTD(1)),
    relation Nullable(String) COMMENT 'Relationship to group organizer (spouse, child, sibling, parent, friend)' CODEC(ZSTD(1)),
    docs_complete Nullable(UInt8) COMMENT 'Whether traveller''s documents have been fully uploaded and verified (0=false, 1=true)' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 country code for visa destination' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- A co-traveller is dropped from the group application.
CREATE TABLE atlys.traveller_removed
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Group organizer user ID' CODEC(ZSTD(1)),
    application_id String COMMENT 'Visa application ID shared across all group travellers' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for the group application' CODEC(ZSTD(1)),
    traveller_index UInt8 COMMENT 'Zero-based position of traveller within the group' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 country code for visa destination' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- The group application is submitted with all co-travellers and their documents.
CREATE TABLE atlys.group_submitted
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Group organizer user ID' CODEC(ZSTD(1)),
    application_id String COMMENT 'Visa application ID shared across all group travellers' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for the group application' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 country code for visa destination' CODEC(ZSTD(1)),
    group_size Nullable(UInt8) COMMENT 'Total number of travellers in the group including organizer' CODEC(ZSTD(1)),
    travellers_submitted UInt8 COMMENT 'Number of travellers actually submitted (may differ from group_size if some were removed)' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Daily device_type, geoip_country_code rollup for group_submitted: event count + unique users, pre-aggregated so AnalyticsAgent's segment cuts don't rescan raw events.
CREATE MATERIALIZED VIEW atlys.group_submitted_daily_segment_mv
ENGINE = AggregatingMergeTree
ORDER BY (day, device_type, geoip_country_code)

SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT
    toDate(timestamp) AS day,
    device_type, geoip_country_code,
    count() AS events,
    uniqState(user_id) AS unique_users_state
FROM atlys.group_submitted
GROUP BY day, device_type, geoip_country_code;