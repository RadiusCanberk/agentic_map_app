"""
User Model - For user favorite places and search history
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.db import Base


# Association table for Many-to-Many relationship
user_favorites = Table(
    'user_favorites',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('place_id', Integer, ForeignKey('places.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)


class User(Base):
    """
    User model
    Stores favorite places and search history
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # User Information
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    
    # Authentication (optional - keeping it simple for now)
    hashed_password = Column(String(255), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    # favorites = relationship("Place", secondary=user_favorites, backref="favorited_by")
    search_history = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class SearchHistory(Base):
    """
    User search history
    Tracks what users searched for and when they searched
    """
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    
    # Search Details
    search_query = Column(String(500), nullable=False)
    search_type = Column(String(50), nullable=True)  # "restaurant", "cafe", "nearby", etc.
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    radius = Column(Integer, nullable=True)  # in meters
    
    # Results
    results_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User", back_populates="search_history")
    
    def __repr__(self):
        return f"<SearchHistory(id={self.id}, query='{self.search_query}')>"
