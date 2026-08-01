import agents.config
from agents.tracing.agent import tracer


class AnalyticsAgent:

    def __init__(self):
        print("  [Analytics] Initializing ClickHouse client...", flush=True)
        self.ch_client = agents.config.get_clickhouse_client()
        _, _, self.or_config = agents.config.get_config()
        self.ai_client = self.or_config.get_client()

    def analyze_feature(self, query_intent: str) -> str:
        with tracer.create_trace(
            name="AnalyticsAgent", input_data={"intent": query_intent}
        ) as trace:
            ch_sql = """
            SELECT
                device_type,
                count(DISTINCT user_id) AS total_users,
                windowFunnel(86400)(
                    timestamp,
                    event_type = 'destination_card_clicked',
                    event_type = 'application_started',
                    event_type = 'document_uploaded',
                    event_type = 'purchase_completed'
                ) AS funnel_step
            FROM (
                SELECT 'destination_card_clicked' AS event_type, user_id, timestamp, device_type FROM destination_card_clicked
                UNION ALL
                SELECT 'application_started' AS event_type, user_id, timestamp, device_type FROM application_started
                UNION ALL
                SELECT 'document_uploaded' AS event_type, user_id, timestamp, device_type FROM document_uploaded
                UNION ALL
                SELECT 'purchase_completed' AS event_type, user_id, timestamp, device_type FROM purchase_completed
            )
            GROUP BY device_type
            """

            print("  [Analytics] Running ClickHouse funnel query...", flush=True)
            with trace.span(name="ClickHouse Window Funnel Query") as span_db:
                result = self.ch_client.query(ch_sql)
                data_summary = result.result_rows
                span_db.end(output={"rows": str(data_summary)})
            print("  [Analytics] ClickHouse query finished!", flush=True)

            prompt = f"""
            You are Atlys's Lead Analytics Agent writing an insight summary for Product Management.

            Query Intent: {query_intent}
            ClickHouse Funnel Aggregates (Device, Total Users, Max Step Reached):
            {data_summary}

            Write an insight summary detailing:
            1. Key drop-offs across funnel stages.
            2. Potential root causes (e.g., iOS WebKit OTP issues, Android scan failures).
            3. Direct recommendations for product/engineering.
            """

            print("  [Analytics] Generating insight with Gemini...", flush=True)
            with trace.span(name="Generate PM Insight") as span_llm:
                response = self.ai_client.models.generate_content(
                    model=self.or_config.model, contents=prompt
                )
                insight_text = response.text
                span_llm.end(output={"insight": insight_text})
            print("  [Analytics] Insight generated!", flush=True)

            trace.update(output={"insight": insight_text})
            return insight_text