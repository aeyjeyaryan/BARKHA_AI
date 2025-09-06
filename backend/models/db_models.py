# app/models/db_models.py
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid as uuid_pkg

from core.database import Base

class Assessment(Base):
    __tablename__ = "assessments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_pkg.uuid4)
    site_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    roof_area = Column(Float, nullable=False)
    roof_material = Column(String, nullable=False)
    roof_condition = Column(String, default="good")
    soil_type = Column(String, nullable=False)
    annual_rainfall = Column(Float, nullable=False)
    water_demand = Column(Float, nullable=False)
    site_photos = Column(JSON)
    assessment_data = Column(JSON)
    recommendations = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_synced = Column(Boolean, default=True)

class LocalConfig(Base):
    __tablename__ = "local_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_pkg.uuid4)
    region = Column(String, nullable=False)
    rainfall_data = Column(JSON)
    soil_data = Column(JSON)
    cost_data = Column(JSON)
    tariff_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)