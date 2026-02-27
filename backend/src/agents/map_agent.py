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
    search_places_by_text,
    search_nearby_places,
    geocode_location,
    get_place_details,
    _nominatim_search_structured,
)

TOOLS = [
    search_places_by_text,
    search_nearby_places,
    geocode_location,
    get_place_details,
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

        # Pattern 1: numbered list with name (possibly bold markdown), then coordinates line
        # "1. **Place Name**\n   - Coordinates: 41.01, 28.97"
        # "1. Place Name\n   📍 Coordinates: 41.01, 28.97"
        coord_blocks = re.findall(
            r"\d+\.\s+\*{0,2}(.+?)\*{0,2}\s*\n(?:.*\n)*?.*?(?:📍|🧭|Coordinates?|Koordinat)[^\d]*([\d]+\.[\d]+),\s*([\d]+\.[\d]+)",
            content,
            re.MULTILINE,
        )
        for name, lat, lon in coord_blocks:
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

        # Pattern 2: "Latitude: 41.01\n   Longitude: 28.97" (geocode_location output)
        geo_blocks = re.findall(
            r"📍\s+(.+?)\n[^\n]*?Latitude[^\n]*?([\d]+\.[\d]+)\n[^\n]*?Longitude[^\n]*?([\d]+\.[\d]+)",
            content,
            re.MULTILINE,
        )
        for name, lat, lon in geo_blocks:
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

        # Extract structured places from tool outputs (ToolMessage) first, then fallback to AI messages
        tool_messages = [m for m in messages if type(m).__name__ == "ToolMessage" and getattr(m, "content", "")]
        structured_places = _extract_places_from_messages(tool_messages)
        if not structured_places:
            final_ai_messages = [m for m in messages if type(m).__name__ == "AIMessage" and getattr(m, "content", "")]
            structured_places = _extract_places_from_messages(final_ai_messages)

    except Exception as e:
        response_text = f"Agent error: {str(e)}"

    # Fallback: direct Nominatim search only if agent completely failed (exception) and returned no places
    agent_failed = response_text.startswith("Agent error:")
    if not structured_places and agent_failed:
        try:
            from src.tools.map_tools import _translate_query
            translated = _translate_query(prompt)
            nominatim_places = _nominatim_search_structured(translated)
            if not nominatim_places and translated != prompt:
                nominatim_places = _nominatim_search_structured(prompt)
            if nominatim_places:
                structured_places = nominatim_places
                if not response_text or "sonuç bulamadım" in response_text.lower() or "no results" in response_text.lower() or "error" in response_text.lower():
                    lines = [f"Places found for '{prompt}':\n"]
                    for i, p in enumerate(nominatim_places, 1):
                        lines.append(f"{i}. {p['name']}\n   📍 Coordinates: {p['lat']}, {p['lon']}\n")
                    response_text = "\n".join(lines)
        except Exception as e:
            if not response_text:
                response_text = f"Search failed: {str(e)}"

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
    }
