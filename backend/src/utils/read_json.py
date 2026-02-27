import json
from pathlib import Path

# System Prompts Loader
def load_system_prompts() -> dict:
    """Load system prompts from JSON file."""
    prompts_path = Path(__file__).parent.parent / "static" / "system_prompts.json"

    if not prompts_path.exists():
        # Fallback to default prompts if file doesn't exist
        return {
            "system_prompt": "You are a helpful AI assistant.",
        }

    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load system prompts: {e}")
        return {
            "system_prompt": "You are a helpful AI assistant.",
        }