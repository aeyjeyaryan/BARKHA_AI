from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any

class SiteDetailsInput(BaseModel):
    site_name: str
    latitude: float
    longitude: float
    roof_area: float
    roof_material: str
    roof_condition: str = "good"
    soil_type: str
    annual_rainfall: float
    water_demand: float
    
    @field_validator('roof_area')
    def validate_roof_area(cls, v):
        if v <= 0:
            raise ValueError('Roof area must be positive')
        return v
    
    @field_validator('annual_rainfall')
    def validate_rainfall(cls, v):
        if v < 0:
            raise ValueError('Rainfall cannot be negative')
        return v

class AssessmentResult(BaseModel):
    assessment_id: str
    harvestable_volume: float
    recommended_option: str
    storage_recommendation: Dict[str, Any]
    recharge_recommendation: Dict[str, Any]
    cost_analysis: Dict[str, Any]
    savings_analysis: Dict[str, Any]
    safety_checks: List[str]
    bill_of_quantities: Dict[str, Any]

class ConfigData(BaseModel):
    region: str
    rainfall_data: Dict[str, float]
    soil_data: Dict[str, Any]
    cost_data: Dict[str, float]
    tariff_data: Dict[str, float]