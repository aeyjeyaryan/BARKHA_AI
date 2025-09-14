#!/usr/bin/env python3
import os
import sys
import json
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import tempfile
import logging

# Set environment for headless QGIS BEFORE importing QGIS
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['DISPLAY'] = ':99'

# Import and initialize QGIS
from qgis.core import QgsApplication

# Initialize QGIS Application ONCE at module level
QgsApplication.setPrefixPath('/usr', True)
qgs = QgsApplication([], False)
qgs.initQgis()

# Now import other QGIS modules
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsGeometry, QgsPointXY, QgsFeature, QgsField, QgsFields,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProcessingFeedback, QgsVectorFileWriter, QgsRasterFileWriter,
    QgsProcessingContext, QgsProcessingAlgorithm, QgsWkbTypes,
    QgsDistanceArea, QgsUnitTypes, QgsFeatureRequest, QgsSpatialIndex,
    QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
)
from qgis.analysis import QgsNativeAlgorithms
import processing
from processing.core.Processing import Processing

# Initialize processing
Processing.initialize()

# GDAL imports
from osgeo import gdal, ogr, osr, gdalconst
import rasterio
import rasterio.features
import rasterio.warp
from rasterio.windows import Window
from rasterio.transform import from_bounds

# Shapely imports
from shapely.geometry import (
    Point, Polygon, LineString, MultiPolygon, GeometryCollection,
    box as shapely_box
)
from shapely.ops import transform, unary_union, nearest_points, split
from shapely.affinity import scale, rotate, translate
import pyproj
from functools import partial

# Scientific libraries
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial.distance import cdist
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

# Plotting
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import ListedColormap
import seaborn as sns

# Set matplotlib backend for headless operation
plt.switch_backend('Agg')

def advanced_gis_analysis_for_rtrwh(
    site_coordinates: Tuple[float, float],
    roof_polygon: Optional[List[Tuple[float, float]]] = None,
    analysis_radius: float = 1000.0,
    dem_path: Optional[str] = None,
    soil_data_path: Optional[str] = None,
    land_use_path: Optional[str] = None,
    rainfall_raster_path: Optional[str] = None,
    output_dir: str = "/app/output"
) -> Dict[str, Any]:
    """
    Advanced GIS analysis function for RTRWH assessment using QGIS APIs, GDAL, and Shapely.
    
    Args:
        site_coordinates: (latitude, longitude) of the assessment site
        roof_polygon: List of (lat, lon) coordinates defining roof boundary
        analysis_radius: Radius in meters for spatial analysis
        dem_path: Path to Digital Elevation Model raster
        soil_data_path: Path to soil type vector data
        land_use_path: Path to land use vector data
        rainfall_raster_path: Path to rainfall intensity raster
        output_dir: Directory for output files
        
    Returns:
        Dictionary containing comprehensive GIS analysis results
    """
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Results dictionary
        results = {
            "site_info": {},
            "topographic_analysis": {},
            "soil_analysis": {},
            "hydrological_analysis": {},
            "spatial_suitability": {},
            "catchment_analysis": {},
            "optimization_results": {},
            "visualizations": {},
            "recommendations": {}
        }
        
        lat, lon = site_coordinates
        
        # =================================================================
        # 1. COORDINATE SYSTEM SETUP AND SITE PREPARATION
        # =================================================================
        
        # Define coordinate systems
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        utm_zone = int((lon + 180) / 6) + 1
        utm_epsg = f"EPSG:{32600 + utm_zone if lat >= 0 else 32700 + utm_zone}"
        utm_crs = QgsCoordinateReferenceSystem(utm_epsg)
        
        # Create coordinate transformer
        transform_to_utm = QgsCoordinateTransform(wgs84, utm_crs, QgsProject.instance())
        transform_to_wgs84 = QgsCoordinateTransform(utm_crs, wgs84, QgsProject.instance())
        
        # Site point in both coordinate systems
        site_point_wgs84 = QgsPointXY(lon, lat)
        site_point_utm = transform_to_utm.transform(site_point_wgs84)
        
        # Create Shapely point for advanced operations
        shapely_site_point = Point(lon, lat)
        
        results["site_info"] = {
            "coordinates_wgs84": (lat, lon),
            "coordinates_utm": (site_point_utm.x(), site_point_utm.y()),
            "utm_zone": utm_zone,
            "utm_epsg": utm_epsg
        }
        
        # =================================================================
        # 2. ROOF AND BUILDING ANALYSIS
        # =================================================================
        
        if roof_polygon:
            # Create roof geometry from coordinates
            roof_coords_utm = []
            for roof_lat, roof_lon in roof_polygon:
                roof_point_wgs84 = QgsPointXY(roof_lon, roof_lat)
                roof_point_utm = transform_to_utm.transform(roof_point_wgs84)
                roof_coords_utm.append([roof_point_utm.x(), roof_point_utm.y()])
            
            # Create Shapely polygon for roof
            roof_shapely = Polygon(roof_coords_utm)
            roof_area = roof_shapely.area  # in square meters
            
            # Calculate roof properties
            roof_bounds = roof_shapely.bounds
            roof_centroid = roof_shapely.centroid
            roof_perimeter = roof_shapely.length
            
            # Roof shape analysis
            roof_rectangularity = (4 * np.pi * roof_area) / (roof_perimeter ** 2)
            
            # Optimal orientation analysis (for drainage)
            minx, miny, maxx, maxy = roof_bounds
            roof_length = max(maxx - minx, maxy - miny)
            roof_width = min(maxx - minx, maxy - miny)
            aspect_ratio = roof_length / roof_width if roof_width > 0 else 1
            
            results["site_info"]["roof_analysis"] = {
                "area_sqm": roof_area,
                "perimeter_m": roof_perimeter,
                "rectangularity_index": roof_rectangularity,
                "aspect_ratio": aspect_ratio,
                "dimensions": {"length": roof_length, "width": roof_width}
            }
        
        # =================================================================
        # 3. TOPOGRAPHIC ANALYSIS (Simplified for demo)
        # =================================================================
        
        # Since we may not have actual DEM data, provide synthetic analysis
        if dem_path and os.path.exists(dem_path):
            try:
                # Load DEM using GDAL
                dem_dataset = gdal.Open(dem_path)
                if dem_dataset:
                    dem_band = dem_dataset.GetRasterBand(1)
                    dem_transform = dem_dataset.GetGeoTransform()
                    
                    # Extract elevation at site point
                    def get_elevation_at_point(x, y, dataset, transform):
                        """Extract elevation value at given coordinates"""
                        px = int((x - transform[0]) / transform[1])
                        py = int((y - transform[3]) / transform[5])
                        
                        if 0 <= px < dataset.RasterXSize and 0 <= py < dataset.RasterYSize:
                            elevation_array = dataset.GetRasterBand(1).ReadAsArray(px, py, 1, 1)
                            return float(elevation_array[0, 0]) if elevation_array is not None else None
                        return None
                    
                    site_elevation = get_elevation_at_point(
                        site_point_utm.x(), site_point_utm.y(), 
                        dem_dataset, dem_transform
                    )
                    
                    # Calculate slope and aspect using GDAL processing
                    slope_path = str(output_path / "slope.tif")
                    aspect_path = str(output_path / "aspect.tif")
                    
                    try:
                        # Calculate slope
                        gdal.DEMProcessing(slope_path, dem_path, 'slope', format='GTiff')
                        
                        # Calculate aspect  
                        gdal.DEMProcessing(aspect_path, dem_path, 'aspect', format='GTiff')
                        
                        # Extract slope and aspect at site
                        slope_dataset = gdal.Open(slope_path)
                        aspect_dataset = gdal.Open(aspect_path)
                        
                        site_slope = get_elevation_at_point(
                            site_point_utm.x(), site_point_utm.y(),
                            slope_dataset, slope_dataset.GetGeoTransform()
                        ) if slope_dataset else 2.0
                        
                        site_aspect = get_elevation_at_point(
                            site_point_utm.x(), site_point_utm.y(),
                            aspect_dataset, aspect_dataset.GetGeoTransform()
                        ) if aspect_dataset else 180.0
                        
                        # Close datasets
                        if slope_dataset:
                            slope_dataset = None
                        if aspect_dataset:
                            aspect_dataset = None
                            
                    except Exception as e:
                        print(f"DEM processing error: {str(e)}")
                        site_slope = 2.0
                        site_aspect = 180.0
                    
                    # Close main dataset
                    dem_dataset = None
                else:
                    site_elevation = 100.0
                    site_slope = 2.0
                    site_aspect = 180.0
            except Exception as e:
                print(f"DEM loading error: {str(e)}")
                site_elevation = 100.0
                site_slope = 2.0
                site_aspect = 180.0
        else:
            # Default values for demo
            site_elevation = 100.0
            site_slope = 2.0
            site_aspect = 180.0
        
        # Analyze drainage patterns
        results["topographic_analysis"] = {
            "elevation_m": site_elevation,
            "slope_degrees": site_slope,
            "aspect_degrees": site_aspect,
            "drainage_direction": "north" if 315 <= site_aspect <= 45 else
                                "east" if 45 < site_aspect <= 135 else
                                "south" if 135 < site_aspect <= 225 else "west",
            "slope_category": "flat" if site_slope < 2 else
                            "gentle" if site_slope < 5 else
                            "moderate" if site_slope < 15 else "steep"
        }
        
        # =================================================================
        # 4. SOIL ANALYSIS (Simplified for demo)
        # =================================================================
        
        if soil_data_path and os.path.exists(soil_data_path):
            try:
                # Load soil data
                soil_layer = QgsVectorLayer(soil_data_path, "soil_data", "ogr")
                
                if soil_layer.isValid():
                    # Spatial query to find soil type at site
                    site_geom = QgsGeometry.fromPointXY(site_point_utm)
                    
                    soil_features = []
                    for feature in soil_layer.getFeatures():
                        if feature.geometry().contains(site_geom):
                            soil_features.append(feature)
                    
                    if soil_features:
                        soil_feature = soil_features[0]  # Take first match
                        
                        # Map soil properties (assuming standard field names)
                        soil_type = soil_feature.attribute('SOIL_TYPE') or 'loamy'
                        clay_percent = float(soil_feature.attribute('CLAY_PCT') or 30)
                        sand_percent = float(soil_feature.attribute('SAND_PCT') or 40)
                        organic_matter = float(soil_feature.attribute('ORG_MATTER') or 2)
                        
                        # Calculate infiltration rate based on soil composition
                        infiltration_rate = calculate_infiltration_rate(
                            clay_percent, sand_percent, organic_matter
                        )
                        
                        results["soil_analysis"] = {
                            "soil_type": soil_type,
                            "clay_percentage": clay_percent,
                            "sand_percentage": sand_percent,
                            "silt_percentage": 100 - clay_percent - sand_percent,
                            "organic_matter": organic_matter,
                            "infiltration_rate_mmh": infiltration_rate,
                            "permeability_class": classify_permeability(infiltration_rate),
                            "recharge_suitability": assess_recharge_suitability(infiltration_rate)
                        }
                    else:
                        # Default soil analysis
                        results["soil_analysis"] = create_default_soil_analysis()
                else:
                    results["soil_analysis"] = create_default_soil_analysis()
            except Exception as e:
                print(f"Soil analysis error: {str(e)}")
                results["soil_analysis"] = create_default_soil_analysis()
        else:
            # Default soil analysis for demo
            results["soil_analysis"] = create_default_soil_analysis()
        
        # =================================================================
        # 5. HYDROLOGICAL ANALYSIS
        # =================================================================
        
        # Calculate catchment area contributing to site
        contributing_area = calculate_contributing_area(
            site_coordinates, dem_path, analysis_radius
        )
        
        results["hydrological_analysis"] = {
            "contributing_area_ha": contributing_area / 10000,  # Convert to hectares
            "runoff_coefficient": estimate_runoff_coefficient(results.get("soil_analysis", {})),
            "time_of_concentration_min": estimate_time_of_concentration(
                contributing_area, results.get("topographic_analysis", {})
            )
        }
        
        # =================================================================
        # 6. SPATIAL SUITABILITY ANALYSIS
        # =================================================================
        
        suitability_factors = {}
        
        # Topographic suitability
        if "topographic_analysis" in results:
            topo = results["topographic_analysis"]
            slope_score = 10 - min(topo.get("slope_degrees", 0) * 2, 10)  # Lower slope = better
            elevation_score = 5  # Neutral unless we have regional elevation preferences
            suitability_factors["topographic"] = (slope_score + elevation_score) / 2
        
        # Soil suitability
        if "soil_analysis" in results:
            soil = results["soil_analysis"]
            infiltration_score = min(soil.get("infiltration_rate_mmh", 1) * 2, 10)
            clay_penalty = max(0, (soil.get("clay_percentage", 30) - 40) * 0.2)
            suitability_factors["soil"] = max(0, infiltration_score - clay_penalty)
        
        # Distance-based factors
        distance_factors = analyze_distance_factors(
            site_coordinates, analysis_radius, output_path
        )
        suitability_factors.update(distance_factors)
        
        # Overall suitability score
        overall_suitability = np.mean(list(suitability_factors.values()))
        
        results["spatial_suitability"] = {
            "individual_factors": suitability_factors,
            "overall_score": overall_suitability,
            "suitability_class": classify_suitability(overall_suitability),
            "limiting_factors": identify_limiting_factors(suitability_factors)
        }
        
        # =================================================================
        # 7. OPTIMIZATION AND DESIGN RECOMMENDATIONS
        # =================================================================
        
        # Optimal structure placement using spatial analysis
        if roof_polygon:
            optimal_locations = find_optimal_structure_locations(
                roof_shapely, site_point_utm, results
            )
            
            results["optimization_results"] = {
                "optimal_tank_location": optimal_locations.get("tank"),
                "optimal_recharge_locations": optimal_locations.get("recharge", []),
                "pipe_routing": optimal_locations.get("routing"),
                "excavation_suitability": assess_excavation_conditions(results)
            }
        
        # =================================================================
        # 8. VISUALIZATION AND MAPPING
        # =================================================================
        
        visualization_paths = create_analysis_visualizations(
            site_coordinates, results, output_path, analysis_radius
        )
        
        results["visualizations"] = {
            "site_map": str(visualization_paths.get("site_map", "")),
            "suitability_map": str(visualization_paths.get("suitability_map", "")),
            "elevation_profile": str(visualization_paths.get("elevation_profile", "")),
            "flow_analysis": str(visualization_paths.get("flow_analysis", ""))
        }
        
        # =================================================================
        # 9. FINAL RECOMMENDATIONS
        # =================================================================
        
        recommendations = generate_gis_based_recommendations(results)
        results["recommendations"] = recommendations
        
        # Save results to JSON
        results_path = output_path / "gis_analysis_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        return results
        
    except Exception as e:
        logging.error(f"GIS Analysis Error: {str(e)}")
        return {"error": str(e), "partial_results": results if 'results' in locals() else {}}

# =================================================================
# HELPER FUNCTIONS
# =================================================================

def create_default_soil_analysis() -> Dict[str, Any]:
    """Create default soil analysis for demo purposes"""
    clay_percent = 30.0
    sand_percent = 40.0
    organic_matter = 2.0
    
    infiltration_rate = calculate_infiltration_rate(clay_percent, sand_percent, organic_matter)
    
    return {
        "soil_type": "loamy",
        "clay_percentage": clay_percent,
        "sand_percentage": sand_percent,
        "silt_percentage": 100 - clay_percent - sand_percent,
        "organic_matter": organic_matter,
        "infiltration_rate_mmh": infiltration_rate,
        "permeability_class": classify_permeability(infiltration_rate),
        "recharge_suitability": assess_recharge_suitability(infiltration_rate)
    }

def calculate_infiltration_rate(clay_pct: float, sand_pct: float, organic_matter: float) -> float:
    """Calculate soil infiltration rate based on composition"""
    # Simplified infiltration rate calculation (mm/h)
    base_rate = 25.4  # 1 inch/hour baseline
    
    # Clay reduces infiltration
    clay_factor = max(0.1, 1 - (clay_pct / 100) * 0.8)
    
    # Sand increases infiltration
    sand_factor = 1 + (sand_pct / 100) * 0.5
    
    # Organic matter slightly increases infiltration
    organic_factor = 1 + (organic_matter / 100) * 0.2
    
    return base_rate * clay_factor * sand_factor * organic_factor

def classify_permeability(infiltration_rate: float) -> str:
    """Classify soil permeability based on infiltration rate"""
    if infiltration_rate < 1:
        return "very_low"
    elif infiltration_rate < 5:
        return "low"
    elif infiltration_rate < 15:
        return "moderate"
    elif infiltration_rate < 50:
        return "high"
    else:
        return "very_high"

def assess_recharge_suitability(infiltration_rate: float) -> str:
    """Assess suitability for artificial recharge"""
    if infiltration_rate < 2:
        return "not_suitable"
    elif infiltration_rate < 10:
        return "marginal"
    elif infiltration_rate < 30:
        return "suitable"
    else:
        return "highly_suitable"

def calculate_contributing_area(site_coords: Tuple[float, float], 
                              dem_path: str, radius: float) -> float:
    """Calculate contributing drainage area"""
    # Simplified calculation - in practice would use watershed delineation
    lat, lon = site_coords
    
    # Approximate area based on topographic analysis
    # This is a placeholder - actual implementation would use flow accumulation
    contributing_area = np.pi * (radius ** 2) * 0.7  # 70% of circular area
    
    return contributing_area

def estimate_runoff_coefficient(soil_data: Dict) -> float:
    """Estimate runoff coefficient based on soil properties"""
    if not soil_data:
        return 0.5  # Default moderate runoff
    
    infiltration_rate = soil_data.get("infiltration_rate_mmh", 10)
    clay_pct = soil_data.get("clay_percentage", 30)
    
    # Higher clay and lower infiltration = higher runoff
    base_coeff = 0.3
    clay_factor = (clay_pct / 100) * 0.4
    infiltration_factor = max(0, (20 - infiltration_rate) / 20) * 0.3
    
    return min(0.9, base_coeff + clay_factor + infiltration_factor)

def estimate_time_of_concentration(area_sqm: float, topo_data: Dict) -> float:
    """Estimate time of concentration for catchment"""
    if not topo_data:
        return 30  # Default 30 minutes
    
    # Simplified Kirpich equation approximation
    length_km = np.sqrt(area_sqm / np.pi) * 2 / 1000  # Approximate flow length
    slope_pct = topo_data.get("slope_degrees", 2) * 1.75  # Convert to percent
    
    # Time in minutes
    time_conc = 0.0195 * (length_km ** 0.77) * (slope_pct ** -0.385) * 60
    
    return max(10, min(180, time_conc))  # Clamp between 10-180 minutes

def analyze_distance_factors(site_coords: Tuple[float, float], 
                           radius: float, output_path: Path) -> Dict[str, float]:
    """Analyze distance-based suitability factors"""
    # Placeholder for actual distance analysis to infrastructure, water bodies, etc.
    factors = {
        "infrastructure_accessibility": 8.0,  # 0-10 score
        "water_body_proximity": 6.0,
        "urban_density": 7.0,
        "road_accessibility": 8.5
    }
    
    return factors

def classify_suitability(score: float) -> str:
    """Classify overall suitability score"""
    if score >= 8:
        return "excellent"
    elif score >= 6:
        return "good"
    elif score >= 4:
        return "fair"
    elif score >= 2:
        return "poor"
    else:
        return "unsuitable"

def identify_limiting_factors(factors: Dict[str, float]) -> List[str]:
    """Identify factors that limit suitability"""
    limiting_factors = []
    threshold = 4.0
    
    for factor, score in factors.items():
        if score < threshold:
            limiting_factors.append(factor)
    
    return limiting_factors

def find_optimal_structure_locations(roof_polygon: Polygon, 
                                   site_point: QgsPointXY,
                                   analysis_results: Dict) -> Dict[str, Any]:
    """Find optimal locations for RTRWH structures"""
    
    # Tank location - typically near building corner with good access
    roof_bounds = roof_polygon.bounds
    centroid = roof_polygon.centroid
    
    # Prefer corner locations for tanks
    corners = [
        Point(roof_bounds[0], roof_bounds[1]),  # SW
        Point(roof_bounds[2], roof_bounds[1]),  # SE
        Point(roof_bounds[2], roof_bounds[3]),  # NE
        Point(roof_bounds[0], roof_bounds[3])   # NW
    ]
    
    # Score corners based on accessibility and drainage
    corner_scores = []
    for corner in corners:
        # Distance to centroid (prefer corners)
        dist_score = corner.distance(centroid) / max(roof_polygon.length, 1)
        
        # Elevation advantage (if available)
        elev_score = 5.0  # Default neutral
        
        total_score = dist_score * 0.7 + elev_score * 0.3
        corner_scores.append(total_score)
    
    best_corner_idx = np.argmax(corner_scores)
    optimal_tank_location = {
        "coordinates": (corners[best_corner_idx].x, corners[best_corner_idx].y),
        "score": corner_scores[best_corner_idx],
        "rationale": "Corner location with good drainage access"
    }
    
    # Recharge locations - prefer areas with good soil infiltration
    recharge_locations = []
    if analysis_results.get("soil_analysis", {}).get("recharge_suitability") in ["suitable", "highly_suitable"]:
        # Create potential recharge points around the site
        buffer_geom = roof_polygon.buffer(20)  # 20m buffer
        
        # Sample points within buffer
        bounds = buffer_geom.bounds
        for i in range(3):  # Up to 3 recharge points
            x = bounds[0] + (bounds[2] - bounds[0]) * (i + 1) / 4
            y = bounds[1] + (bounds[3] - bounds[1]) * 0.5
            
            recharge_point = Point(x, y)
            if buffer_geom.contains(recharge_point):
                recharge_locations.append({
                    "coordinates": (recharge_point.x, recharge_point.y),
                    "type": "infiltration_pit",
                    "capacity_m3": 10 + i * 5
                })
    
    # Pipe routing - simple straight line connections
    routing = {
        "tank_connection": {
            "from": (centroid.x, centroid.y),
            "to": optimal_tank_location["coordinates"],
            "length_m": centroid.distance(Point(*optimal_tank_location["coordinates"]))
        },
        "recharge_connections": [
            {
                "from": optimal_tank_location["coordinates"],
                "to": loc["coordinates"],
                "length_m": Point(*optimal_tank_location["coordinates"]).distance(Point(*loc["coordinates"]))
            }
            for loc in recharge_locations
        ]
    }
    
    return {
        "tank": optimal_tank_location,
        "recharge": recharge_locations,
        "routing": routing
    }

def assess_excavation_conditions(analysis_results: Dict) -> Dict[str, Any]:
    """Assess conditions for excavation work"""
    soil_data = analysis_results.get("soil_analysis", {})
    topo_data = analysis_results.get("topographic_analysis", {})
    
    # Excavation difficulty score
    clay_pct = soil_data.get("clay_percentage", 30)
    slope_deg = topo_data.get("slope_degrees", 2)
    
    difficulty_score = (clay_pct / 10) + (slope_deg / 5)  # Higher = more difficult
    
    conditions = {
        "excavation_difficulty": "easy" if difficulty_score < 5 else
                               "moderate" if difficulty_score < 10 else "difficult",
        "recommended_equipment": get_equipment_recommendations(difficulty_score),
        "seasonal_constraints": assess_seasonal_constraints(analysis_results),
        "estimated_cost_factor": 1.0 + (difficulty_score - 5) * 0.1  # Cost multiplier
    }
    
    return conditions

def get_equipment_recommendations(difficulty_score: float) -> List[str]:
    """Recommend excavation equipment based on difficulty"""
    if difficulty_score < 5:
        return ["hand_tools", "small_excavator"]
    elif difficulty_score < 10:
        return ["medium_excavator", "compactor", "dewatering_pump"]
    else:
        return ["heavy_excavator", "rock_breaker", "dewatering_system", "shoring"]

def assess_seasonal_constraints(analysis_results: Dict) -> Dict[str, str]:
    """Assess seasonal constraints for construction"""
    return {
        "best_season": "dry_season",
        "avoid_season": "monsoon",
        "soil_conditions": "stable" if analysis_results.get("soil_analysis", {}).get("clay_percentage", 30) < 40 else "unstable_when_wet"
    }

def create_analysis_visualizations(site_coords: Tuple[float, float], 
                                 results: Dict, output_path: Path, 
                                 radius: float) -> Dict[str, Path]:
    """Create visualization maps and plots"""
    
    viz_paths = {}
    
    try:
        # Site overview map
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        
        lat, lon = site_coords
        
        # Create base map extent
        deg_radius = radius / 111000  # Convert meters to degrees
        extent = [lon - deg_radius, lon + deg_radius, lat - deg_radius, lat + deg_radius]
        
        # Plot site point
        ax.scatter(lon, lat, c='red', s=200, marker='*', label='Assessment Site', zorder=5)
        
        # Add analysis buffer
        buffer_circle = plt.Circle((lon, lat), deg_radius, fill=False, 
                                 linestyle='--', color='blue', label='Analysis Buffer')
        ax.add_patch(buffer_circle)
        
        # Suitability overlay (simplified)
        if "spatial_suitability" in results:
            suitability_score = results["spatial_suitability"]["overall_score"]
            color = plt.cm.RdYlGn(suitability_score / 10)  # Normalize to 0-1
            
            suitability_circle = plt.Circle((lon, lat), deg_radius * 0.5, 
                                          alpha=0.3, color=color, 
                                          label=f'Suitability: {suitability_score:.1f}/10')
            ax.add_patch(suitability_circle)
        
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title('RTRWH Site Analysis Overview')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        site_map_path = output_path / "site_overview_map.png"
        plt.savefig(site_map_path, dpi=300, bbox_inches='tight')
        plt.close()
        viz_paths["site_map"] = site_map_path
        
        # Suitability factors chart
        if "spatial_suitability" in results:
            factors = results["spatial_suitability"]["individual_factors"]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            factor_names = list(factors.keys())
            factor_scores = list(factors.values())
            
            bars = ax.bar(factor_names, factor_scores, 
                         color=['red' if score < 4 else 'yellow' if score < 7 else 'green' 
                               for score in factor_scores])
            ax.set_ylim(0, 10)
            ax.set_ylabel('Suitability Score (0-10)')
            ax.set_title('RTRWH Suitability Factors Analysis')
            ax.tick_params(axis='x', rotation=45)
            
            # Add score labels on bars
            for bar, score in zip(bars, factor_scores):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                       f'{score:.1f}', ha='center', va='bottom')
            
            suitability_chart_path = output_path / "suitability_factors.png"
            plt.savefig(suitability_chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            viz_paths["suitability_map"] = suitability_chart_path
        
    except Exception as e:
        print(f"Visualization error: {str(e)}")
    
    return viz_paths

def generate_gis_based_recommendations(results: Dict) -> Dict[str, Any]:
    """Generate comprehensive recommendations based on GIS analysis"""
    
    recommendations = {
        "priority_actions": [],
        "design_specifications": {},
        "implementation_sequence": [],
        "risk_mitigation": [],
        "monitoring_requirements": []
    }
    
    # Priority actions based on suitability analysis
    if "spatial_suitability" in results:
        suitability = results["spatial_suitability"]
        overall_score = suitability.get("overall_score", 5)
        limiting_factors = suitability.get("limiting_factors", [])
        
        if overall_score >= 7:
            recommendations["priority_actions"].append("Proceed with full RTRWH implementation")
        elif overall_score >= 5:
            recommendations["priority_actions"].append("Implement with site modifications")
        else:
            recommendations["priority_actions"].append("Conduct detailed feasibility study")
        
        # Address limiting factors
        for factor in limiting_factors:
            if "soil" in factor:
                recommendations["priority_actions"].append("Consider soil improvement or alternative recharge methods")
            if "topographic" in factor:
                recommendations["priority_actions"].append("Modify site grading or drainage design")
            if "accessibility" in factor:
                recommendations["priority_actions"].append("Improve site access for construction and maintenance")
    
    # Design specifications based on analysis results
    design_specs = {}
    
    # Storage system specifications
    if "topographic_analysis" in results:
        topo = results["topographic_analysis"]
        slope = topo.get("slope_degrees", 2)
        
        if slope > 10:
            design_specs["storage_type"] = "elevated_tank"
            design_specs["foundation_type"] = "reinforced_concrete"
        else:
            design_specs["storage_type"] = "ground_level_tank"
            design_specs["foundation_type"] = "standard_concrete"
    
    # Recharge system specifications
    if "soil_analysis" in results:
        soil = results["soil_analysis"]
        infiltration_rate = soil.get("infiltration_rate_mmh", 10)
        clay_pct = soil.get("clay_percentage", 30)
        
        if infiltration_rate > 20:
            design_specs["recharge_type"] = "infiltration_pit"
            design_specs["pit_depth"] = "3-4 meters"
        elif infiltration_rate > 5:
            design_specs["recharge_type"] = "recharge_trench"
            design_specs["trench_length"] = "based_on_available_space"
        else:
            design_specs["recharge_type"] = "injection_well"
            design_specs["well_depth"] = "6-10 meters"
        
        if clay_pct > 40:
            design_specs["filter_media"] = "enhanced_sand_gravel_mix"
            design_specs["geotextile"] = "required"
    
    # Filtration specifications
    design_specs["first_flush_diverter"] = "required"
    design_specs["filtration_stages"] = ["coarse_filter", "fine_filter", "activated_carbon"]
    
    recommendations["design_specifications"] = design_specs
    
    # Implementation sequence
    sequence = [
        "Site preparation and access improvement",
        "Excavation for recharge structures",
        "Installation of storage system",
        "Piping and connection work", 
        "Filtration system installation",
        "Testing and commissioning",
        "Landscaping and site restoration"
    ]
    
    # Modify sequence based on soil conditions
    if results.get("soil_analysis", {}).get("clay_percentage", 30) > 40:
        sequence.insert(2, "Soil conditioning and amendment")
    
    recommendations["implementation_sequence"] = sequence
    
    return recommendations

# Main execution
if __name__ == "__main__":
    try:
        print("Starting RTRWH GIS Analysis...")
        
        # Test with sample data
        results = advanced_gis_analysis_for_rtrwh(
            site_coordinates=(28.6139, 77.2090),  # Delhi coordinates
            roof_polygon=[(28.614, 77.209), (28.615, 77.209), (28.615, 77.210), (28.614, 77.210)],
            analysis_radius=1000.0,
            output_dir="/app/output"
        )
        
        print("Analysis completed successfully!")
        print("=" * 50)
        print("RESULTS SUMMARY:")
        print("=" * 50)
        
        # Print key results
        if "site_info" in results:
            site_info = results["site_info"]
            print(f"Site Coordinates: {site_info.get('coordinates_wgs84')}")
            print(f"UTM Zone: {site_info.get('utm_zone')}")
            if "roof_analysis" in site_info:
                roof = site_info["roof_analysis"]
                print(f"Roof Area: {roof.get('area_sqm', 0):.2f} sq meters")
        
        if "spatial_suitability" in results:
            suitability = results["spatial_suitability"]
            print(f"Overall Suitability: {suitability.get('overall_score', 0):.1f}/10 ({suitability.get('suitability_class', 'unknown')})")
        
        if "recommendations" in results:
            recommendations = results["recommendations"]
            print("\nTop Priority Actions:")
            for action in recommendations.get("priority_actions", [])[:3]:
                print(f"  - {action}")
        
        print("\n" + "=" * 50)
        print("Full results saved to: /app/output/gis_analysis_results.json")
        print("Visualizations saved in: /app/output/")
        
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up QGIS
        if 'qgs' in globals():
            qgs.exitQgis()
