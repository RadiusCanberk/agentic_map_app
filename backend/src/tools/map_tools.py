"""
Map Agent Tools
LangChain tools for map searches using OpenStreetMap (Nominatim + Overpass)
"""
from __future__ import annotations

import json
import re
from typing import Optional, Any

import httpx
from langchain.tools import tool

from src.core.settings import NOMINATIM_EMAIL, NOMINATIM_USER_AGENT, PLACEMAKING_API_URL

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
# Multiple Overpass mirrors — tried in order until one succeeds
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = NOMINATIM_USER_AGENT or "AgenticMapApp/1.0 (contact: dev@example.com)"

# Placemaking API countries endpoint
PLACEMAKING_COUNTRIES_URL = "https://placemaking.test.brick-n-data.com/every-data/locations/get-country"
_PLACEMAKING_COUNTRIES_CACHE: list[dict] | None = None

# Cache for last search results — avoids passing large JSON through agent LLM
_LAST_SEARCH_RESULTS: list[dict] = []


def _nominatim_get(path: str, params: dict) -> dict | list:
    if NOMINATIM_EMAIL:
        params = {**params, "email": NOMINATIM_EMAIL}
    headers = {"User-Agent": USER_AGENT}
    url = f"{NOMINATIM_BASE}{path}"
    with httpx.Client(timeout=20.0, headers=headers) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _overpass_query(query: str) -> dict:
    """Tries each Overpass mirror in order; returns first successful result."""
    headers = {"User-Agent": USER_AGENT}
    last_exc: Exception | None = None
    for mirror in OVERPASS_MIRRORS:
        try:
            with httpx.Client(timeout=25.0, headers=headers) as client:
                resp = client.post(mirror, data={"data": query})
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            last_exc = exc
            continue
    raise last_exc or RuntimeError("All Overpass mirrors failed")


def _fetch_placemaking_countries() -> list[dict]:
    """Fetches and caches the list of countries from Placemaking API."""
    global _PLACEMAKING_COUNTRIES_CACHE
    if _PLACEMAKING_COUNTRIES_CACHE is not None:
        return _PLACEMAKING_COUNTRIES_CACHE

    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=10.0, headers=headers) as client:
        resp = client.get(PLACEMAKING_COUNTRIES_URL)
        resp.raise_for_status()
        data = resp.json()
        # API returns: {"result": {"is_success": true, "result": [{...}, ...]}}
        countries = []
        if isinstance(data, list):
            countries = data
        elif isinstance(data, dict):
            # Try nested structure first: data["result"]["result"]
            result = data.get("result")
            if isinstance(result, dict):
                countries = result.get("result", [])
            elif isinstance(result, list):
                countries = result
        _PLACEMAKING_COUNTRIES_CACHE = countries
    return _PLACEMAKING_COUNTRIES_CACHE


def _format_address(tags: dict) -> str:
    parts = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
        tags.get("addr:city"),
        tags.get("addr:district"),
        tags.get("addr:postcode"),
    ]
    return ", ".join([p for p in parts if p]) or "No address"


def _nominatim_search_structured(query: str) -> list[dict]:
    """Returns structured place list from Nominatim for the given query."""
    results = _nominatim_get(
        "/search",
        {"q": query, "format": "json", "addressdetails": 1, "namedetails": 1, "limit": 20},
    )
    places = []
    for place in results:
        lat = place.get("lat")
        lon = place.get("lon")
        if lat and lon:
            namedetails = place.get("namedetails", {})
            name = (
                namedetails.get("name")
                or namedetails.get("name:tr")
                or namedetails.get("name:en")
                or place.get("display_name", "Unknown").split(",")[0].strip()
            )
            places.append({
                "name": name,
                "lat": float(lat),
                "lon": float(lon),
                "address": place.get("display_name", ""),
                "source": "nominatim",
            })
    return places


_TR_TO_EN = {
    "restoran": "restaurant", "restoranlar": "restaurant",
    "kafe": "cafe", "kafeler": "cafe", "kahve": "cafe",
    "bar": "bar", "barlar": "bar",
    "fırın": "bakery", "pastane": "bakery",
    "otel": "hotel", "oteller": "hotel",
    "hastane": "hospital", "eczane": "pharmacy",
    "market": "supermarket", "süpermarket": "supermarket",
    "park": "park", "müze": "museum",
    "okul": "school", "üniversite": "university",
    "avm": "mall", "alışveriş": "mall", "merkezi": "mall",
    "spor": "gym", "fitness": "gym", "salon": "gym",
    "kütüphane": "library", "kitap": "library",
    "sinema": "cinema", "tiyatro": "theatre",
}

# Synonyms for business categories to improve filtering
_CATEGORY_SYNONYMS = {
    "restaurant": ["restaurant", "food", "dining", "eatery", "brasserie", "diner", "restoran", "yemek"],
    "cafe": ["cafe", "coffee", "tea", "bakery", "pastry", "kafe", "kahve", "pastane"],
    "bar": ["bar", "pub", "club", "nightlife", "lounge", "meyhane", "birahane"],
    "supermarket": ["supermarket", "grocery", "market", "shop", "store", "bakkal", "manav"],
    "pharmacy": ["pharmacy", "drugstore", "chemist", "apothecary", "eczane"],
    "hospital": ["hospital", "clinic", "medical", "doctor", "health", "hastane", "klinik", "sağlık"],
    "hotel": ["hotel", "motel", "hostel", "accommodation", "lodging", "inn", "otel", "pansiyon", "konaklama"],
    "gym": ["gym", "fitness", "sports", "workout", "club", "spor", "salon", "antrenman"],
    "school": ["school", "university", "college", "education", "academy", "okul", "üniversite", "eğitim"],
    "park": ["park", "garden", "recreation", "nature", "outdoor", "bahçe", "doğa"],
    # Food/cuisine specific synonyms for better filtering of specific restaurant types
    "burger": ["burger", "hamburger", "fast food", "fast_food", "burger joint", "burger bar"],
    "pizza": ["pizza", "pizzeria", "italian"],
    "kebab": ["kebab", "doner", "döner", "shawarma", "turkish grill"],
    "sushi": ["sushi", "japanese", "ramen", "asian"],
    "steak": ["steak", "steakhouse", "grill", "bbq", "barbecue"],
    "seafood": ["seafood", "fish", "balık", "deniz ürünleri"],
    "vegan": ["vegan", "vegetarian", "plant-based"],
    "bakery": ["bakery", "pastry", "bread", "fırın", "pastane"],
}


def _translate_query(query: str) -> str:
    """Translates Turkish place type keywords to English for better Nominatim results."""
    words = query.split()
    translated = []
    for w in words:
        w_lower = w.lower()
        # Exact match first
        if w_lower in _TR_TO_EN:
            translated.append(_TR_TO_EN[w_lower])
            continue
        # Stem match: check if word starts with any known Turkish keyword
        matched = False
        for tr_key, en_val in _TR_TO_EN.items():
            if w_lower.startswith(tr_key):
                translated.append(en_val)
                matched = True
                break
        if not matched:
            translated.append(w)
    return " ".join(translated)


# Mapping of English place types to Nominatim amenity tags
_AMENITY_TYPES = {
    "cafe": "cafe", "cafes": "cafe", "coffee": "cafe",
    "restaurant": "restaurant", "restaurants": "restaurant",
    "bar": "bar", "bars": "bar",
    "bakery": "bakery", "bakeries": "bakery",
    "pub": "pub", "pubs": "pub",
    "fast_food": "fast_food",
    "pharmacy": "pharmacy", "pharmacies": "pharmacy",
    "hospital": "hospital", "hospitals": "hospital",
    "school": "school", "schools": "school",
    "bank": "bank", "banks": "bank",
    "hotel": "hotel", "hotels": "hotel",
}


def _extract_amenity(query: str) -> Optional[str]:
    """Extracts amenity type from query string."""
    q_lower = query.lower()
    for keyword, amenity in _AMENITY_TYPES.items():
        if keyword in q_lower:
            return amenity
    return None


# Fallback country code to English name mapping (for when Placemaking API fails)
_COUNTRY_CODE_TO_NAME = {
    "TR": "Turkey",
    "US": "United States",
    "GB": "UK",
    "FR": "France",
    "DE": "Germany",
    "IT": "Italy",
    "ES": "Spain",
    "NL": "Netherlands",
    "BE": "Belgium",
    "AT": "Austria",
    "CH": "Switzerland",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "FI": "Finland",
    "PL": "Poland",
    "CZ": "Czech Republic",
    "GR": "Greece",
    "PT": "Portugal",
    "JP": "Japan",
    "CN": "China",
    "IN": "India",
    "BR": "Brazil",
    "CA": "Canada",
    "AU": "Australia",
}


@tool
def get_country_for_area(area_name: str) -> str:
    """
    Determines the correct Placemaking-compatible country name for a given area.
    Call this BEFORE search_places_in_polygon to get the correct country value.

    Args:
        area_name: Area/city name (e.g., 'Kadıköy', 'İstanbul', 'Paris')
    Returns:
        Country name as expected by Placemaking API (e.g., 'Turkey', 'France', 'UK')
    """
    try:
        # Step 1: Nominatim reverse lookup → get country_code + country name
        results = _nominatim_get("/search", {
            "q": area_name, "format": "json", "limit": 1, "addressdetails": 1
        })
        if not results:
            return f"Could not determine country for: {area_name}"

        address = results[0].get("address", {})
        country_code = address.get("country_code", "").upper()    # e.g., "TR"

        # Step 2: Fetch Placemaking countries list (cached after first call)
        try:
            countries = _fetch_placemaking_countries()
        except Exception as e:
            # Fallback to hardcoded mapping if Placemaking API fails
            return _COUNTRY_CODE_TO_NAME.get(country_code, f"Country lookup failed: {str(e)}")

        # Step 3: Match by country_code first
        for c in countries:
            c_code = (c.get("country_code") or c.get("code") or "").upper()
            c_name = c.get("name") or c.get("country") or ""
            if c_code and c_code == country_code:
                return c_name

        # Step 4: If no match found, use hardcoded mapping
        return _COUNTRY_CODE_TO_NAME.get(country_code, "Unknown")

    except Exception as e:
        # Last resort fallback
        return f"Error determining country: {str(e)}"


@tool
def search_places_in_polygon(polygon_geojson: str, country: str = "Unknown") -> str:
    """
    Searches for businesses and POIs (restaurants, cafes, shops, etc.) within a given area polygon.
    Use this tool AFTER getting a polygon with get_area_polygon to find all places in that area.

    Args:
        polygon_geojson: GeoJSON polygon string or the output from get_area_polygon tool.
        country: Country name for the Placemaking API (get this from get_country_for_area tool).

    Returns:
        JSON string containing list of places with name, latitude, longitude, address, and business category.

    Example workflow:
        1. First call get_area_polygon("Kadıköy") to get the polygon
        2. Then call get_country_for_area("Kadıköy") to get the correct country
        3. Then call this function with the polygon and country to find all places
        4. Optionally call filter_places_by_category to filter by type
    """
    if not PLACEMAKING_API_URL:
        return "Placemaking API URL is not configured."

    try:
        # Extract JSON from the response string if it contains POLYGON_DATA::: prefix
        json_str = polygon_geojson
        if "POLYGON_DATA:::" in polygon_geojson:
            json_str = polygon_geojson.split("POLYGON_DATA:::", 1)[1].strip()

        # Parse the JSON string
        poly_data = json.loads(json_str)

        # Convert to FeatureCollection if needed
        if poly_data.get("type") != "FeatureCollection":
            poly_data = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": poly_data
                    }
                ]
            }

        payload = {
            "country": country,
            "polygon": poly_data
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Timeout: 300 seconds (5 minutes) for Placemaking API polygon search
        with httpx.Client(timeout=300.0, headers=headers) as client:
            resp = client.post(PLACEMAKING_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Handle nested response structure: {"result": {"is_success": bool, "result": [...]}}
        result_wrapper = data.get("result", {})
        if isinstance(result_wrapper, dict):
            results = result_wrapper.get("result", [])
        else:
            results = result_wrapper if isinstance(result_wrapper, list) else []

        if not results:
            return "No places found within this polygon in the live data."

        # Limit results to reduce token count in agent (avoid exceeding LLM context window)
        results = results[:300]

        # Cache results so filter_places_by_categories can access without agent passing large JSON
        global _LAST_SEARCH_RESULTS
        _LAST_SEARCH_RESULTS = results

        return f"SEARCH_DONE:::{len(results)} places found. Now call filter_places_by_categories with categories parameter to filter these results."

    except json.JSONDecodeError as e:
        return f"Error parsing polygon JSON: {str(e)}. Received data: {polygon_geojson[:200]}..."
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json().get("message", e.response.text[:500])
        except Exception:
            error_detail = e.response.text[:500]
        return f"Placemaking API error {e.response.status_code}: {error_detail}"
    except httpx.TimeoutException as e:
        return f"Request timeout after 300 seconds: {str(e)}"
    except httpx.RequestError as e:
        return f"Request error (network/connection issue): {str(e)}"
    except Exception as e:
        return f"Error searching in polygon: {str(e)}"


@tool
def filter_places_by_categories(places_json: Any, categories: str) -> str:
    """
    Filters POI places intelligently using LLM (semantic understanding, not pattern matching).
    The LLM analyzes place names and categories to find intelligent matches.
    Handles large result sets with batching and provides robust error handling.

    Args:
        places_json: JSON string containing the list of places (from search_places_in_polygon)
        categories: Category query (e.g., 'burger restaurants', 'pizza places', 'Limited-Service Restaurants')

    Returns:
        JSON string with filtered places + human-readable formatted output

    Example:
        places_json: '[{"name": "Burger King", "business_category": "Limited-Service Restaurants", ...}]'
        categories: "burger restaurants"
    """
    try:
        from langchain_openai import ChatOpenAI
        from src.core.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

        # Use cached results from search_places_in_polygon (avoids passing large JSON through agent)
        global _LAST_SEARCH_RESULTS
        if _LAST_SEARCH_RESULTS:
            results = _LAST_SEARCH_RESULTS
        elif isinstance(places_json, list):
            results = places_json
        elif isinstance(places_json, str) and places_json.strip().startswith("["):
            results = json.loads(places_json)
        else:
            results = []

        if not isinstance(results, list):
            return "Invalid places data provided."

        if not results:
            return f"No places available to filter for: {categories}"

        if not OPENROUTER_API_KEY:
            return "LLM API key not configured. Cannot perform intelligent filtering."

        # Process in batches of 50 places for better LLM performance
        BATCH_SIZE = 50
        filtered_results = []

        for batch_start in range(0, len(results), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(results))
            batch = results[batch_start:batch_end]

            # Prepare data summary for LLM
            places_summary = []
            for idx_in_batch, place in enumerate(batch):
                places_summary.append({
                    "index": idx_in_batch,
                    "name": place.get("name", "Unknown"),
                    "business_category": place.get("business_category", "N/A"),
                    "main_category": place.get("main_category", "N/A"),
                    "street_address": place.get("street_address", ""),
                    "city": place.get("city", ""),
                })

            # Create enhanced prompt with Turkish/English examples and reasoning request
            llm_prompt = f"""You are a place filtering assistant. Analyze POI places and find semantic matches.
            
            User category query: "{categories}"
            
            Places to analyze:
            {json.dumps(places_summary, indent=2)}
            
            MATCHING RULES (use broad semantic understanding — err on the side of inclusion):
            - "restaurant/restoran/yemek/food": Match ANY place related to eating/dining: restaurants, lokanta, bistro, fast food, kebab, pizza, burger, döner, pide, lahmacun, köfte, balık evi, meze, ocakbaşı, mangal, izgara, çorba, börek, simit, pastane, fırın, hazır yemek, yemek fabrikası, catering, Full-Service Restaurants, Limited-Service Restaurants, Snack and Nonalcoholic Beverage Bars, Special Food Services, Food Service Contractors. Also match by NAME if it sounds like a restaurant (e.g., "Kebapçı", "Pide Salonu", "Lokanta", "Restoran").
            - "cafe/coffee/kahve": Match "Cafe", "Coffee", "Kahve", "Tea House", "Pastry", "Bakery", "Fırın"
            - "bar/pub/meyhane": Match "Bar", "Pub", "Meyhane", "Nightlife", "Birahane"
            - "market/supermarket": Match "Grocery", "Supermarket", "Market", "Food & Beverage Stores"
            - "pharmacy/eczane": Match "Pharmacy", "Eczane", "Drug Store"
            - "burger/hamburger": Match burger/fast food places specifically
            - "pizza/pizzeria": Match pizza places specifically
            - "kebab/döner": Match kebab/döner places specifically
            - For ANY food/dining query: be INCLUSIVE — if unsure whether a place serves food, include it
            
            IMPORTANT: If the query is about restaurants/food, include ALL food-related places. It is better to include too many than too few.
            
            Task:
            1. Understand user's intent broadly — when in doubt, include the place
            2. Match based on place NAME and CATEGORY fields
            3. Return ONLY valid JSON with two fields:
               - "filtered_indices": array of matching indices [0, 2, 5]
               - "reasoning": brief explanation (1 sentence)
            
            Example response:
            {{"filtered_indices": [0, 1, 3], "reasoning": "Matched places with restaurant categories"}}
            
            Return ONLY valid JSON, no extra text."""

            # Call LLM for intelligent filtering
            llm = ChatOpenAI(
                model="openrouter/auto",
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
                temperature=0,  # Deterministic classification
            )

            try:
                response = llm.invoke(llm_prompt)
                llm_response = response.content.strip()

                # Strip markdown code blocks if present (e.g. ```json ... ```)
                if llm_response.startswith("```"):
                    llm_response = re.sub(r"^```[a-zA-Z]*\n?", "", llm_response)
                    llm_response = re.sub(r"\n?```$", "", llm_response).strip()

                # Parse LLM response
                parsed = json.loads(llm_response)
                filtered_indices = parsed.get("filtered_indices", [])
                reasoning = parsed.get("reasoning", "")

            except json.JSONDecodeError:
                # Fallback: Use pattern matching from old tool
                filtered_indices = _fallback_pattern_filter(batch, categories)
                reasoning = "Fallback pattern matching used"
            except Exception as e:
                return f"LLM filtering error: {str(e)}"

            # Extract filtered places from this batch using indices
            for idx in filtered_indices:
                if 0 <= idx < len(batch):
                    filtered_results.append(batch[idx])

        if not filtered_results:
            # Fallback: if LLM found nothing, return all results (better than empty)
            filtered_results = results
            reasoning_fallback = f"No specific matches found for '{categories}', returning all {len(results)} places."

        # Format output: FILTERED_DATA::: prefix for reliable extraction, then human-readable
        json_output = json.dumps(filtered_results)

        output_lines = [f"Found {len(filtered_results)} places matching '{categories}':\n"]
        for i, place in enumerate(filtered_results[:50], 1):  # Show max 50
            name = place.get("name", "Unknown")
            lat = place.get("latitude")
            lon = place.get("longitude")
            address = place.get("street_address", "No address")
            business_cat = place.get("business_category", "N/A")
            main_cat = place.get("main_category", "N/A")
            city = place.get("city", "N/A")

            output_lines.append(
                f"{i}. {name}\n"
                f"   📍 {lat}, {lon}\n"
                f"   🏠 {address} - {city}\n"
                f"   🧭 {business_cat} | {main_cat}\n"
            )

        if len(filtered_results) > 50:
            output_lines.append(f"\n... and {len(filtered_results) - 50} more places.")

        return f"FILTERED_DATA:::{json_output}\n\n{''.join(output_lines)}"

    except json.JSONDecodeError as e:
        return f"Error parsing places JSON: {str(e)}"
    except Exception as e:
        return f"Error filtering places: {str(e)}"


def _fallback_pattern_filter(places: list[dict], category_query: str) -> list[int]:
    """Fallback pattern matching for when LLM filtering fails."""
    cat_lower = category_query.lower()
    tokens = cat_lower.split()

    if not tokens:
        return []

    matched_indices = []

    for idx, place in enumerate(places):
        r_cat = (place.get("business_category") or "").lower()
        r_main_cat = (place.get("main_category") or "").lower()
        r_name = (place.get("name") or "").lower()
        combined_cats = f"{r_cat} {r_main_cat}".strip()

        # Check if any token matches
        all_tokens_match = True
        for token in tokens:
            token_matched = False

            # Check category fields
            if token in combined_cats:
                token_matched = True
            # Check place name for meaningful terms (min 4 chars)
            elif len(token) >= 4 and token in r_name:
                token_matched = True

            if not token_matched:
                all_tokens_match = False
                break

        if all_tokens_match:
            matched_indices.append(idx)

    return matched_indices


@tool
def search_and_filter_places(polygon_geojson: str, country: str, categories: str) -> str:
    """
    Combined tool: Searches for POIs within a polygon AND filters them by category in one step.
    Use this instead of calling search_places_in_polygon + filter_places_by_categories separately.
    This avoids passing large JSON between tools through the agent.

    Args:
        polygon_geojson: The output from get_area_polygon tool (POLYGON_DATA::: string).
        country: Country name from get_country_for_area tool.
        categories: Category to filter by (e.g., 'restaurant', 'cafe', 'pharmacy').

    Returns:
        FILTERED_DATA:::JSON + human-readable list of matching places.
    """
    if not PLACEMAKING_API_URL:
        return "Placemaking API URL is not configured."

    try:
        # Step 1: Extract polygon
        json_str = polygon_geojson
        if "POLYGON_DATA:::" in polygon_geojson:
            json_str = polygon_geojson.split("POLYGON_DATA:::", 1)[1].strip()

        poly_data = json.loads(json_str)
        if poly_data.get("type") != "FeatureCollection":
            poly_data = {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": {}, "geometry": poly_data}]
            }

        # Step 2: Fetch POIs from Placemaking API
        payload = {"country": country, "polygon": poly_data}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        with httpx.Client(timeout=300.0, headers=headers) as client:
            resp = client.post(PLACEMAKING_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        result_wrapper = data.get("result", {})
        if isinstance(result_wrapper, dict):
            results = result_wrapper.get("result", [])
        else:
            results = result_wrapper if isinstance(result_wrapper, list) else []

        if not results:
            return "No places found within this polygon in the live data."

        results = results[:300]

        # Step 3: Filter using LLM (batched, no agent round-trip)
        try:
            from langchain_openai import ChatOpenAI
            from src.core.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

            if not OPENROUTER_API_KEY:
                raise ValueError("No API key")

            BATCH_SIZE = 50
            filtered_results = []

            llm = ChatOpenAI(
                model="openrouter/auto",
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
                temperature=0,
            )

            for batch_start in range(0, len(results), BATCH_SIZE):
                batch = results[batch_start:batch_start + BATCH_SIZE]

                places_summary = [
                    {
                        "index": i,
                        "name": p.get("name", "Unknown"),
                        "business_category": p.get("business_category", "N/A"),
                        "main_category": p.get("main_category", "N/A"),
                    }
                    for i, p in enumerate(batch)
                ]

                llm_prompt = f"""You are a place filtering assistant. Analyze POI places and find semantic matches.

User category query: "{categories}"

Places to analyze:
{json.dumps(places_summary, indent=2)}

MATCHING RULES (use broad semantic understanding — err on the side of inclusion):
- "restaurant/restoran/yemek/food": Match ANY place related to eating/dining: restaurants, lokanta, bistro, fast food, kebab, pizza, burger, döner, pide, lahmacun, köfte, balık evi, meze, ocakbaşı, mangal, izgara, çorba, börek, simit, pastane, fırın, hazır yemek, yemek fabrikası, catering, Full-Service Restaurants, Limited-Service Restaurants, Snack and Nonalcoholic Beverage Bars, Special Food Services, Food Service Contractors. Also match by NAME if it sounds like a restaurant (e.g., "Kebapçı", "Pide Salonu", "Lokanta", "Restoran").
- "cafe/coffee/kahve": Match "Cafe", "Coffee", "Kahve", "Tea House", "Pastry", "Bakery", "Fırın"
- "bar/pub/meyhane": Match "Bar", "Pub", "Meyhane", "Nightlife", "Birahane"
- "market/supermarket": Match "Grocery", "Supermarket", "Market", "Food & Beverage Stores"
- "pharmacy/eczane": Match "Pharmacy", "Eczane", "Drug Store"
- For ANY food/dining query: be INCLUSIVE — if unsure whether a place serves food, include it

IMPORTANT: If the query is about restaurants/food, include ALL food-related places.

Return ONLY valid JSON:
{{"filtered_indices": [0, 1, 3], "reasoning": "Matched places with restaurant categories"}}"""

                try:
                    response = llm.invoke(llm_prompt)
                    llm_response = response.content.strip()
                    if llm_response.startswith("```"):
                        llm_response = re.sub(r"^```[a-zA-Z]*\n?", "", llm_response)
                        llm_response = re.sub(r"\n?```$", "", llm_response).strip()
                    parsed = json.loads(llm_response)
                    filtered_indices = parsed.get("filtered_indices", [])
                except Exception:
                    filtered_indices = _fallback_pattern_filter(batch, categories)

                for idx in filtered_indices:
                    if 0 <= idx < len(batch):
                        filtered_results.append(batch[idx])

            if not filtered_results:
                filtered_results = results

        except Exception:
            # If LLM filtering fails entirely, return all results
            filtered_results = results

        # Step 4: Format output
        json_output = json.dumps(filtered_results)
        output_lines = [f"Found {len(filtered_results)} places matching '{categories}':\n"]
        for i, place in enumerate(filtered_results[:50], 1):
            name = place.get("name", "Unknown")
            lat = place.get("latitude")
            lon = place.get("longitude")
            address = place.get("street_address", "No address")
            business_cat = place.get("business_category", "N/A")
            city = place.get("city", "N/A")
            output_lines.append(
                f"{i}. {name}\n"
                f"   📍 {lat}, {lon}\n"
                f"   🏠 {address} - {city}\n"
                f"   🧭 {business_cat}\n"
            )
        if len(filtered_results) > 50:
            output_lines.append(f"\n... and {len(filtered_results) - 50} more places.")

        return f"FILTERED_DATA:::{json_output}\n\n{''.join(output_lines)}"

    except json.JSONDecodeError as e:
        return f"Error parsing polygon JSON: {str(e)}"
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json().get("message", e.response.text[:500])
        except Exception:
            error_detail = e.response.text[:500]
        return f"Placemaking API error {e.response.status_code}: {error_detail}"
    except httpx.TimeoutException as e:
        return f"Request timeout: {str(e)}"
    except Exception as e:
        return f"Error in search_and_filter_places: {str(e)}"


@tool
def get_area_polygon(area_name: str) -> str:
    """
    Fetches the GeoJSON polygon for a given area name (city, district, etc.).
    Example: 'Kadıköy', 'Beşiktaş', 'İstanbul'
    Args:
        area_name: Name of the area to get the polygon for.
    """
    try:
        # Step 1: Search for the area
        results = _nominatim_get(
            "/search",
            {
                "q": area_name,
                "format": "json",
                "polygon_geojson": 1,
                "limit": 10,
                "addressdetails": 1,
            },
        )
        if not results:
            return f"No polygon found for area: {area_name}"

        # Step 2: Try to find the best match (prioritize administrative boundaries)
        best_match = None
        
        # Priority 1: Exact match on type (city, district, administrative)
        for res in results:
            geojson = res.get("geojson")
            if not geojson or geojson.get("type") not in ["Polygon", "MultiPolygon"]:
                continue
            
            place_type = res.get("type", "")
            place_class = res.get("class", "")
            
            # These are usually what users mean by 'area'
            if place_class == "boundary" and place_type == "administrative":
                best_match = res
                break
        
        # Priority 2: Any Polygon/MultiPolygon
        if not best_match:
            for res in results:
                geojson = res.get("geojson")
                if geojson and geojson.get("type") in ["Polygon", "MultiPolygon"]:
                    best_match = res
                    break
        
        if not best_match:
            return f"No boundary polygon found for area: {area_name}. Found results but they don't have polygon data."

        name = best_match.get("display_name", area_name)
        geojson = best_match.get("geojson")
        
        return f"POLYGON_DATA:::{json.dumps(geojson)}"

    except Exception as e:
        return f"Error fetching polygon: {str(e)}"


@tool
def search_places_by_text(query: str) -> str:
    """
    Performs a text-based place search using OpenStreetMap Nominatim.
    Example: 'Kadıköy restaurants', 'Beşiktaş cafes', 'Taksim pizza'
    Args:
        query: Search text (area + place type). Use English place types for best results.
    """
    try:
        # Try original query first, then translated version
        translated_query = _translate_query(query)
        amenity = _extract_amenity(translated_query) or _extract_amenity(query)

        base_params: dict = {
            "format": "json",
            "addressdetails": 1,
            "namedetails": 1,
            "limit": 20,
        }

        results = None
        area = ""
        # If amenity detected, try structured search (amenity + city extracted from query)
        if amenity:
            # Extract area name by removing all amenity-related keywords from query
            area = translated_query
            for keyword in _AMENITY_TYPES:
                area = re.sub(rf"\b{re.escape(keyword)}\b", "", area, flags=re.IGNORECASE)
            area = area.strip().strip(",").strip()
            if area:
                structured = dict(base_params)
                structured["amenity"] = amenity
                structured["city"] = area
                results = _nominatim_get("/search", structured)

        # Fallback 1: free-text search with translated query
        if not results:
            results = _nominatim_get("/search", {**base_params, "q": translated_query})

        # Fallback 2: original query if translation differs
        if not results and translated_query != query:
            results = _nominatim_get("/search", {**base_params, "q": query})

        # Fallback 3: if we have an area, try broader free-text search with amenity keyword
        if not results and amenity and area:
            results = _nominatim_get("/search", {**base_params, "q": f"{amenity} {area}"})

        if not results:
            return f"No results found for '{query}'."

        output_lines = [f"Places found for '{query}':\n"]
        for i, place in enumerate(results, 1):
            namedetails = place.get("namedetails", {})
            short_name = (
                namedetails.get("name")
                or namedetails.get("name:tr")
                or namedetails.get("name:en")
                or place.get("display_name", "Unknown").split(",")[0].strip()
            )
            address = place.get("display_name", "")
            category = f"{place.get('class', 'place')} / {place.get('type', 'unknown')}"
            lat = place.get("lat")
            lon = place.get("lon")
            osm_id = place.get("osm_id")
            osm_type = place.get("osm_type")

            output_lines.append(
                f"{i}. {short_name}\n"
                f"   📍 Coordinates: {lat}, {lon}\n"
                f"   🏠 Address: {address}\n"
                f"   🧭 Category: {category}\n"
                f"   🆔 OSM: {osm_type}/{osm_id}\n"
            )

        return "\n".join(output_lines)

    except Exception as e:
        return f"An error occurred during search: {str(e)}"


@tool
def search_nearby_places(latitude: float, longitude: float, place_type: str, radius: int = 1500) -> str:
    """
    Searches for nearby places around specific coordinates using Overpass.
    Args:
        latitude: Latitude (e.g.: 41.0082)
        longitude: Longitude (e.g.: 28.9784)
        place_type: Place type (restaurant, cafe, bar, bakery, etc.)
        radius: Search radius in meters (default: 1500)
    """
    try:
        overpass_query_str = f"""
        [out:json][timeout:20];
        (
          node["amenity"="{place_type}"](around:{radius},{latitude},{longitude});
          way["amenity"="{place_type}"](around:{radius},{latitude},{longitude});
          relation["amenity"="{place_type}"](around:{radius},{latitude},{longitude});
        );
        out center 20;
        """
        try:
            data = _overpass_query(overpass_query_str)
            elements = data.get("elements", [])
        except Exception:
            elements = []

        # Fallback: Nominatim search when Overpass fails or returns nothing
        if not elements:
            nominatim_amenity = _AMENITY_TYPES.get(place_type, place_type)
            # Build a small bounding box (~radius*2) around the coordinates for viewbox
            deg_offset = radius / 111000  # rough degrees per metre
            viewbox = (
                f"{longitude - deg_offset},{latitude + deg_offset},"
                f"{longitude + deg_offset},{latitude - deg_offset}"
            )
            fallback_results = _nominatim_get(
                "/search",
                {
                    "amenity": nominatim_amenity,
                    "format": "json",
                    "addressdetails": 1,
                    "namedetails": 1,
                    "limit": 20,
                    "viewbox": viewbox,
                    "bounded": 1,
                },
            )
            if not fallback_results:
                # wider search without bounding box
                fallback_results = _nominatim_get(
                    "/search",
                    {
                        "q": f"{nominatim_amenity} near {latitude},{longitude}",
                        "format": "json",
                        "addressdetails": 1,
                        "namedetails": 1,
                        "limit": 20,
                    },
                )
            if not fallback_results:
                return f"No '{place_type}' found within {radius}m of ({latitude}, {longitude})."

            output_lines = [f"'{place_type}' places near ({latitude}, {longitude}) (Nominatim):\n"]
            for i, place in enumerate(fallback_results, 1):
                namedetails = place.get("namedetails", {})
                name = (
                    namedetails.get("name")
                    or namedetails.get("name:tr")
                    or namedetails.get("name:en")
                    or place.get("display_name", "Unknown").split(",")[0].strip()
                )
                lat_p = place.get("lat")
                lon_p = place.get("lon")
                address = place.get("display_name", "")
                output_lines.append(
                    f"{i}. {name}\n"
                    f"   📍 Coordinates: {lat_p}, {lon_p}\n"
                    f"   🏠 Address: {address}\n"
                )
            return "\n".join(output_lines)

        output_lines = [f"'{place_type}' places near ({latitude}, {longitude}) ({radius}m):\n"]
        for i, element in enumerate(elements[:20], 1):
            tags = element.get("tags", {})
            name = tags.get("name") or tags.get("name:tr") or tags.get("name:en") or "Unknown"
            address = _format_address(tags)
            center = element.get("center") or {"lat": element.get("lat"), "lon": element.get("lon")}
            lat_e = center.get("lat")
            lon_e = center.get("lon")
            osm_id = element.get("id")
            osm_type = element.get("type")

            output_lines.append(
                f"{i}. {name}\n"
                f"   📍 Address: {address}\n"
                f"   🧭 Coordinates: {lat_e}, {lon_e}\n"
                f"   🆔 OSM: {osm_type}/{osm_id}\n"
            )

        return "\n".join(output_lines)

    except Exception as e:
        return f"An error occurred during nearby search: {str(e)}"


@tool
def geocode_location(address: str) -> str:
    """
    Converts an address or area name to coordinates using Nominatim.
    Args:
        address: Address or area name (e.g.: 'Kadıköy, Istanbul', 'Beşiktaş')
    """
    try:
        results = _nominatim_get(
            "/search",
            {
                "q": address,
                "format": "json",
                "limit": 1,
            },
        )

        if not results:
            return f"No coordinates found for '{address}'."

        location = results[0]
        display_name = location.get("display_name", address)

        return (
            f"📍 {display_name}\n"
            f"   Latitude: {location.get('lat')}\n"
            f"   Longitude: {location.get('lon')}"
        )

    except Exception as e:
        return f"An error occurred during geocoding: {str(e)}"


@tool
def get_place_details(place_id: str) -> str:
    """
    Retrieves detailed information about a place from OSM.
    Args:
        place_id: OSM identifier in the form 'node/123', 'way/456', 'relation/789'
    """
    try:
        if "/" not in place_id:
            return "Place id must be in the form 'node/123', 'way/456', or 'relation/789'."

        osm_type, osm_id = place_id.split("/", 1)
        if osm_type not in {"node", "way", "relation"}:
            return "Place id must be in the form 'node/123', 'way/456', or 'relation/789'."

        query = f"""
        [out:json];
        {osm_type}({osm_id});
        out body;
        """
        data = _overpass_query(query)
        elements = data.get("elements", [])
        if not elements:
            return f"No place details found for '{place_id}'."

        element = elements[0]
        tags = element.get("tags", {})
        name = tags.get("name", "Unknown")
        address = _format_address(tags)
        phone = tags.get("phone", "No phone")
        website = tags.get("website", "No website")
        category = f"{tags.get('amenity', 'place')}"

        return (
            f"🏪 {name}\n"
            f"   📍 Address: {address}\n"
            f"   🧭 Category: {category}\n"
            f"   📞 Phone: {phone}\n"
            f"   🌐 Website: {website}"
        )

    except Exception as e:
        return f"An error occurred while fetching place details: {str(e)}"
