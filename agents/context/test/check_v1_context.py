import json

def inspect_v1_context(context_agent):
    # Fetch the unified context dictionary
    latest_context = context_agent.get_latest_context()
    
    print(f"=== CURRENT CONTEXT VERSION: {latest_context['context_version']} ===")
    print("\n--- Tier 1: Schema Comments ---")
    print(json.dumps(latest_context["schema_context"], indent=2))
    
    print("\n--- Tier 2: Business Rules & Metrics ---")
    print(json.dumps(latest_context["business_context"], indent=2))
    
    print("\n--- Open Context Flags ---")
    print(json.dumps(latest_context["flags"], indent=2))

    return latest_context