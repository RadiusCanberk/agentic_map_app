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
    filter_places_by_category,
)

TOOLS = [
    get_area_polygon,
    get_country_for_area,
    search_places_in_polygon,
    filter_places_by_category,
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
    Extracts places from ToolMessage JSON outputs (search_places_in_polygon, filter_places_by_category).
    Prioritizes filtered results (from filter_places_by_category) over raw results (from search_places_in_polygon).
    """
    places = []
    seen = set()

    # Collect all JSON arrays from tool messages
    json_arrays = []
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
        if not content.strip().startswith("["):
            continue

        try:
            # Extract JSON from content start until we find a non-JSON character
            # This handles cases where JSON is followed by text
            json_str = content.strip()
            # Find where valid JSON ends (look for closing bracket followed by non-whitespace)
            for i in range(len(json_str), 0, -1):
                try:
                    data = json.loads(json_str[:i])
                    if isinstance(data, list) and len(data) > 0:
                        json_arrays.append(data)
                    break
                except json.JSONDecodeError:
                    continue
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON array, skip silently
            pass

    # If we have multiple JSON arrays, use the last one (from filter_places_by_category)
    # Otherwise, use the first one (from search_places_in_polygon)
    if json_arrays:
        data = json_arrays[-1] if len(json_arrays) > 1 else json_arrays[0]
        for item in data:
            if isinstance(item, dict):
                place = _extract_place_from_item(item)
                if place:
                    key = (round(place["lat"], 4), round(place["lon"], 4))
                    if key not in seen:
                        seen.add(key)
                        places.append(place)

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
        
        if "Polygon found for" in content:
            try:
                # Find the JSON part
                match = re.search(r"Polygon found for .*?: (\{.*\})", content)
                if match:
                    return json.loads(match.group(1))
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
        "places": structured_places or None,
        "polygon": polygon,
    }
