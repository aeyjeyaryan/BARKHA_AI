import math
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RTRWHCalculator:
    def __init__(self):
        # Runoff coefficients sourced from TWDB, NRCS, and Indian standards (2025)
        self.roof_material_coefficients = {
            "concrete": 0.75,
            "tile": 0.80,
            "metal": 0.92,
            "asbestos": 0.82,
            "thatched": 0.60
        }

        # Infiltration rates (mm/hr) based on NRCS and Indian soil data
        self.soil_infiltration_rates = {
            "sandy": 30.0,
            "loamy": 15.0,
            "clay": 2.5,
            "rocky": 0.5
        }

        # First flush volume (mm) per rainfall event, based on Indian RWH guidelines
        self.first_flush_volume = 1.5
        self.annual_rainfall_events = 24  # Average rainfall events per year

        # Roof condition factors (estimated based on maintenance impact)
        self.roof_condition_factors = {
            "good": 1.0,
            "fair": 0.85,
            "poor": 0.70
        }

        # Porosity for recharge structures
        self.pit_porosity = 0.40
        self.trench_porosity = 0.30

        # Structural dimensions (meters), based on Indian RWH design standards
        self.pit_depth = 2.5
        self.trench_width = 0.75
        self.trench_depth = 1.25

        # Cost parameters (INR, 2025 market rates adjusted for residential systems)
        self.storage_cost_per_m3 = 10000  # RCC tank + installation (reduced from 12000)
        self.recharge_cost_per_m2 = 2500  # Excavation + filter media (reduced from 4500)
        self.piping_cost_per_unit = 1000  # Per m³ for storage, halved for recharge
        self.filtration_cost = 15000  # First flush + sand filter (reduced from 20000)
        self.labor_factor = 0.20  # 20% of major components
        self.contingency_factor = 0.10  # 10% of materials + labor
        self.tax_rate = 0.18  # 18% GST
        self.max_recharge_area = 10.0  # Max recharge pit area for residential systems (m²)

    def _validate_input(self, value, min_val=0, max_val=None, name="input"):
        if not isinstance(value, (int, float)) or value < min_val or (max_val and value > max_val):
            raise ValueError(f"Invalid {name}: {value}. Must be numeric between {min_val} and {max_val or 'inf'}.")

    def calculate_harvestable_volume(self, roof_area: float, annual_rainfall: float,
                                    roof_material: str, roof_condition: str) -> float:
        """Calculate annual harvestable rainwater volume in m³"""
        try:
            self._validate_input(roof_area, min_val=0, name="roof_area")
            self._validate_input(annual_rainfall, min_val=0, name="annual_rainfall")
        except ValueError as e:
            logger.error(f"Validation error in calculate_harvestable_volume: {str(e)}")
            return 0.0

        roof_material = roof_material.strip().lower() if roof_material else "concrete"
        base_coefficient = self.roof_material_coefficients.get(roof_material, 0.75)
        if base_coefficient == 0.75 and roof_material != "concrete":
            logger.warning(f"Unknown roof material '{roof_material}'. Using default coefficient 0.75.")

        condition_factor = self.roof_condition_factors.get(
            roof_condition.strip().lower() if roof_condition else "fair", 0.85
        )
        if condition_factor == 0.85 and roof_condition and roof_condition.strip().lower() not in self.roof_condition_factors:
            logger.warning(f"Unknown roof condition '{roof_condition}'. Using default factor 0.85.")

        potential_volume = roof_area * annual_rainfall * base_coefficient * condition_factor / 1000
        first_flush_loss_per_event = roof_area * self.first_flush_volume / 1000
        annual_first_flush_loss = first_flush_loss_per_event * self.annual_rainfall_events

        harvestable = potential_volume - annual_first_flush_loss
        logger.info(f"Harvestable volume: {harvestable:.2f} m³ for roof_area={roof_area}, rainfall={annual_rainfall}, "
                    f"material={roof_material}, condition={roof_condition}")
        return max(0, harvestable)

    def calculate_storage_requirement(self, daily_demand: float, rainfall_pattern: str = "uniform") -> Dict[str, float]:
        """Calculate storage tank requirements in m³"""
        try:
            self._validate_input(daily_demand, min_val=0, name="daily_demand")
        except ValueError as e:
            logger.error(f"Validation error in calculate_storage_requirement: {str(e)}")
            return {"required_volume": 0.0, "recommended_volume": 0.0, "storage_days": 0}

        patterns = {"uniform": 45, "seasonal": 150}
        storage_days = patterns.get(rainfall_pattern.strip().lower(), 75)
        required_storage = daily_demand * storage_days / 1000
        recommended_storage = required_storage * 1.25

        result = {
            "required_volume": round(required_storage, 2),
            "recommended_volume": round(recommended_storage, 2),
            "storage_days": storage_days
        }
        logger.info(f"Storage requirements: {result}")
        return result

    def calculate_recharge_structure(self, soil_type: str, available_volume: float, available_space: float) -> Dict[str, Any]:
        """Calculate artificial recharge structure requirements with space constraint"""
        try:
            self._validate_input(available_volume, min_val=0, name="available_volume")
            self._validate_input(available_space, min_val=0, max_val=1000, name="available_space")
        except ValueError as e:
            logger.error(f"Validation error in calculate_recharge_structure: {str(e)}")
            return {
                "recharge_pit": {"diameter": 0.0, "depth": self.pit_depth, "area": 0.0},
                "recharge_trench": {"length": 0.0, "width": self.trench_width, "depth": self.trench_depth},
                "infiltration_rate": 0.0,
                "suitability_score": 0.0
            }

        soil_type = soil_type.strip().lower() if soil_type else "clay"
        infiltration_rate = self.soil_infiltration_rates.get(soil_type, 1.0)
        if infiltration_rate == 1.0 and soil_type not in self.soil_infiltration_rates:
            logger.warning(f"Unknown soil type '{soil_type}'. Using default infiltration rate 1.0.")

        # Cap recharge area based on available space and max residential limit
        required_area = available_volume / (self.pit_depth * self.pit_porosity) if available_volume > 0 else 0
        capped_area = min(required_area, available_space, self.max_recharge_area)
        if capped_area < required_area:
            logger.info(f"Recharge area capped from {required_area:.2f} m² to {capped_area:.2f} m² due to space constraints.")

        pit_diameter = math.sqrt(capped_area * 4 / math.pi) if capped_area > 0 else 0
        trench_length = available_volume / (self.trench_width * self.trench_depth * self.trench_porosity) if available_volume > 0 else 0

        result = {
            "recharge_pit": {
                "diameter": round(pit_diameter, 2),
                "depth": self.pit_depth,
                "area": round(capped_area, 2)
            },
            "recharge_trench": {
                "length": round(trench_length, 2),
                "width": self.trench_width,
                "depth": self.trench_depth
            },
            "infiltration_rate": infiltration_rate,
            "suitability_score": min(10, infiltration_rate / 3)
        }
        logger.info(f"Recharge structure: {result}")
        return result

    def recommend_best_option(self, harvestable_volume: float, daily_demand: float,
                             soil_type: str, available_space: float) -> str:
        """Recommend the best RTRWH option"""
        try:
            self._validate_input(harvestable_volume, min_val=0, name="harvestable_volume")
            self._validate_input(daily_demand, min_val=0, name="daily_demand")
            self._validate_input(available_space, min_val=0, max_val=1000, name="available_space")
        except ValueError as e:
            logger.error(f"Validation error in recommend_best_option: {str(e)}")
            return "not_feasible"

        annual_demand = daily_demand * 365 / 1000
        storage_viable = harvestable_volume >= annual_demand * 0.4
        soil_type = soil_type.strip().lower() if soil_type else "clay"
        infiltration_rate = self.soil_infiltration_rates.get(soil_type, 1.0)
        recharge_viable = infiltration_rate > 2.0 and available_space >= 5  # Reduced threshold for residential

        recommendation = (
            "hybrid" if storage_viable and recharge_viable and harvestable_volume > annual_demand * 0.7
            else "storage_priority_hybrid" if storage_viable and recharge_viable
            else "storage_only" if storage_viable
            else "recharge_only" if recharge_viable
            else "not_feasible"
        )
        logger.info(f"Recommendation: {recommendation} (harvestable_volume={harvestable_volume}, "
                    f"daily_demand={daily_demand}, soil_type={soil_type}, available_space={available_space})")
        return recommendation

    def calculate_costs(self, recommendation: str, storage_volume: float,
                        recharge_area: float) -> Dict[str, float]:
        """Calculate implementation costs in INR with detailed breakdown"""
        try:
            self._validate_input(storage_volume, min_val=0, name="storage_volume")
            self._validate_input(recharge_area, min_val=0, name="recharge_area")
        except ValueError as e:
            logger.error(f"Validation error in calculate_costs: {str(e)}")
            return {
                "storage_tank_cost": 0.0,
                "recharge_structure_cost": 0.0,
                "piping_cost": 0.0,
                "filtration_cost": 0.0,
                "labor_cost": 0.0,
                "material_contingency": 0.0,
                "tax": 0.0,
                "total_cost": 0.0
            }

        costs = {
            "storage_tank_cost": 0.0,
            "recharge_structure_cost": 0.0,
            "piping_cost": 0.0,
            "filtration_cost": 0.0,
            "labor_cost": 0.0,
            "material_contingency": 0.0,
            "tax": 0.0,
            "total_cost": 0.0
        }

        recommendation = recommendation.strip().lower() if recommendation else "not_feasible"
        valid_recommendations = ["storage_only", "recharge_only", "hybrid", "storage_priority_hybrid", "not_feasible"]
        if recommendation not in valid_recommendations:
            logger.warning(f"Invalid recommendation '{recommendation}'. Defaulting to 'not_feasible'.")
            recommendation = "not_feasible"

        logger.info(f"Calculating costs for recommendation: {recommendation}, "
                    f"storage_volume: {storage_volume} m³, recharge_area: {recharge_area} m²")

        if recommendation != "not_feasible":
            storage_keywords = ["storage_only", "hybrid", "storage_priority_hybrid"]
            if any(recommendation == keyword for keyword in storage_keywords):
                if storage_volume <= 0:
                    logger.warning("Storage volume is zero or negative. Skipping storage-related costs.")
                else:
                    costs["storage_tank_cost"] = storage_volume * self.storage_cost_per_m3
                    costs["piping_cost"] += storage_volume * self.piping_cost_per_unit
                    costs["filtration_cost"] = self.filtration_cost
                    logger.info(f"Storage costs: tank={costs['storage_tank_cost']}, "
                                f"piping={costs['piping_cost']}, filtration={costs['filtration_cost']}")

            recharge_keywords = ["recharge_only", "hybrid", "storage_priority_hybrid"]
            if any(recommendation == keyword for keyword in recharge_keywords):
                if recharge_area <= 0:
                    logger.warning("Recharge area is zero or negative. Skipping recharge-related costs.")
                else:
                    costs["recharge_structure_cost"] = recharge_area * self.recharge_cost_per_m2
                    costs["piping_cost"] += recharge_area * (self.piping_cost_per_unit * 0.5)
                    logger.info(f"Recharge costs: structure={costs['recharge_structure_cost']}, "
                                f"additional piping={recharge_area * (self.piping_cost_per_unit * 0.5)}")

            major_components = costs["storage_tank_cost"] + costs["recharge_structure_cost"]
            costs["labor_cost"] = major_components * self.labor_factor
            materials_and_labor = (
                major_components +
                costs["piping_cost"] +
                costs["filtration_cost"] +
                costs["labor_cost"]
            )
            costs["material_contingency"] = materials_and_labor * self.contingency_factor
            subtotal = materials_and_labor + costs["material_contingency"]
            costs["tax"] = subtotal * self.tax_rate
            costs["total_cost"] = subtotal + costs["tax"]

        logger.info(f"Cost breakdown: {costs}")
        return {k: round(v, 2) for k, v in costs.items()}

    def calculate_savings(self, harvestable_volume: float, water_tariff: float = 25) -> Dict[str, float]:
        """Calculate annual water savings"""
        try:
            self._validate_input(harvestable_volume, min_val=0, name="harvestable_volume")
            self._validate_input(water_tariff, min_val=0, name="water_tariff")
        except ValueError as e:
            logger.error(f"Validation error in calculate_savings: {str(e)}")
            return {
                "annual_water_saved": 0.0,
                "annual_cost_savings": 0.0,
                "monthly_savings": 0.0,
                "water_tariff_used": water_tariff
            }

        annual_savings = harvestable_volume * water_tariff
        result = {
            "annual_water_saved": round(harvestable_volume, 2),
            "annual_cost_savings": round(annual_savings, 2),
            "monthly_savings": round(annual_savings / 12, 2),
            "water_tariff_used": water_tariff
        }
        logger.info(f"Savings: {result}")
        return result

    def safety_checks(self, site_data: Dict[str, Any]) -> List[str]:
        """Perform safety and compliance checks"""
        if not isinstance(site_data, dict):
            logger.error("site_data must be a dictionary.")
            return ["ERROR: Invalid site_data format. Must be a dictionary."]

        warnings = []
        roof_material = site_data.get("roof_material", "").strip().lower()
        if roof_material == "asbestos":
            warnings.append("CRITICAL: Asbestos roof detected. Water not suitable for drinking without extensive treatment.")

        soil_type = site_data.get("soil_type", "").strip().lower()
        annual_rainfall = site_data.get("annual_rainfall", 0)
        if soil_type == "clay" and annual_rainfall > 1200:
            warnings.append("WARNING: High clay content with heavy rainfall may cause waterlogging.")

        storage_required = site_data.get("storage_required", 0)
        if storage_required > 15:
            warnings.append("WARNING: Large storage tank requires structural analysis and UV protection.")

        warnings.extend([
            "REQUIRED: Install first-flush diverter to remove initial contaminated water.",
            "REQUIRED: Ensure proper overflow and drainage to prevent structural damage.",
            "RECOMMENDED: Regularly test harvested water for pH, bacteria, and contaminants.",
            "RECOMMENDED: Use opaque tanks to prevent algal growth.",
            "RECOMMENDED: Clean gutters and screens biannually."
        ])

        logger.info(f"Safety checks: {warnings}")
        return warnings

    def generate_boq(self, recommendation: str, storage_req: Dict, recharge_req: Dict, costs: Dict) -> Dict[str, Any]:
        """Generate Bill of Quantities"""
        if not all(isinstance(d, dict) for d in [storage_req, recharge_req, costs]):
            logger.error("Invalid input: storage_req, recharge_req, and costs must be dictionaries.")
            return {"items": [], "total_cost": 0.0}

        boq = {"items": [], "total_cost": 0.0}
        recommendation = recommendation.strip().lower() if recommendation else "not_feasible"

        storage_keywords = ["storage_only", "hybrid", "storage_priority_hybrid"]
        if any(recommendation == keyword for keyword in storage_keywords):
            volume = storage_req.get("recommended_volume", 0)
            boq["items"].extend([
                {"item": "RCC Water Storage Tank", "quantity": f"{volume:.2f} m³", "rate": self.storage_cost_per_m3, "amount": round(volume * self.storage_cost_per_m3, 2)},
                {"item": "First Flush Diverter", "quantity": "1 No.", "rate": 5000, "amount": 5000},
                {"item": "Filtration System (Sand)", "quantity": "1 Set", "rate": self.filtration_cost, "amount": self.filtration_cost},
                {"item": "PVC Piping & Fittings", "quantity": "1 Lot", "rate": costs.get("piping_cost", 0), "amount": round(costs.get("piping_cost", 0), 2)}
            ])

        recharge_keywords = ["recharge_only", "hybrid", "storage_priority_hybrid"]
        if any(recommendation == keyword for keyword in recharge_keywords):
            pit_area = recharge_req.get("recharge_pit", {}).get("area", 0)
            boq["items"].extend([
                {"item": "Recharge Pit Excavation", "quantity": f"{pit_area:.2f} m²", "rate": 500, "amount": round(pit_area * 500, 2)},
                {"item": "Filter Media (Sand & Gravel)", "quantity": f"{pit_area * 0.6:.2f} m³", "rate": 1500, "amount": round(pit_area * 0.6 * 1500, 2)},
                {"item": "Perforated Pipe", "quantity": "20 m", "rate": 200, "amount": 4000}
            ])

        boq["total_cost"] = sum(item["amount"] for item in boq["items"])
        boq["total_cost"] = round(boq["total_cost"], 2)
        logger.info(f"BOQ: {boq}")
        return boq