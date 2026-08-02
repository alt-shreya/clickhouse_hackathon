-- Event table for share_clicked
CREATE TABLE atlys.share_clicked
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    share_id Nullable(String) COMMENT 'From share_clicked.share_id',
    status_shared Nullable(String) COMMENT 'From share_clicked.status_shared'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Event table for channel_selected
CREATE TABLE atlys.channel_selected
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    share_id Nullable(String) COMMENT 'From channel_selected.share_id',
    status_shared Nullable(String) COMMENT 'From channel_selected.status_shared',
    channel Nullable(String) COMMENT 'From channel_selected.channel'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Event table for link_generated
CREATE TABLE atlys.link_generated
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    share_id Nullable(String) COMMENT 'From link_generated.share_id',
    status_shared Nullable(String) COMMENT 'From link_generated.status_shared',
    channel Nullable(String) COMMENT 'From link_generated.channel'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Event table for link_opened
CREATE TABLE atlys.link_opened
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id Nullable(String) COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    destination Nullable(String) COMMENT 'Destination country',
    share_id Nullable(String) COMMENT 'From link_opened.share_id',
    channel Nullable(String) COMMENT 'From link_opened.channel',
    recipient_is_new_user Nullable(UInt8) COMMENT 'From link_opened.recipient_is_new_user'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp);

-- Event table for recipient_cta_clicked
CREATE TABLE atlys.recipient_cta_clicked
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id Nullable(String) COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    destination Nullable(String) COMMENT 'Destination country',
    share_id Nullable(String) COMMENT 'From recipient_cta_clicked.share_id',
    cta Nullable(String) COMMENT 'From recipient_cta_clicked.cta'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp);