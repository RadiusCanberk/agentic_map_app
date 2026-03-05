"""
Place Model - PostgreSQL + PostGIS
Model for restaurants, cafes and other places
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from src.database.db import Base


class Place(Base):
    """
    Place model (Restaurant, cafe, etc.)

    Stores geographic coordinates using PostGIS Geography type.
    Geography type is used to calculate real-world distances.
    """
    __tablename__ = "places"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Google Places API
    google_place_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    address = Column(Text, nullable=True)
    street = Column(Text, nullable=True)
    postal_code = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    website = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    business_category = Column(String(100), nullable=True)
    type = Column(String(100), nullable=True)
    subtypes = Column(String(100), nullable=True)
    location = Column(
        Geography(geometry_type='POINT', srid=4326),
        nullable=False,
        index=True
    )
    review_tags = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    review = Column(Integer, nullable=True)
    price_range = Column(Integer, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Place(id={self.id}, name='{self.name}', rating={self.rating})>"
    def to_dict(self):
        """Convert Place model to dictionary"""
        return {
            "id": self.id,
            "google_place_id": self.google_place_id,
            "name": self.name,
            "address": self.address,
            "street": self.street,
            "postal_code": self.postal_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "website": self.website,
            "phone": self.phone,
            "category": self.category,
            "business_category": self.business_category,
            "type": self.type,
            "subtypes": self.subtypes,
            "review_tags": self.review_tags,
            "description": self.description,
            "rating": self.rating,
            "review": self.review,
            "price_range": self.price_range,
            "city": self.city,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }