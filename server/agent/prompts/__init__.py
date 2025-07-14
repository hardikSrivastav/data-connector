"""
Prompt templates for LLM interactions.
"""

import os
from pathlib import Path

# Get the directory containing this file
PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Templates directory
TEMPLATES_DIR = os.path.join(PROMPTS_DIR, "templates")

# List of available templates
TEMPLATES = {
    # Core templates
    "nl2sql.tpl": os.path.join(PROMPTS_DIR, "nl2sql.tpl"),
    "mongo_query.tpl": os.path.join(PROMPTS_DIR, "mongo_query.tpl"),
    "vector_search.tpl": os.path.join(PROMPTS_DIR, "vector_search.tpl"),
    "slack_query.tpl": os.path.join(PROMPTS_DIR, "slack_query.tpl"),
    "slack_semantic_query.tpl": os.path.join(PROMPTS_DIR, "slack_semantic_query.tpl"),
    "schema_classifier.tpl": os.path.join(PROMPTS_DIR, "schema_classifier.tpl"),
    
    # Orchestration templates
    "orchestration_system.tpl": os.path.join(PROMPTS_DIR, "orchestration_system.tpl"),
    "orchestration_plan.tpl": os.path.join(PROMPTS_DIR, "orchestration_plan.tpl"),
    "plan_optimization.tpl": os.path.join(PROMPTS_DIR, "plan_optimization.tpl"),
    "result_aggregator.tpl": os.path.join(PROMPTS_DIR, "result_aggregator.tpl"),
    "validation_check.tpl": os.path.join(PROMPTS_DIR, "validation_check.tpl"),
    "dry_run_analysis.tpl": os.path.join(PROMPTS_DIR, "dry_run_analysis.tpl"),
    
    # API adapter templates
    "uniware_query.tpl": os.path.join(TEMPLATES_DIR, "uniware_query.tpl"),
    "payu_query.tpl": os.path.join(TEMPLATES_DIR, "payu_query.tpl"),
    "easebuzz_query.tpl": os.path.join(TEMPLATES_DIR, "easebuzz_query.tpl"),
    "shiprocket_query.tpl": os.path.join(TEMPLATES_DIR, "shiprocket_query.tpl"),
}

def get_template_path(template_name: str) -> str:
    """
    Get the full path to a template file.
    
    Args:
        template_name: Name of the template file
        
    Returns:
        Full path to the template file
    """
    if template_name not in TEMPLATES:
        raise ValueError(f"Template not found: {template_name}")
        
    return TEMPLATES[template_name]
