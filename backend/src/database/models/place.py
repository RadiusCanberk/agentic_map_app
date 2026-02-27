"""
Place (Mekan) Model - PostgreSQL + PostGIS
Restoranlar, kafeler ve diğer mekanlar için model
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from src.database.db import Base


class Place(Base):
    """
    Mekan modeli (Restoran, kafe, vb.)
    
    PostGIS Geography type kullanarak coğrafi koordinatları saklar.
    Geography type, gerçek dünya mesafelerini hesaplamak için kullanılır.
    """
    __tablename__ = "places"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Google Places API
    google_place_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    address = Column(Text, nullable=True)
    phone_number = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    location = Column(
        Geography(geometry_type='POINT', srid=4326),
        nullable=False,
        index=True
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    category = Column(String(100), index=True)
    subcategory = Column(String(100), index=True)
    cuisine_type = Column(String(100), index=True, nullable=True)
    rating = Column(Float, default=0.0, index=True)
    reviews = Column(Integer, default=0)
    price_level = Column(Integer, nullable=True)
    is_open_now = Column(Boolean, default=False, index=True)
    opening_hours = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    photos = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    view_count = Column(Integer, default=0)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Place(id={self.id}, name='{self.name}', rating={self.rating})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "google_place_id": self.google_place_id,
            "name": self.name,
            "address": self.address,
            "phone_number": self.phone_number,
            "website": self.website,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "category": self.category,
            "types": self.types,
            "cuisine_type": self.cuisine_type,
            "rating": self.rating,
            "user_ratings_total": self.user_ratings_total,
            "price_level": self.price_level,
            "is_open_now": self.is_open_now,
            "opening_hours": self.opening_hours,
            "description": self.description,
            "photos": self.photos,
            "view_count": self.view_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
