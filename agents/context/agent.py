import agents.config
from agents.tracing.agent import tracer


class ContextAgent:

    def __init__(self, base_context_path: str = "base_context.md"):
        self.base_context_path = base_context_path
        _, _, self.or_config = agents.config.get_config()
        self.ai_client = self.or_config.get_client()

    def update_context(self, table_name: str, ddl: str) -> str:
        with tracer.create_trace(
            name="ContextAgent", input_data={"table_name": table_name}
        ) as trace:
            try:
                with open(self.base_context_path, "r", encoding="utf-8") as f:
                    base_context = f.read()
            except FileNotFoundError:
                base_context = "Base context layer file not found."

            prompt = f"""
            You are the Context Agent for Atlys.

            Current Base Context Layer:
            {base_context}

            New ClickHouse Schema DDL:
            {ddl}

            Tasks:
            1. Identify new metrics, entity links (`user_id`, `application_id`), and event types introduced.
            2. Note any contradictions or gaps with existing metrics/known issues.
            3. Output an updated markdown section summarizing the changelog for this schema addition.
            """

            with trace.span(name="Evolve Context Layer") as span:
                response = self.ai_client.models.generate_content(
                    model=self.or_config.model, contents=prompt
                )
                context_diff = response.text
                span.end(output={"response": context_diff})

            with open("updated_context.md", "a", encoding="utf-8") as f:
                f.write(
                    f"\n\n---\n## Context Evolution: {table_name}\n"
                    + context_diff
                )

            trace.update(output={"context_diff": context_diff})
            return context_diff