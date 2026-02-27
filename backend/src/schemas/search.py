"""
Search Schemas
Arama işlemleri için Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AutocompleteRequest(BaseModel):
    """Autocomplete arama request"""
    input: str = Field(..., min_length=1, max_length=200, description="Arama metni")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    radius: Optional[int] = Field(5000, ge=100, le=50000)
    types: Optional[List[str]] = Field(None, description="establishment, restaurant, cafe, etc.")


class AutocompleteSuggestion(BaseModel):
    """Autocomplete öneri"""
    place_id: str
    description: str
    main_text: str
    secondary_text: str
    types: List[str]


class AutocompleteResponse(BaseModel):
    """Autocomplete response"""
    suggestions: List[AutocompleteSuggestion]
    status: str


class GeocodeRequest(BaseModel):
    """Adres -> Koordinat çevirme request"""
    address: str = Field(..., min_length=1, max_length=500)


class GeocodeResponse(BaseModel):
    """Geocode response"""
    latitude: float
    longitude: float
    formatted_address: str
    place_id: str


class ReverseGeocodeRequest(BaseModel):
    """Koordinat -> Adres çevirme request"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class ReverseGeocodeResponse(BaseModel):
    """Reverse geocode response"""
    formatted_address: str
    address_components: List[dict]
    place_id: str


class SearchHistoryCreate(BaseModel):
    """Arama geçmişi kaydetme"""
    search_query: str
    search_type: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    radius: Optional[int] = None
    results_count: int = 0


class SearchHistoryResponse(BaseModel):
    """Arama geçmişi response"""
    id: int
    search_query: str
    search_type: Optional[str] = None
    results_count: int
    created_at: datetime

    class Config:
        from_attributes = True
