"""
Reproducible setup for the control-plane tables the agents depend on:
- analytics_context.business_context   (versioned business-context Markdown document; ContextAgent)
- atlys.meta_context_registry          (InstrumentationAgent's registry of generated tables)

These previously existed only as hand-created tables on the live ClickHouse Cloud
service with no DDL checked into the repo. This module makes that reproducible:
call `ensure_control_tables(client)` once at the start of the pipeline (main.py
does this) and it's a no-op if everything already exists with the right shape.

Note: agent_control.context_layer / agent_control.context_flags (the old row-per-
fact Tier-2 model + separate flags table) are retired -- superseded by
analytics_context.business_context, which stores the whole business-context
document as Markdown text per version instead of decomposing it into atomic
rows. See agents/context/agent.py for why. This module no longer creates them;
if they still exist on a given ClickHouse service from before this change, drop
them manually -- ensure_control_tables() only ever creates, never drops.
"""

import clickhouse_connect


def ensure_control_tables(client) -> None:
    client.command("CREATE DATABASE IF NOT EXISTS analytics_context")

    client.command("""
        CREATE TABLE IF NOT EXISTS analytics_context.business_context
        (
            doc_id String,
            content String,
            version UInt32,
            changelog_summary String,
            updated_at DateTime DEFAULT now()
        )
        ENGINE = ReplacingMergeTree(version)
        ORDER BY (doc_id)
    """)
    # ReplacingMergeTree(version) only -- deliberately WITHOUT the optional
    # is_deleted parameter. agents/setup.py (the old meta_context_registry
    # table) already documents the footgun this avoids: binding a table's
    # "current" semantics to ReplacingMergeTree's is_deleted purges the WHOLE
    # duplicate-key group on merge, not just the losing rows. Every read here
    # goes through ContextAgent._latest_doc()'s `ORDER BY version DESC LIMIT 1`
    # rather than relying on merge-time dedup anyway, so this table only needs
    # ReplacingMergeTree to eventually collapse old versions for storage, never
    # to decide correctness.

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


def is_business_context_seeded(client) -> bool:
    result = client.query("SELECT count() FROM analytics_context.business_context")
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
