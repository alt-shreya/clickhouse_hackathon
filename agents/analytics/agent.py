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
    
    def get_funnel_metrics(self) -> Dict[str, Any]:
        """Compute conversion funnel metrics."""
        # Funnel: destination_card_clicked -> application_started -> document_uploaded -> purchase_completed
        queries = {
            "destination_card_clicked": f"SELECT count(DISTINCT user_id) FROM {self.database}.destination_card_clicked",
            "application_started": f"SELECT count(DISTINCT user_id) FROM {self.database}.application_started",
            "document_uploaded": f"SELECT count(DISTINCT user_id) FROM {self.database}.document_uploaded",
            "purchase_completed": f"SELECT count(DISTINCT user_id) FROM {self.database}.purchase_completed",
        }
        results = {}
        for step, query in queries.items():
            results[step] = self.client.command(query)
        return results
    
    def get_drop_off_rates(self) -> Dict[str, float]:
        """Calculate drop-off rates between funnel steps."""
        funnel = self.get_funnel_metrics()
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
    
    def generate_narrative_insights(self, query_results: Dict[str, Any], context: str) -> List[Insight]:
        """Use LLM to generate narrative insights from query results."""
        if not self._llm_client:
            print("No LLM client configured, falling back to basic insights")
            return []
            
        prompt = f"""
        Analyze the following query results and context to generate actionable product insights.
        
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

    def run_full_analysis(self) -> List[Insight]:
        """Run complete analysis pipeline."""
        with get_tracer().trace_span("analytics.run_full_analysis"):
            # Funnel analysis
            funnel = self.get_funnel_metrics()
            drop_offs = self.get_drop_off_rates()
            
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
            # Segment analysis
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
            
            # Now generate narrative insights using LLM
            query_results = {
                "funnel": funnel,
                "drop_offs": drop_offs,
                "segments": segments_data
            }
            
            context_summary = "No context available"
            if self.context_agent:
                context_summary = "Context loaded from ContextAgent."
            
            self.generate_narrative_insights(query_results, context_summary)
            
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