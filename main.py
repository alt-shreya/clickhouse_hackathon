import os
import sys
from agents.analytics.agent import AnalyticsAgent
from agents.context.agent import ContextAgent
from agents.instrumentation.agent import InstrumentationAgent
from agents.visualization.dashboard_builder import print_summary_dashboard


def run_pipeline_for_spec(spec_dir: str):
    spec_path = os.path.join(spec_dir, "spec.md")
    feature_name = os.path.basename(os.path.normpath(spec_dir))

    if not os.path.exists(spec_path):
        print(f"Error: {spec_path} not found.")
        return

    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    print(f"\n🚀 Running Pipeline for Spec: {feature_name}")

    # 1. Instrumentation
    instrumentation_agent = InstrumentationAgent()
    ddl = instrumentation_agent.process_spec(feature_name, spec_content)

    # 2. Context Evolution
    context_agent = ContextAgent()
    context_diff = context_agent.update_context(feature_name, ddl)

    # 3. Analytics
    analytics_agent = AnalyticsAgent()
    insight = analytics_agent.analyze_feature(
        f"Analyze drop-off and performance for {feature_name}"
    )

    # 4. Visualization Output
    print_summary_dashboard(feature_name, ddl, context_diff, insight)

    # Save output insight summary
    insight_path = os.path.join(spec_dir, "insight_summary.md")
    with open(insight_path, "w", encoding="utf-8") as f:
        f.write(insight)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_spec = sys.argv[1]
        run_pipeline_for_spec(target_spec)
    else:
        run_pipeline_for_spec("specs/01_express_checkout")