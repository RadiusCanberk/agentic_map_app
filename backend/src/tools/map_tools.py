"""
Map Agent Tools
LangChain tools for map searches using OpenStreetMap (Nominatim + Overpass)
"""
from __future__ import annotations

import re
from typing import Optional

import httpx
from langchain.tools import tool

from src.core.settings import NOMINATIM_EMAIL, NOMINATIM_USER_AGENT

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
# Multiple Overpass mirrors — tried in order until one succeeds
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = NOMINATIM_USER_AGENT or "AgenticMapApp/1.0 (contact: dev@example.com)"


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
