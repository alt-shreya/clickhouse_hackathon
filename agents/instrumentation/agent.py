import re
import agents.config
from agents.tracing.agent import tracer


class InstrumentationAgent:

    def __init__(self):
        print("  [Instrumentation] Connecting to ClickHouse...", flush=True)
        self.ch_client = agents.config.get_clickhouse_client()
        print("  [Instrumentation] ClickHouse connected!", flush=True)

        _, _, self.or_config = agents.config.get_config()
        self.ai_client = self.or_config.get_client()

    def process_spec(
        self, feature_name: str, spec_content: str, raw_ndjson: str = ""
    ) -> str:
        with tracer.create_trace(
            name="InstrumentationAgent", input_data={"feature": feature_name}
        ) as trace:
            prompt = f"""
            You are a ClickHouse Database Architect for Atlys analytics.
            Design an optimal `CREATE TABLE IF NOT EXISTS` DDL for feature: '{feature_name}'.

            Feature Spec:
            {spec_content}

            Sample Event NDJSON (if available):
            {raw_ndjson}

            Requirements:
            1. Use `Engine = MergeTree()`.
            2. Set `ORDER BY (user_id, timestamp, ...)` for analytical query alignment.
            3. Use `LowCardinality(String)` for low-cardinality fields.
            4. IMPORTANT CLICKHOUSE RULE: NEVER use `Nullable(LowCardinality(String))` or `LowCardinality(Nullable(String))`. LowCardinality should directly wrap `String`.
            5. Use explicit types: `DateTime64(3, 'UTC')`, `UInt8`, `UInt32`, `Float64`.
            6. Return ONLY the valid SQL DDL inside ```sql ``` block.
            """

            print("  [Instrumentation] Calling Gemini model...", flush=True)
            with trace.span("Generate DDL LLM Call") as span:
                response = self.ai_client.models.generate_content(
                    model=self.or_config.model, contents=prompt
                )
                ddl_text = response.text
                span.end(output={"response": ddl_text})
            print("  [Instrumentation] LLM response received!", flush=True)

            ddl_match = re.search(r"```sql\s*(.*?)\s*```", ddl_text, re.DOTALL)
            ddl = ddl_match.group(1).strip() if ddl_match else ddl_text.strip()

            # Sanitize illegal Nullable(LowCardinality(...)) types
            ddl = re.sub(
                r"Nullable\s*\(\s*LowCardinality\s*\(\s*String\s*\)\s*\)",
                "LowCardinality(String)",
                ddl,
                flags=re.IGNORECASE,
            )
            ddl = re.sub(
                r"LowCardinality\s*\(\s*Nullable\s*\(\s*String\s*\)\s*\)",
                "LowCardinality(String)",
                ddl,
                flags=re.IGNORECASE,
            )

            print("  [Instrumentation] Executing DDL on ClickHouse...", flush=True)
            self.ch_client.command(ddl)
            print("  [Instrumentation] DDL executed successfully!", flush=True)

            trace.update(output={"ddl": ddl, "status": "executed"})
            return ddl