"""
Analytics Agent
Queries data, applies context, writes insight summaries.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json

from agents.tracing.agent import get_tracer


@dataclass
class Insight:
    """Represents an analytical insight."""
    title: str
    description: str
    metric: str
    value: Any
    context: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # info, warning, critical
    tags: List[str] = field(default_factory=list)
    query: str = ""
    timestamp: str = ""


class AnalyticsAgent:
    """Agent that analyzes data and produces actionable insights."""

    CORE_FUNNEL_STEPS = ["destination_card_clicked", "application_started", "document_uploaded", "purchase_completed"]

    def __init__(self, client, database: str, context_agent=None, openrouter_config=None):
        self.client = client
        self.database = database
        self.context_agent = context_agent
        self.insights: List[Insight] = []

        self.openrouter_config = openrouter_config
        self._llm_client = None
        if openrouter_config and openrouter_config.enabled:
            self._llm_client = openrouter_config.get_client()

    def run_query(self, query: str) -> List[Dict]:
        """Execute a query and return results as list of dicts."""
        result = self.client.query(query)
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]

    def sequential_funnel(self, steps: List[str], id_column: str = "user_id", window_days: int = 30) -> Dict[str, int]:
        """Count users reaching each step of `steps`, IN ORDER, within a
        `window_days` window -- via ClickHouse's windowFunnel(), per
        base_context.md §7's explicit guidance ("Prefer windowFunnel/
        sequenceMatch over per-table row dumps"). A prior version counted
        count(DISTINCT user_id) independently per table with no ordering/join
        constraint at all, which isn't a funnel -- it doesn't verify a user who
        appears in step N+1 ever passed through step N.
        """
        if not steps:
            return {}
        union_sql = "\nUNION ALL\n".join(
            f"SELECT {id_column}, timestamp, '{t}' AS step FROM {self.database}.{t}"
            for t in steps
        )
        conds = ", ".join(f"step = '{t}'" for t in steps)
        level_counts = ", ".join(f"countIf(level >= {i + 1}) AS step_{i + 1}" for i in range(len(steps)))
        query = f"""
        SELECT {level_counts}
        FROM (
            SELECT {id_column}, windowFunnel({window_days * 86400})(timestamp, {conds}) AS level
            FROM ( {union_sql} )
            GROUP BY {id_column}
        )
        """
        result = self.client.query(query)
        row = result.result_rows[0] if result.result_rows else [0] * len(steps)
        return dict(zip(steps, row))

    def get_funnel_metrics(self) -> Dict[str, Any]:
        """Sequential funnel over the 4 core pre-purchase steps."""
        return self.sequential_funnel(self.CORE_FUNNEL_STEPS)

    def get_drop_off_rates(self, funnel: Optional[Dict[str, int]] = None) -> Dict[str, float]:
        """Calculate drop-off rates between funnel steps."""
        funnel = funnel if funnel is not None else self.get_funnel_metrics()
        rates = {}
        steps = list(funnel.keys())
        for i in range(len(steps) - 1):
            current = funnel[steps[i]]
            next_step = funnel[steps[i + 1]]
            if current > 0:
                rates[f"{steps[i]} -> {steps[i+1]}"] = (current - next_step) / current * 100
        return rates
    
    def analyze_by_segment(self, segment_column: str, table: str) -> List[Dict]:
        """Analyze metrics broken down by a segment."""
        query = f"""
        SELECT 
            {segment_column},
            count(DISTINCT user_id) as users,
            count() as events
        FROM {self.database}.{table}
        WHERE {segment_column} IS NOT NULL
        GROUP BY {segment_column}
        ORDER BY users DESC
        LIMIT 20
        """
        return self.run_query(query)
    
    def detect_anomalies(self, table: str, metric_column: str, 
                         time_column: str = "timestamp", 
                         window: str = "1 day") -> List[Dict]:
        """Detect statistical anomalies in time series data."""
        query = f"""
        WITH stats AS (
            SELECT 
                toStartOfDay({time_column}) as day,
                avg({metric_column}) as avg_val,
                stddevPop({metric_column}) as std_val
            FROM {self.database}.{table}
            WHERE {time_column} >= now() - INTERVAL 30 DAY
            GROUP BY day
        )
        SELECT 
            day,
            avg_val,
            std_val,
            CASE WHEN avg_val > (lag(avg_val) OVER (ORDER BY day) + 2 * lag(std_val) OVER (ORDER BY day))
                 THEN 'spike'
                 WHEN avg_val < (lag(avg_val) OVER (ORDER BY day) - 2 * lag(std_val) OVER (ORDER BY day))
                 THEN 'drop'
                 ELSE 'normal'
            END as anomaly_type
        FROM stats
        ORDER BY day DESC
        LIMIT 30
        """
        return self.run_query(query)
    
    def generate_insight(self, title: str, description: str, metric: str, 
                         value: Any, severity: str = "info", **kwargs) -> Insight:
        """Create and store an insight."""
        insight = Insight(
            title=title,
            description=description,
            metric=metric,
            value=value,
            severity=severity,
            **kwargs
        )
        self.insights.append(insight)
        return insight
    
    def generate_narrative_insights(
        self, query_results: Dict[str, Any], context: str, pm_questions: Optional[List[str]] = None
    ) -> List[Insight]:
        """Use LLM to generate narrative insights from query results."""
        if not self._llm_client:
            print("No LLM client configured, falling back to basic insights")
            return []

        questions_block = ""
        if pm_questions:
            bullet_list = "\n".join(f"- {q}" for q in pm_questions)
            questions_block = f"""
        This feature's spec lists these specific questions a PM will ask. Prioritize
        insights that directly answer them over generic funnel commentary -- if the
        query results don't support answering one, say so rather than skipping it silently:
        {bullet_list}
        """

        prompt = f"""
        Analyze the following query results and context to generate actionable product insights.
        {questions_block}
        Context:
        {context}

        Query Results:
        {json.dumps(query_results, indent=2, default=str)}

        Output JSON format:
        {{
            "insights": [
                {{
                    "title": "Short title",
                    "description": "Detailed narrative insight, what it means, and suggested action.",
                    "metric": "name of key metric",
                    "value": "value of metric",
                    "severity": "info, warning, or critical",
                    "tags": ["tag1", "tag2"]
                }}
            ]
        }}
        
        CRITICAL: Return ONLY valid JSON. Do not include markdown blocks, explanations, or any other text.
        """
        
        with get_tracer().trace_span("analytics.generate_narrative_insights"):
            try:
                response = self._llm_client.chat.completions.create(
                    model=self.openrouter_config.model,
                    messages=[
                        {"role": "system", "content": "You are an expert product analyst."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                    response_format={"type": "json_object"},
                )
                
                content = response.choices[0].message.content.strip()
                # Strip markdown formatting if present
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                parsed = json.loads(content)
                
                new_insights = []
                for item in parsed.get("insights", []):
                    insight = self.generate_insight(
                        title=item.get("title", "Insight"),
                        description=item.get("description", ""),
                        metric=item.get("metric", ""),
                        value=item.get("value", ""),
                        severity=item.get("severity", "info"),
                        tags=item.get("tags", [])
                    )
                    new_insights.append(insight)
                return new_insights
            except Exception as e:
                print(f"Failed to generate narrative insights: {e}")
                return []

    def analyze_spec_tables(self, table_names: List[str]) -> Dict[str, Any]:
        """Analyze the tables InstrumentationAgent just created for the current
        spec: a sequential funnel over them (in the order given, which follows
        the spec's own event sequence) plus per-table segment breakdowns. This
        is what makes a spec's insights about *that* feature, rather than only
        ever repeating the 4 core funnel tables' generic numbers regardless of
        which spec is running.
        """
        if not table_names:
            return {}

        funnel: Dict[str, int] = {}
        drop_offs: Dict[str, float] = {}
        if len(table_names) > 1:
            try:
                funnel = self.sequential_funnel(table_names)
                drop_offs = self.get_drop_off_rates(funnel)
            except Exception as e:
                print(f"Spec funnel query failed: {e}")

        segments: Dict[str, List[Dict]] = {}
        for table in table_names:
            for segment in ("device_type", "geoip_country_code"):
                try:
                    rows = self.analyze_by_segment(segment, table)
                    if rows:
                        segments[f"{table}_{segment}"] = rows
                except Exception:
                    pass

        return {"tables": table_names, "funnel": funnel, "drop_offs": drop_offs, "segments": segments}

    def run_full_analysis(
        self,
        spec_tables: Optional[List[str]] = None,
        pm_questions: Optional[List[str]] = None,
        spec_name: str = "",
    ) -> List[Insight]:
        """Run the complete analysis pipeline: the 4 core pre-purchase funnel
        tables (always-relevant background) plus, when given, the current
        spec's own newly-instrumented tables and its "Questions the PM will
        ask". A prior version only ever analyzed the 4 core tables -- every
        spec produced the same generic funnel commentary and never actually
        answered that spec's own PM questions.
        """
        with get_tracer().trace_span("analytics.run_full_analysis", metadata={"spec_name": spec_name}):
            # Core pre-purchase funnel
            funnel = self.get_funnel_metrics()
            drop_offs = self.get_drop_off_rates(funnel)

            self.generate_insight(
                title="Conversion Funnel Overview",
                description=f"Funnel metrics: {json.dumps(funnel)}",
                metric="funnel_users",
                value=funnel,
                severity="info",
                tags=["funnel", "overview"]
            )

            for step, rate in drop_offs.items():
                severity = "warning" if rate > 50 else "info"
                self.generate_insight(
                    title=f"Drop-off: {step}",
                    description=f"{rate:.1f}% of users drop off at this step",
                    metric="drop_off_rate",
                    value=rate,
                    severity=severity,
                    tags=["funnel", "drop_off"]
                )

            segments_data = {}
            for table in ["destination_card_clicked", "application_started", "purchase_completed"]:
                for segment in ["device_type", "geoip_country_code", "funnel_type"]:
                    try:
                        segments = self.analyze_by_segment(segment, table)
                        if segments:
                            top = segments[0]
                            segments_data[f"{table}_{segment}"] = segments
                            self.generate_insight(
                                title=f"Top {segment} for {table}",
                                description=f"{top[segment]}: {top['users']} users",
                                metric=f"top_{segment}",
                                value=top,
                                severity="info",
                                tags=["segment", table, segment]
                            )
                    except Exception:
                        pass

            # The current spec's own tables -- what makes this run's insights
            # specific to the feature being analyzed.
            spec_analysis: Dict[str, Any] = {}
            if spec_tables:
                spec_analysis = self.analyze_spec_tables(spec_tables)
                if spec_analysis.get("funnel"):
                    self.generate_insight(
                        title=f"{spec_name or 'Feature'} funnel",
                        description=f"Sequential funnel over {', '.join(spec_tables)}: {json.dumps(spec_analysis['funnel'])}",
                        metric="spec_funnel_users",
                        value=spec_analysis["funnel"],
                        severity="info",
                        tags=["funnel", "spec", spec_name] if spec_name else ["funnel", "spec"],
                    )
                for step, rate in spec_analysis.get("drop_offs", {}).items():
                    severity = "warning" if rate > 50 else "info"
                    self.generate_insight(
                        title=f"{spec_name or 'Feature'} drop-off: {step}",
                        description=f"{rate:.1f}% of users drop off at this step",
                        metric="spec_drop_off_rate",
                        value=rate,
                        severity=severity,
                        tags=["funnel", "drop_off", "spec", spec_name] if spec_name else ["funnel", "drop_off", "spec"],
                    )

            # Now generate narrative insights using LLM
            query_results = {
                "core_funnel": funnel,
                "core_drop_offs": drop_offs,
                "core_segments": segments_data,
                "spec_analysis": spec_analysis,
            }

            context_summary = "No context available"
            if self.context_agent:
                entities_in_scope = list(self.CORE_FUNNEL_STEPS) + list(spec_tables or [])
                latest_context = self.context_agent.get_latest_context(entities=entities_in_scope)
                context_summary = f"Context from ContextAgent:\n{json.dumps(latest_context, indent=2, default=str)}"

            self.generate_narrative_insights(query_results, context_summary, pm_questions=pm_questions)

            return self.insights
    
    def export_insights(self, output_path: Path, format: str = "json"):
        """Export insights to file."""
        data = [
            {
                "title": i.title,
                "description": i.description,
                "metric": i.metric,
                "value": i.value,
                "severity": i.severity,
                "tags": i.tags,
                "query": i.query,
                "timestamp": i.timestamp,
            }
            for i in self.insights
        ]
        if format == "json":
            output_path.write_text(json.dumps(data, indent=2, default=str))
        elif format == "markdown":
            md = "# Analytics Insights\n\n"
            for i in self.insights:
                md += f"## {i.title} [{i.severity.upper()}]\n"
                md += f"{i.description}\n\n"
                md += f"**Metric:** {i.metric}  \n"
                md += f"**Value:** {i.value}  \n\n"
            output_path.write_text(md)