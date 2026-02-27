"""
User Model - Kullanıcı favori mekanları ve arama geçmişi için
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.db import Base


# Many-to-Many relationship için association table
user_favorites = Table(
    'user_favorites',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('place_id', Integer, ForeignKey('places.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)


class User(Base):
    """
    Kullanıcı modeli
    Favori mekanları ve arama geçmişini saklar
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Kullanıcı Bilgileri
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    
    # Authentication (opsiyonel - şimdilik basit tutuyoruz)
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
    Kullanıcı arama geçmişi
    Hangi kullanıcı ne aradı, ne zaman aradı
    """
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign Key
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    
    # Arama Detayları
    search_query = Column(String(500), nullable=False)
    search_type = Column(String(50), nullable=True)  # "restaurant", "cafe", "nearby", etc.
    latitude = Column(String(50), nullable=True)
    longitude = Column(String(50), nullable=True)
    radius = Column(Integer, nullable=True)  # metre cinsinden
    
    # Results
    results_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User", back_populates="search_history")
    
    def __repr__(self):
        return f"<SearchHistory(id={self.id}, query='{self.search_query}')>"
