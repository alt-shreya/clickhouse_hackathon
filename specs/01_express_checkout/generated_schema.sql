-- Express checkout button rendered to eligible user with saved payment method.
CREATE TABLE atlys.express_checkout_shown
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp (UTC)' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier (28-char string)' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique visa application identifier (32-char hex)' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of visa destination' CODEC(ZSTD(1)),
    device_type LowCardinality(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code LowCardinality(String) COMMENT 'ISO-2 country code of user''s geolocation' CODEC(ZSTD(1)),
    app_version String COMMENT 'Client application version (semantic versioning)' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from geoip' CODEC(ZSTD(1)),
    client_lib LowCardinality(String) COMMENT 'Client library identifier (mobile-rn, web-js)' CODEC(ZSTD(1)),
    eligible UInt8 COMMENT 'Whether user is eligible for express checkout (has saved payment method)' CODEC(ZSTD(1)),
    shown_amount Float64 COMMENT 'Amount displayed to user when express checkout is shown' CODEC(ZSTD(1)),
    currency LowCardinality(String) COMMENT 'ISO-4217 currency code' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- User taps Express button and commits to express checkout flow.
CREATE TABLE atlys.express_checkout_selected
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp (UTC)' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier (28-char string)' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique visa application identifier (32-char hex)' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of visa destination' CODEC(ZSTD(1)),
    device_type LowCardinality(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code LowCardinality(String) COMMENT 'ISO-2 country code of user''s geolocation' CODEC(ZSTD(1)),
    app_version String COMMENT 'Client application version (semantic versioning)' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from geoip' CODEC(ZSTD(1)),
    client_lib LowCardinality(String) COMMENT 'Client library identifier (mobile-rn, web-js)' CODEC(ZSTD(1)),
    saved_method_type LowCardinality(String) COMMENT 'Type of saved payment instrument (card, upi, wallet)' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Saved payment instrument is loaded and ready for OTP verification.
CREATE TABLE atlys.saved_method_used
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp (UTC)' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier (28-char string)' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique visa application identifier (32-char hex)' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of visa destination' CODEC(ZSTD(1)),
    device_type LowCardinality(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code LowCardinality(String) COMMENT 'ISO-2 country code of user''s geolocation' CODEC(ZSTD(1)),
    app_version String COMMENT 'Client application version (semantic versioning)' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from geoip' CODEC(ZSTD(1)),
    client_lib LowCardinality(String) COMMENT 'Client library identifier (mobile-rn, web-js)' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- User submits OTP for payment verification in express checkout.
CREATE TABLE atlys.otp_entered
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp (UTC)' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier (28-char string)' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique visa application identifier (32-char hex)' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of visa destination' CODEC(ZSTD(1)),
    device_type LowCardinality(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code LowCardinality(String) COMMENT 'ISO-2 country code of user''s geolocation' CODEC(ZSTD(1)),
    app_version String COMMENT 'Client application version (semantic versioning)' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from geoip' CODEC(ZSTD(1)),
    client_lib LowCardinality(String) COMMENT 'Client library identifier (mobile-rn, web-js)' CODEC(ZSTD(1)),
    otp_attempts Int32 COMMENT 'Number of OTP submission attempts' CODEC(ZSTD(1)),
    otp_success UInt8 COMMENT 'Whether OTP verification succeeded' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Payment succeeds via express checkout; conversion event for express flow.
CREATE TABLE atlys.express_payment_confirmed
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp (UTC)' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier (28-char string)' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique visa application identifier (32-char hex)' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of visa destination' CODEC(ZSTD(1)),
    device_type LowCardinality(String) COMMENT 'Device platform (ios, android, web-user-b2c, Desktop)' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code LowCardinality(String) COMMENT 'ISO-2 country code of user''s geolocation' CODEC(ZSTD(1)),
    app_version String COMMENT 'Client application version (semantic versioning)' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from geoip' CODEC(ZSTD(1)),
    client_lib LowCardinality(String) COMMENT 'Client library identifier (mobile-rn, web-js)' CODEC(ZSTD(1)),
    payment_amount Float64 COMMENT 'Final payment amount charged' CODEC(ZSTD(1)),
    payment_currency LowCardinality(String) COMMENT 'Currency of payment transaction' CODEC(ZSTD(1)),
    latency_ms Int32 COMMENT 'Payment processing latency in milliseconds' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;