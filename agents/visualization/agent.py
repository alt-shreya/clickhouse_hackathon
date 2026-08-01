"""
Visualization Agent
Visualization layer for the entire pipeline.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json


@dataclass
class VisualizationSpec:
    """Specification for a visualization."""
    id: str
    title: str
    type: str  # chart, table, metric, funnel, heatmap
    query: str
    config: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


class VisualizationAgent:
    """Agent that creates and manages visualizations."""
    
    def __init__(self, client, database: str, output_dir: str = "visualizations"):
        self.client = client
        self.database = database
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.specs: Dict[str, VisualizationSpec] = {}
    
    def create_funnel_viz(self, viz_id: str = "conversion_funnel") -> VisualizationSpec:
        """Create funnel visualization spec."""
        spec = VisualizationSpec(
            id=viz_id,
            title="Conversion Funnel",
            type="funnel",
            query=f"""
            SELECT 
                'Destination Card Clicked' as step,
                count(DISTINCT user_id) as users
            FROM {self.database}.destination_card_clicked
            UNION ALL
            SELECT 
                'Application Started' as step,
                count(DISTINCT user_id) as users
            FROM {self.database}.application_started
            UNION ALL
            SELECT 
                'Document Uploaded' as step,
                count(DISTINCT user_id) as users
            FROM {self.database}.document_uploaded
            UNION ALL
            SELECT 
                'Purchase Completed' as step,
                count(DISTINCT user_id) as users
            FROM {self.database}.purchase_completed
            """,
            config={
                "step_field": "step",
                "value_field": "users",
                "orientation": "vertical",
            },
            description="User conversion through the purchase funnel"
        )
        self.specs[viz_id] = spec
        return spec
    
    def create_segment_bar_chart(self, table: str, segment: str, 
                                  viz_id: str = None) -> VisualizationSpec:
        """Create bar chart for segment analysis."""
        vid = viz_id or f"{table}_by_{segment}"
        spec = VisualizationSpec(
            id=vid,
            title=f"{table} by {segment}",
            type="bar",
            query=f"""
            SELECT 
                {segment} as segment,
                count(DISTINCT user_id) as users,
                count() as events
            FROM {self.database}.{table}
            WHERE {segment} IS NOT NULL
            GROUP BY {segment}
            ORDER BY users DESC
            LIMIT 20
            """,
            config={
                "x_field": "segment",
                "y_field": "users",
                "color_field": None,
            },
            description=f"Distribution of {table} across {segment}"
        )
        self.specs[vid] = spec
        return spec
    
    def create_time_series(self, table: str, metric: str, 
                           time_col: str = "timestamp",
                           viz_id: str = None) -> VisualizationSpec:
        """Create time series visualization."""
        vid = viz_id or f"{table}_{metric}_over_time"
        spec = VisualizationSpec(
            id=vid,
            title=f"{metric} over time ({table})",
            type="line",
            query=f"""
            SELECT 
                toStartOfHour({time_col}) as hour,
                {metric} as value
            FROM {self.database}.{table}
            WHERE {time_col} >= now() - INTERVAL 7 DAY
            ORDER BY hour
            """,
            config={
                "x_field": "hour",
                "y_field": "value",
                "time_format": "%Y-%m-%d %H:00",
            },
            description=f"Time series of {metric} from {table}"
        )
        self.specs[vid] = spec
        return spec
    
    def create_heatmap(self, table: str, x_field: str, y_field: str,
                       viz_id: str = None) -> VisualizationSpec:
        """Create heatmap visualization."""
        vid = viz_id or f"{table}_heatmap_{x_field}_vs_{y_field}"
        spec = VisualizationSpec(
            id=vid,
            title=f"Heatmap: {x_field} vs {y_field} ({table})",
            type="heatmap",
            query=f"""
            SELECT 
                {x_field} as x,
                {y_field} as y,
                count(DISTINCT user_id) as users
            FROM {self.database}.{table}
            WHERE {x_field} IS NOT NULL AND {y_field} IS NOT NULL
            GROUP BY {x_field}, {y_field}
            ORDER BY users DESC
            """,
            config={
                "x_field": "x",
                "y_field": "y",
                "value_field": "users",
            },
            description=f"Cross-tabulation of {x_field} and {y_field}"
        )
        self.specs[vid] = spec
        return spec
    
    def create_metric_card(self, name: str, query: str, 
                           viz_id: str = None) -> VisualizationSpec:
        """Create single metric card."""
        vid = viz_id or f"metric_{name.lower().replace(' ', '_')}"
        spec = VisualizationSpec(
            id=vid,
            title=name,
            type="metric",
            query=query,
            config={
                "format": "number",
                "precision": 0,
            },
            description=f"Metric: {name}"
        )
        self.specs[vid] = spec
        return spec
    
    def execute_viz(self, viz_id: str) -> List[Dict]:
        """Execute a visualization query and return data."""
        if viz_id not in self.specs:
            raise ValueError(f"Visualization {viz_id} not found")
        spec = self.specs[viz_id]
        
        result = self.client.query(spec.query)
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]
    
    def export_specs(self, output_path: Path = None):
        """Export all visualization specs to JSON."""
        path = output_path or self.output_dir / "viz_specs.json"
        data = {
            vid: {
                "id": spec.id,
                "title": spec.title,
                "type": spec.type,
                "query": spec.query,
                "config": spec.config,
                "description": spec.description,
            }
            for vid, spec in self.specs.items()
        }
        path.write_text(json.dumps(data, indent=2))
        return path
    
    def export_data(self, viz_id: str, output_path: Path = None, format: str = "json"):
        """Export visualization data."""
        data = self.execute_viz(viz_id)
        path = output_path or self.output_dir / f"{viz_id}.{format}"
        
        if format == "json":
            path.write_text(json.dumps(data, indent=2, default=str))
        elif format == "csv":
            import csv
            if data:
                with open(path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
        return path
    
    def generate_dashboard_html(self, output_path: Path = None) -> Path:
        """Generate a simple HTML dashboard."""
        path = output_path or self.output_dir / "dashboard.html"
        
        # Execute all visualizations to get sample data
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Atlys Click-a-thon Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .viz { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .viz-title { font-size: 1.2em; font-weight: 600; margin-bottom: 10px; }
        .viz-desc { color: #666; margin-bottom: 15px; }
        canvas { max-width: 100%; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }
        .metric-value { font-size: 2.5em; font-weight: 700; color: #2563eb; }
        .metric-label { color: #666; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Atlys Click-a-thon 2026 Dashboard</h1>
        <div id="visualizations">
"""
        
        for vid, spec in self.specs.items():
            html += f'        <div class="viz" id="{vid}">\n'
            html += f'            <div class="viz-title">{spec.title}</div>\n'
            html += f'            <div class="viz-desc">{spec.description}</div>\n'
            
            if spec.type == "metric":
                html += '            <div class="metric-card"><div class="metric-value" id="metric-' + vid + '">Loading...</div><div class="metric-label">' + spec.title + '</div></div>\n'
            elif spec.type in ("bar", "line", "funnel"):
                html += f'            <canvas id="chart-{vid}" width="800" height="400"></canvas>\n'
            
            html += '        </div>\n'
        
        html += """        </div>
    </div>
    <script>
        // This would be populated with actual data from the API
        console.log('Dashboard loaded. Connect to API to populate charts.');
    </script>
</body>
</html>
"""
        path.write_text(html)
        return path
    
    def setup_default_visualizations(self):
        """Create a standard set of visualizations."""
        # Funnel
        self.create_funnel_viz()
        
        # Key metrics
        self.create_metric_card(
            "Total Users",
            f"SELECT count(DISTINCT user_id) FROM {self.database}.destination_card_clicked"
        )
        self.create_metric_card(
            "Conversion Rate",
            f"SELECT round(100 * (SELECT count(DISTINCT user_id) FROM {self.database}.purchase_completed) / (SELECT count(DISTINCT user_id) FROM {self.database}.destination_card_clicked), 2)"
        )
        
        # Segment charts
        for table in ["destination_card_clicked", "application_started", "purchase_completed"]:
            for segment in ["device_type", "geoip_country_code", "funnel_type"]:
                self.create_segment_bar_chart(table, segment)
        
        # Time series
        for table in ["destination_card_clicked", "application_started", "purchase_completed"]:
            self.create_time_series(table, "count()", "timestamp", f"{table}_events_over_time")
        
        # Heatmaps
        self.create_heatmap("destination_card_clicked", "device_type", "geoip_country_code")
        self.create_heatmap("application_started", "funnel_type", "device_type")