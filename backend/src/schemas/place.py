"""
Place Pydantic Schemas
API Request/Response için validation ve serialization
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class LocationBase(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Enlem (-90 ile 90 arası)")
    longitude: float = Field(..., ge=-180, le=180, description="Boylam (-180 ile 180 arası)")


class PlaceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = None
    phone_number: Optional[str] = None
    website: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    category: Optional[str] = Field(None, max_length=100)
    subcategory: Optional[List[str]] = None
    cuisine_type: Optional[str] = Field(None, max_length=100)


class PlaceCreate(PlaceBase):
    google_place_id: str = Field(..., min_length=1, max_length=255)
    rating: Optional[float] = Field(0.0, ge=0.0, le=5.0)
    user_ratings_total: Optional[int] = Field(0, ge=0)
    price_level: Optional[int] = Field(None, ge=0, le=4)
    is_open_now: Optional[bool] = False
    opening_hours: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    photos: Optional[List[Dict[str, str]]] = None


class PlaceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    phone_number: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    user_ratings_total: Optional[int] = Field(None, ge=0)
    price_level: Optional[int] = Field(None, ge=0, le=4)
    is_open_now: Optional[bool] = None
    opening_hours: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    photos: Optional[List[Dict[str, str]]] = None


class PlaceResponse(PlaceBase):
    id: int
    google_place_id: str
    rating: float
    reviews: int
    price_level: Optional[int] = None
    is_open_now: bool
    opening_hours: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    photos: Optional[List[Dict[str, str]]] = None
    view_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    distance: Optional[float] = Field(None, description="Kullanıcıya olan mesafe (metre)")

    class Config:
        from_attributes = True


class PlaceListResponse(BaseModel):
    places: List[PlaceResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class NearbySearchRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius: int = Field(5000, ge=100, le=50000, description="r (meter)")
    category: Optional[str] = Field(None, description="restaurant, cafe, bar, etc.")
    cuisine_type: Optional[str] = Field(None, description="italian, turkish, chinese, etc.")
    min_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    price_level: Optional[int] = Field(None, ge=0, le=4)
    is_open_now: Optional[bool] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class TextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    radius: Optional[int] = Field(5000, ge=100, le=50000)
    category: Optional[str] = None
    min_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class TopRatedRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius: int = Field(10000, ge=100, le=50000)
    category: Optional[str] = Field("restaurant", description="Kategori")
    cuisine_type: Optional[str] = None
    limit: int = Field(10, ge=1, le=50)

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        if v > 50:
            return 50
        return v
