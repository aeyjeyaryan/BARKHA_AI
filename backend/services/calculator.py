# app/services/calculator.py
import math
from typing import Dict, Any, List

class RTRWHCalculator:
    def __init__(self):
        self.roof_material_coefficients = {
            "concrete": 0.8,
            "tile": 0.75,
            "metal": 0.9,
            "asbestos": 0.85,
            "thatched": 0.6
        }
        
        self.soil_infiltration_rates = {
            "sandy": 5.0,  # mm/hr
            "loamy": 2.5,
            "clay": 0.5,
            "rocky": 0.1
        }
        
        self.first_flush_volume = 1.0  # mm equivalent
    
    def calculate_harvestable_volume(self, roof_area: float, annual_rainfall: float, 
                                   roof_material: str, roof_condition: str) -> float:
        """Calculate annual harvestable rainwater volume"""
        base_coefficient = self.roof_material_coefficients.get(roof_material, 0.75)
        condition_factor = {"good": 1.0, "fair": 0.85, "poor": 0.7}.get(roof_condition, 0.85)
        first_flush_loss = roof_area * self.first_flush_volume * 24
        
        harvestable = (roof_area * annual_rainfall * base_coefficient * condition_factor) / 1000 - first_flush_loss
        return max(0, harvestable)
    
    def calculate_storage_requirement(self, daily_demand: float, rainfall_pattern: str = "uniform") -> Dict[str, float]:
        """Calculate storage tank requirements"""
        storage_days = 30 if rainfall_pattern == "uniform" else (120 if rainfall_pattern == "seasonal" else 60)
        required_storage = daily_demand * storage_days / 1000
        recommended_storage = required_storage * 1.2
        
        return {
            "required_volume": required_storage,
            "recommended_volume": recommended_storage,
            "storage_days": storage_days
        }
    
    def calculate_recharge_structure(self, soil_type: str, available_volume: float) -> Dict[str, Any]:
        """Calculate artificial recharge structure requirements"""
        infiltration_rate = self.soil_infiltration_rates.get(soil_type, 1.0)
        pit_depth = 2.0
        required_area = available_volume / (pit_depth * 0.4)
        pit_diameter = math.sqrt(required_area * 4 / math.pi)
        
        trench_width = 1.0
        trench_depth = 1.5
        trench_length = available_volume / (trench_width * trench_depth * 0.3)
        
        return {
            "recharge_pit": {
                "diameter": round(pit_diameter, 2),
                "depth": pit_depth,
                "area": round(required_area, 2)
            },
            "recharge_trench": {
                "length": round(trench_length, 2),
                "width": trench_width,
                "depth": trench_depth
            },
            "infiltration_rate": infiltration_rate,
            "suitability_score": min(10, infiltration_rate * 2)
        }
    
    def recommend_best_option(self, harvestable_volume: float, daily_demand: float, 
                            soil_type: str, available_space: float) -> str:
        """Recommend the best RTRWH option"""
        annual_demand = daily_demand * 365 / 1000
        storage_viable = harvestable_volume >= annual_demand * 0.3
        infiltration_rate = self.soil_infiltration_rates.get(soil_type, 1.0)
        recharge_viable = infiltration_rate > 1.0 and available_space > 10
        
        if storage_viable and recharge_viable:
            return "hybrid" if harvestable_volume > annual_demand * 0.8 else "storage_priority_hybrid"
        elif storage_viable:
            return "storage_only"
        elif recharge_viable:
            return "recharge_only"
        else:
            return "not_feasible"
    
    def calculate_costs(self, recommendation: str, storage_volume: float, 
                       recharge_area: float) -> Dict[str, float]:
        """Calculate implementation costs"""
        costs = {
            "storage_tank_cost": 0, "recharge_structure_cost": 0,
            "piping_cost": 0, "filtration_cost": 0, "labor_cost": 0
        }
        
        storage_cost_per_m3 = 15000
        recharge_cost_per_m2 = 5000
        
        if "storage" in recommendation:
            costs["storage_tank_cost"] = storage_volume * storage_cost_per_m3
            costs["piping_cost"] = storage_volume * 2000
            costs["filtration_cost"] = 25000
        
        if "recharge" in recommendation:
            costs["recharge_structure_cost"] = recharge_area * recharge_cost_per_m2
            costs["piping_cost"] += recharge_area * 1000
        
        costs["labor_cost"] = (costs["storage_tank_cost"] + costs["recharge_structure_cost"]) * 0.3
        costs["total_cost"] = sum(costs.values())
        return costs
    
    def calculate_savings(self, harvestable_volume: float, water_tariff: float = 25) -> Dict[str, float]:
        """Calculate annual water savings"""
        annual_savings = harvestable_volume * water_tariff
        
        return {
            "annual_water_saved": harvestable_volume,
            "annual_cost_savings": annual_savings,
            "monthly_savings": annual_savings / 12,
            "water_tariff_used": water_tariff
        }
    
    def safety_checks(self, site_data: Dict[str, Any]) -> List[str]:
        """Perform safety and compliance checks"""
        warnings = []
        if site_data.get("roof_material") == "asbestos":
            warnings.append("CRITICAL: Asbestos roof detected. Water not suitable for drinking without extensive treatment.")
        if site_data.get("soil_type") == "clay" and site_data.get("annual_rainfall", 0) > 1500:
            warnings.append("WARNING: High clay content with heavy rainfall may cause waterlogging.")
        warnings.append("REQUIRED: Install first-flush diverter to remove initial contaminated water.")
        warnings.append("REQUIRED: Ensure proper overflow and drainage to prevent structural damage.")
        if site_data.get("storage_required", 0) > 10:
            warnings.append("WARNING: Large storage tank requires proper foundation and structural analysis.")
        return warnings

    def generate_boq(self, recommendation: str, storage_req: Dict, recharge_req: Dict, costs: Dict) -> Dict[str, Any]:
        """Generate Bill of Quantities"""
        boq = {"items": [], "total_cost": 0}
        
        if "storage" in recommendation:
            volume = storage_req["recommended_volume"]
            boq["items"].extend([
                {"item": "RCC Water Storage Tank", "quantity": f"{volume:.2f} m³", "rate": 15000, "amount": volume * 15000},
                {"item": "First Flush Diverter", "quantity": "1 No.", "rate": 5000, "amount": 5000},
                {"item": "Filtration System", "quantity": "1 Set", "rate": 25000, "amount": 25000},
                {"item": "PVC Piping & Fittings", "quantity": "1 Lot", "rate": costs["piping_cost"], "amount": costs["piping_cost"]}
            ])
        
        if "recharge" in recommendation:
            pit_area = recharge_req["recharge_pit"]["area"]
            boq["items"].extend([
                {"item": "Recharge Pit Excavation", "quantity": f"{pit_area:.2f} m²", "rate": 500, "amount": pit_area * 500},
                {"item": "Filter Media (Sand & Gravel)", "quantity": f"{pit_area * 0.5:.2f} m³", "rate": 2000, "amount": pit_area * 0.5 * 2000},
                {"item": "Perforated Pipe", "quantity": "50 m", "rate": 200, "amount": 10000}
            ])
        
        boq["total_cost"] = sum(item["amount"] for item in boq["items"])
        return boq