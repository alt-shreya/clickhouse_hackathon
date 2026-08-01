"""
Tier-2 v1 loader for agent_control.context_layer.
Entity/table/column descriptions are NOT here -- they live as native COMMENTs
on atlys.* tables/columns (see schema_comments.sql). This file only holds
business logic that has no natural home in schema metadata: metric formulas,
known issues, the join map, and analysis guidance. Zero LLM calls.
"""

import clickhouse_connect
from datetime import datetime, timezone

# (entity, key, value, value_type, source_table)
ROWS = [
    # --- Metrics (§4) — kept as-is, including the contradiction, not resolved ---
    ("metric.conversion_rate", "formula", "completed purchases / sessions. Headline number reported to leadership. NOTE: 'session' is not defined anywhere in base context as a concrete field.", "metric_definition", "purchase_completed"),
    ("metric.funnel_conversion_rate", "formula", "purchase_completed users / application_started users. This is the denominator actually used in the drop-off dashboards -- DIFFERS from metric.conversion_rate above (session-based).", "metric_definition", "purchase_completed"),
    ("metric.dropoff_rate", "formula", "1 - (distinct user_id at stage N+1 / distinct user_id at stage N), counted in funnel order within a window.", "metric_definition", ""),
    ("metric.step_through_rate", "formula", "distinct user_id at stage N+1 / distinct user_id at stage N.", "metric_definition", ""),
    ("metric.passport_capture_pass_rate", "formula", "document_uploaded rows where is_crossed_failed_attempt_threshold = 0, divided by all document_uploaded rows.", "metric_definition", "document_uploaded"),
    ("metric.on_time_delivery_rate", "formula", "applications issued on/before visa_issuance_eta_days / applications issued. NOT computable from funnel tables -- sourced from post-purchase fulfilment systems, out of scope here.", "metric_definition", ""),
    ("metric.revenue_per_conversion", "formula", "`value` field on purchase_completed, in the event's own currency (not normalized).", "metric_definition", "purchase_completed"),

    # --- Known issues (§5) ---
    ("known_issue.K1", "ios_webkit_otp_regression", "Recent iOS builds: payment OTP field fails to autofill, causing abandons at pay step. Gulf card users most exposed. Watch pay_now_clicked -> purchase_completed for iOS.", "business_rule", "pay_now_clicked"),
    ("known_issue.K2", "passport_scan_model_update", "On-device passport model updated early April 2026. Some Android devices report more capture failures since; being monitored.", "business_rule", "document_uploaded"),
    ("known_issue.K3", "mrz_ocr_non_latin", "Passports with non-Latin machine-readable zones need more capture retries.", "business_rule", "document_uploaded"),
    ("known_issue.K4", "schengen_summer_slot_scarcity", "Schengen appointment slots scarce Apr-Jun. Expect seasonal softness, not a bug.", "business_rule", "destination_card_clicked"),
    ("known_issue.K5", "whatsapp_nudge_launch", "WhatsApp re-engagement nudge live since Feb 2026; can lift returns to funnel for previously-dropped users.", "business_rule", ""),
    ("known_issue.K6", "summer20_coupon_campaign", "SUMMER20 promo ran Q2; expect elevated coupon_applied and lower realised value.", "business_rule", "purchase_completed"),
    ("known_issue.K7", "app_745_rollout", "App version 7.45.x rolled out mid-quarter; minor funnel-timing shifts expected around rollout.", "business_rule", ""),

    # --- Relationships / join map (§6) ---
    ("relationship.user_id", "join_map", "destination_card_clicked.user_id joins to all eight tables on user_id.", "entity_relationship", ""),
    ("relationship.application_id", "join_map", "application_started.application_id joins to document_uploaded, pay_now_clicked, purchase_completed on application_id.", "entity_relationship", ""),
    ("relationship.supporting_tables", "join_map", "search_typed, landing_page_scrolled, auth_completed join on user_id only; application_id may be empty since they can precede an application.", "entity_relationship", ""),
    ("relationship.funnel_order", "join_map", "Funnel order is by timestamp ascending within a user_id / application_id.", "entity_relationship", ""),
    ("relationship.segment_cuts", "available_cuts", "device_type, os, geoip_country_code, destination, citizenship, co_travelers, acquisition (gclid present => paid search).", "entity_relationship", ""),

    # --- Analysis guidance (§7) ---
    ("analysis_guidance", "funnel_computation", "Compute step counts as uniq(user_id) (or application_id past application start) per stage in timestamp order. Prefer windowFunnel/sequenceMatch over per-table row dumps.", "business_rule", ""),
    ("analysis_guidance", "required_cuts", "Always cut by at least device, geo, and destination before concluding.", "business_rule", ""),
    ("analysis_guidance", "token_discipline", "Push aggregation into ClickHouse; interpret the aggregates, don't read raw rows.", "business_rule", ""),
]


def build_insert_rows(rows, version=1, updated_by="base_load"):
    now = datetime.now(timezone.utc)
    out = []
    for entity, key, value, value_type, source_table in rows:
        out.append({
            "version": version, "entity": entity, "key": key, "value": value,
            "value_type": value_type, "source_table": source_table,
            "updated_by": updated_by, "change_type": "insert",
            "supersedes_version": None, "confidence": 1.0, "updated_at": now,
        })
    return out


def load(client):
    records = build_insert_rows(ROWS)
    client.insert(
        "agent_control.context_layer",
        [list(r.values()) for r in records],
        column_names=list(records[0].keys()),
    )
    print(f"Loaded {len(records)} Tier-2 context rows as version=1.")


if __name__ == "__main__":
    client = clickhouse_connect.get_client(
        host="<your-service-host>", username="<user>", password="<password>", database="atlys",
    )
    load(client)