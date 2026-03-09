"""
Map Agent
LangChain agent that performs map searches using natural language prompts
"""
import json
import re
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from src.core.settings import OPENROUTER_API_KEY, SYSTEM_PROMPT, OPENROUTER_BASE_URL
from src.tools.map_tools import (
    get_area_polygon,
    get_country_for_area,
    search_places_in_polygon,
    filter_places_by_categories,
)

TOOLS = [
    get_country_for_area,
    get_area_polygon,
    search_places_in_polygon,
    filter_places_by_categories,
]


def create_map_agent(model_name: str):
    """Creates and returns a map agent."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set. Please check your .env file.")

    system_prompt = SYSTEM_PROMPT
    if isinstance(system_prompt, dict):
        system_prompt = system_prompt.get("system_prompt", "")

    model = ChatOpenAI(
        model=model_name,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0.7,
    )

    agent = create_react_agent(
        model=model,
        tools=TOOLS,
        prompt=system_prompt,
    )
    return agent


def _extract_places_from_tool_json(messages: list) -> list[dict]:
    """
    Extracts places from tool JSON outputs.
    Strategy: Use the LAST tool output (which should be filtered results from filter_places_by_categories).
    If that's not available, fall back to raw results from search_places_in_polygon.
    This ensures we only show filtered places when filtering is applied.
    """
    places = []
    seen = set()

    # Find all ToolMessage outputs with JSON content
    json_tool_messages = []

    for msg in messages:
        # Only process ToolMessage (tool outputs)
        if type(msg).__name__ != "ToolMessage":
            continue

        content = ""
        if hasattr(msg, "content"):
            content = msg.content or ""
        elif isinstance(msg, dict):
            content = msg.get("content", "") or ""

        if not content:
            continue

        # Skip non-JSON responses (polygon, country, error messages)
        # Accept FILTERED_DATA::: prefix or raw JSON arrays
        if "FILTERED_DATA:::" in content:
            # Extract JSON part after prefix
            json_part = content.split("FILTERED_DATA:::", 1)[1].strip()
            json_tool_messages.append(json_part)
            continue

        # Skip SEARCH_DONE::: messages (no JSON, just a status message)
        if "SEARCH_DONE:::" in content:
            continue

        if not content.strip().startswith("["):
            continue

        json_tool_messages.append(content)

    # Use the LAST JSON tool message (filtered results should be last)
    # This prevents mixing raw search results with filtered results
    if not json_tool_messages:
        return places

    content = json_tool_messages[-1]

    try:
        # Extract JSON array from content (may have formatted text after it)
        # filter_places_by_categories returns: [JSON]\n\nFormatted text
        json_str = content

        # Try to find JSON array boundaries
        bracket_count = 0
        json_end = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue

            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    json_end = i + 1
                    break

        if json_end > 0:
            json_str = content[:json_end]

        # Parse JSON array
        data = json.loads(json_str)

        # Handle list of places
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    place = _extract_place_from_item(item)
                    if place:
                        key = (round(place["lat"], 4), round(place["lon"], 4))
                        if key not in seen:
                            seen.add(key)
                            places.append(place)
    except (json.JSONDecodeError, ValueError):
        # Not valid JSON array, skip silently
        pass

    return places


def _extract_place_from_item(item: dict) -> dict | None:
    """Extracts a single place from a JSON object."""
    if not isinstance(item, dict):
        return None

    # Try different field name combinations for coordinates
    lat = None
    lon = None

    # Try standard field names
    for lat_name in ["latitude", "lat", "y"]:
        if lat_name in item:
            try:
                lat = float(item[lat_name])
                break
            except (ValueError, TypeError):
                pass

    for lon_name in ["longitude", "lon", "x"]:
        if lon_name in item:
            try:
                lon = float(item[lon_name])
                break
            except (ValueError, TypeError):
                pass

    # If coordinates found, create place object
    if lat is not None and lon is not None:
        return {
            "name": str(item.get("name", item.get("title", "Unknown"))),
            "lat": lat,
            "lon": lon,
            "address": str(item.get("address", item.get("name", ""))),
            "source": "api",
        }

    return None


def _extract_places_from_messages(messages: list) -> list[dict]:
    """Extracts structured place data from all agent messages (tool outputs + final response)."""
    places = []
    seen = set()

    for msg in messages:
        content = ""
        if hasattr(msg, "content"):
            content = msg.content or ""
        elif isinstance(msg, dict):
            content = msg.get("content", "") or ""

        if not content:
            continue

        # Pattern 1: Numbered list with coordinates
        # Match: "1. Name", then maybe some lines, then "Coordinates: lat, lon"
        coord_blocks = re.findall(
            r"^\s*(\d+\.\s+)(.+?)\s*\n(?:.*\n)*?.*?(?:📍|🧭|Coordinates?|Koordinat)[^\d\-]*?(-?\d+\.\d+),\s*(-?\d+\.\d+)",
            content,
            re.MULTILINE,
        )
        for prefix, name, lat, lon in coord_blocks:
            name = name.strip().replace("**", "")
            key = (round(float(lat), 4), round(float(lon), 4))
            if key not in seen:
                seen.add(key)
                places.append({
                    "name": name,
                    "lat": float(lat),
                    "lon": float(lon),
                    "address": name,
                    "source": "agent",
                })

        # Pattern 2: List without numbers (e.g. bold name)
        # Match: "**Name**", then maybe some lines, then "Coordinates: lat, lon"
        bold_blocks = re.findall(
            r"^\s*\*{2}(.+?)\*{2}\s*\n(?:.*\n)*?.*?(?:📍|🧭|Coordinates?|Koordinat)[^\d\-]*?(-?\d+\.\d+),\s*(-?\d+\.\d+)",
            content,
            re.MULTILINE,
        )
        for name, lat, lon in bold_blocks:
            name = name.strip()
            key = (round(float(lat), 4), round(float(lon), 4))
            if key not in seen:
                seen.add(key)
                places.append({
                    "name": name,
                    "lat": float(lat),
                    "lon": float(lon),
                    "address": name,
                    "source": "agent",
                })

    return places


def _extract_polygon_from_messages(messages: list) -> dict | None:
    """Extracts GeoJSON polygon data from agent messages."""
    for msg in messages:
        content = ""
        if hasattr(msg, "content"):
            content = msg.content or ""
        elif isinstance(msg, dict):
            content = msg.get("content", "") or ""
        
        if "POLYGON_DATA:::" in content:
            try:
                json_str = content.split("POLYGON_DATA:::", 1)[1].strip()
                return json.loads(json_str)
            except Exception:
                continue
    return None


async def run_map_agent(prompt: str, model_name: str) -> dict:
    """
    Runs the map agent with the given prompt.
    Args:
        prompt: User's natural language request
                Example: 'List the best restaurants in Kadıköy'
        model_name: OpenRouter model name to use
    Returns:
        dict: Agent's response
    """
    structured_places = []
    center = None
    response_text = ""

    polygon = None

    try:
        agent = create_map_agent(model_name)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]}
        )

        messages = result.get("messages", [])

        # Extract text from last AI message
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                response_text = last_message.content or ""
            elif isinstance(last_message, dict):
                response_text = last_message.get("content", "") or ""

        # Extract structured places from tool JSON outputs first (most reliable)
        tool_messages = [m for m in messages if type(m).__name__ == "ToolMessage" and getattr(m, "content", "")]
        final_ai_messages = [m for m in messages if type(m).__name__ == "AIMessage" and getattr(m, "content", "")]

        structured_places = _extract_places_from_tool_json(tool_messages)
        polygon = _extract_polygon_from_messages(tool_messages)

        # Fallback: extract from AI messages (text-based formatted places)
        # Only if we didn't get places from tool JSON
        if not structured_places:
            ai_places = _extract_places_from_messages(final_ai_messages)
            structured_places.extend(ai_places)

        if not polygon:
            polygon = _extract_polygon_from_messages(final_ai_messages)

        # Limit places to 300
        if structured_places:
            structured_places = structured_places[:300]

    except Exception as e:
        response_text = f"Agent error: {str(e)}"

    if not response_text:
        response_text = f"No results found for '{prompt}'."

    # Build center from first place
    if structured_places:
        first = structured_places[0]
        center = {
            "lat": first["lat"],
            "lon": first["lon"],
            "label": first["name"],
        }

    return {
        "query": prompt,
        "response": response_text,
        "center": center,
        "places": structured_places,  # Always return list (empty if no results)
        "polygon": polygon,
    }
