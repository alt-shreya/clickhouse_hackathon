-- Coupon input field rendered on checkout screen.
CREATE TABLE atlys.coupon_field_shown
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD),
    user_id String COMMENT 'Traveller identifier' CODEC(ZSTD),
    application_id String COMMENT 'Visa application identifier' CODEC(ZSTD),
    device_type Nullable(String) COMMENT 'Device type (ios, android, web)' CODEC(ZSTD),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD),
    app_version Nullable(String) COMMENT 'Application version' CODEC(ZSTD),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from GeoIP' CODEC(ZSTD),
    city Nullable(String) COMMENT 'City from GeoIP' CODEC(ZSTD),
    client_lib Nullable(String) COMMENT 'Client library identifier' CODEC(ZSTD),
    destination Nullable(String) COMMENT 'Target destination ISO-2 code' CODEC(ZSTD),
    cart_value Nullable(Float64) COMMENT 'Original cart value before discount' CODEC(ZSTD),
    currency Nullable(String) COMMENT 'ISO 4217 currency code' CODEC(ZSTD)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- User submits a coupon code for validation at checkout.
CREATE TABLE atlys.coupon_entered
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD),
    user_id String COMMENT 'Traveller identifier' CODEC(ZSTD),
    application_id String COMMENT 'Visa application identifier' CODEC(ZSTD),
    device_type Nullable(String) COMMENT 'Device type (ios, android, web)' CODEC(ZSTD),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD),
    app_version Nullable(String) COMMENT 'Application version' CODEC(ZSTD),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from GeoIP' CODEC(ZSTD),
    city Nullable(String) COMMENT 'City from GeoIP' CODEC(ZSTD),
    client_lib Nullable(String) COMMENT 'Client library identifier' CODEC(ZSTD),
    destination Nullable(String) COMMENT 'Target destination ISO-2 code' CODEC(ZSTD),
    coupon_code Nullable(String) COMMENT 'Promotional code entered by user' CODEC(ZSTD),
    cart_value Nullable(Float64) COMMENT 'Original cart value before discount' CODEC(ZSTD),
    currency Nullable(String) COMMENT 'ISO 4217 currency code' CODEC(ZSTD)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Coupon code validated and discount computed and applied.
CREATE TABLE atlys.coupon_applied
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD),
    user_id String COMMENT 'Traveller identifier' CODEC(ZSTD),
    application_id String COMMENT 'Visa application identifier' CODEC(ZSTD),
    device_type Nullable(String) COMMENT 'Device type (ios, android, web)' CODEC(ZSTD),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD),
    app_version Nullable(String) COMMENT 'Application version' CODEC(ZSTD),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from GeoIP' CODEC(ZSTD),
    city Nullable(String) COMMENT 'City from GeoIP' CODEC(ZSTD),
    client_lib Nullable(String) COMMENT 'Client library identifier' CODEC(ZSTD),
    destination Nullable(String) COMMENT 'Target destination ISO-2 code' CODEC(ZSTD),
    coupon_code Nullable(String) COMMENT 'Promotional code applied' CODEC(ZSTD),
    discount_type Nullable(String) COMMENT 'Type of discount: percent or flat' CODEC(ZSTD),
    discount_amount Nullable(Float64) COMMENT 'Absolute discount amount in transaction currency' CODEC(ZSTD),
    cart_value Nullable(Float64) COMMENT 'Original cart value before discount' CODEC(ZSTD),
    currency Nullable(String) COMMENT 'ISO 4217 currency code' CODEC(ZSTD)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Coupon code fails validation with rejection reason.
CREATE TABLE atlys.coupon_rejected
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD),
    user_id String COMMENT 'Traveller identifier' CODEC(ZSTD),
    application_id String COMMENT 'Visa application identifier' CODEC(ZSTD),
    device_type Nullable(String) COMMENT 'Device type (ios, android, web)' CODEC(ZSTD),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD),
    app_version Nullable(String) COMMENT 'Application version' CODEC(ZSTD),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from GeoIP' CODEC(ZSTD),
    city Nullable(String) COMMENT 'City from GeoIP' CODEC(ZSTD),
    client_lib Nullable(String) COMMENT 'Client library identifier' CODEC(ZSTD),
    destination Nullable(String) COMMENT 'Target destination ISO-2 code' CODEC(ZSTD),
    coupon_code Nullable(String) COMMENT 'Promotional code that was rejected' CODEC(ZSTD),
    reject_reason Nullable(String) COMMENT 'Reason coupon validation failed: expired, invalid_code, min_cart_not_met, already_used' CODEC(ZSTD),
    cart_value Nullable(Float64) COMMENT 'Original cart value before discount' CODEC(ZSTD),
    currency Nullable(String) COMMENT 'ISO 4217 currency code' CODEC(ZSTD)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Discounted price displayed to user after coupon validation.
CREATE TABLE atlys.discount_shown
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD),
    user_id String COMMENT 'Traveller identifier' CODEC(ZSTD),
    application_id String COMMENT 'Visa application identifier' CODEC(ZSTD),
    device_type Nullable(String) COMMENT 'Device type (ios, android, web)' CODEC(ZSTD),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD),
    app_version Nullable(String) COMMENT 'Application version' CODEC(ZSTD),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from GeoIP' CODEC(ZSTD),
    city Nullable(String) COMMENT 'City from GeoIP' CODEC(ZSTD),
    client_lib Nullable(String) COMMENT 'Client library identifier' CODEC(ZSTD),
    destination Nullable(String) COMMENT 'Target destination ISO-2 code' CODEC(ZSTD),
    coupon_code Nullable(String) COMMENT 'Promotional code applied' CODEC(ZSTD),
    discount_amount Nullable(Float64) COMMENT 'Absolute discount amount in transaction currency' CODEC(ZSTD),
    cart_value Nullable(Float64) COMMENT 'Original cart value before discount' CODEC(ZSTD),
    currency Nullable(String) COMMENT 'ISO 4217 currency code' CODEC(ZSTD)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- User proceeds to payment at checkout with or without coupon applied.
CREATE TABLE atlys.checkout_with_coupon
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD),
    user_id String COMMENT 'Traveller identifier' CODEC(ZSTD),
    application_id String COMMENT 'Visa application identifier' CODEC(ZSTD),
    device_type Nullable(String) COMMENT 'Device type (ios, android, web)' CODEC(ZSTD),
    os Nullable(String) COMMENT 'Operating system' CODEC(ZSTD),
    app_version Nullable(String) COMMENT 'Application version' CODEC(ZSTD),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from GeoIP' CODEC(ZSTD),
    city Nullable(String) COMMENT 'City from GeoIP' CODEC(ZSTD),
    client_lib Nullable(String) COMMENT 'Client library identifier' CODEC(ZSTD),
    destination Nullable(String) COMMENT 'Target destination ISO-2 code' CODEC(ZSTD),
    coupon_code Nullable(String) COMMENT 'Promotional code applied; null if no coupon used' CODEC(ZSTD),
    discount_amount Nullable(Float64) COMMENT 'Absolute discount amount in transaction currency; 0 if no discount' CODEC(ZSTD),
    cart_value Nullable(Float64) COMMENT 'Original cart value before discount' CODEC(ZSTD),
    final_value Nullable(Float64) COMMENT 'Final checkout value after discount; equals cart_value if no coupon' CODEC(ZSTD),
    currency Nullable(String) COMMENT 'ISO 4217 currency code' CODEC(ZSTD)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Daily device_type, geoip_country_code rollup for checkout_with_coupon: event count + unique users, pre-aggregated so AnalyticsAgent's segment cuts don't rescan raw events.
CREATE MATERIALIZED VIEW atlys.checkout_with_coupon_daily_segment_mv
ENGINE = AggregatingMergeTree
ORDER BY (day, device_type, geoip_country_code)

SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT
    toDate(timestamp) AS day,
    device_type, geoip_country_code,
    count() AS events,
    uniqState(user_id) AS unique_users_state
FROM atlys.checkout_with_coupon
GROUP BY day, device_type, geoip_country_code;