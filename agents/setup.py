"""
Reproducible setup for the control-plane tables the agents depend on:
- agent_control.context_layer   (Tier-2 versioned business context; ContextAgent)
- agent_control.context_flags   (open contradictions/gaps found by ContextAgent.run_audit)
- atlys.meta_context_registry   (InstrumentationAgent's registry of generated tables)

These previously existed only as hand-created tables on the live ClickHouse Cloud
service with no DDL checked into the repo. This module makes that reproducible:
call `ensure_control_tables(client)` once at the start of the pipeline (main.py
does this) and it's a no-op if everything already exists with the right shape.

Note: `context_flags.conflicting_versions` is `Array(String)`, not `Array(UInt32)`.
The column holds "entity.key" identifiers (per audit_base_context.AUDIT_PROMPT),
not version numbers -- an earlier hand-created version of this table had the wrong
type, which meant every audit flag with non-empty conflicting_keys silently failed
to insert.
"""

import clickhouse_connect


def ensure_control_tables(client) -> None:
    client.command("CREATE DATABASE IF NOT EXISTS agent_control")

    client.command("""
        CREATE TABLE IF NOT EXISTS agent_control.context_layer
        (
            version UInt32,
            entity String,
            key String,
            value String,
            value_type LowCardinality(String),
            source_table String,
            updated_by LowCardinality(String),
            change_type LowCardinality(String),
            supersedes_version Nullable(UInt32),
            confidence Float32 DEFAULT 1.,
            updated_at DateTime DEFAULT now()
        )
        ENGINE = MergeTree
        ORDER BY (entity, key, version)
    """)

    client.command("""
        CREATE TABLE IF NOT EXISTS agent_control.context_flags
        (
            flag_id UUID DEFAULT generateUUIDv4(),
            entity String,
            key String,
            flag_type LowCardinality(String),
            description String,
            conflicting_versions Array(String),
            status LowCardinality(String) DEFAULT 'open',
            detected_at DateTime DEFAULT now(),
            resolved_at Nullable(DateTime)
        )
        ENGINE = MergeTree
        ORDER BY (entity, flag_type, detected_at)
    """)

    client.command("""
        CREATE TABLE IF NOT EXISTS atlys.meta_context_registry
        (
            entity_name String,
            entity_type Enum8('table' = 1, 'metric' = 2, 'business_rule' = 3, 'materialized_view' = 4),
            kind LowCardinality(String),
            description String,
            columns Array(Tuple(name String, type String, description String)),
            source_spec LowCardinality(String),
            ordering_key String,
            partition_key String,
            ttl_expression String,
            related_entities Array(String),
            tags Array(String),
            version UInt32,
            is_current UInt8,
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        )
        ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (entity_type, entity_name, version)
    """)
    # NOTE: version-only ReplacingMergeTree(updated_at), deliberately WITHOUT the
    # optional is_deleted parameter. A prior version of this table used
    # ReplacingMergeTree(updated_at, is_current) -- binding the business flag
    # "is this the active version" to ReplacingMergeTree's is_deleted semantics.
    # register_table() always writes is_current=1, so any table re-registered
    # more than once (an entirely normal operation -- re-running a spec,
    # retrying after a partial failure) creates a duplicate-key group where the
    # winning row's is_deleted=1, and ClickHouse purges the WHOLE group on
    # merge. Confirmed live: 3 of 5 tables re-registered multiple times during
    # testing silently vanished from the registry within minutes, while
    # once-only registrations survived. _load_registry() already filters
    # `WHERE is_current = 1` explicitly at query time, so ReplacingMergeTree's
    # merge-time dedup only needs to keep the latest version, never delete rows.


def is_context_layer_seeded(client) -> bool:
    result = client.query("SELECT count() FROM agent_control.context_layer")
    return result.result_rows[0][0] > 0


if __name__ == "__main__":
    import os
    from agents.config import get_config

    ch_config, _, _ = get_config()
    client = clickhouse_connect.get_client(
        host=ch_config.host,
        port=ch_config.port,
        username=ch_config.user,
        password=ch_config.password,
        secure=ch_config.secure,
    )
    ensure_control_tables(client)
    print("Control-plane tables ensured.")
