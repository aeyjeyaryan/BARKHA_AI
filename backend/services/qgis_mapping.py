import os
import json
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import tempfile
import logging

# QGIS and GDAL imports
from qgis.core import (
    QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
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

def advanced_gis_analysis_for_rtrwh(
    site_coordinates: Tuple[float, float],
    roof_polygon: Optional[List[Tuple[float, float]]] = None,
    analysis_radius: float = 1000.0,
    dem_path: Optional[str] = None,
    soil_data_path: Optional[str] = None,
    land_use_path: Optional[str] = None,
    rainfall_raster_path: Optional[str] = None,
    output_dir: str = "./gis_analysis_output"
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
    
    # Initialize QGIS Application
    qgs = QgsApplication([], False)
    qgs.initQgis()
    
    # Initialize processing
    Processing.initialize()
    
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
        # 3. TOPOGRAPHIC ANALYSIS USING DEM
        # =================================================================
        
        if dem_path and os.path.exists(dem_path):
            # Load DEM using GDAL
            dem_dataset = gdal.Open(dem_path)
            dem_band = dem_dataset.GetRasterBand(1)
            dem_transform = dem_dataset.GetGeoTransform()
            dem_projection = dem_dataset.GetProjection()
            
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
            
            # Create analysis buffer around site
            buffer_geom = QgsGeometry.fromPointXY(site_point_utm).buffer(analysis_radius)
            buffer_bbox = buffer_geom.boundingBox()
            
            # Calculate slope and aspect using GDAL processing
            slope_path = str(output_path / "slope.tif")
            aspect_path = str(output_path / "aspect.tif")
            
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
            )
            
            site_aspect = get_elevation_at_point(
                site_point_utm.x(), site_point_utm.y(),
                aspect_dataset, aspect_dataset.GetGeoTransform()
            )
            
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
            
            # Close datasets
            dem_dataset = None
            slope_dataset = None
            aspect_dataset = None
        
        # =================================================================
        # 4. SOIL ANALYSIS AND INFILTRATION ASSESSMENT
        # =================================================================
        
        if soil_data_path and os.path.exists(soil_data_path):
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
                    soil_attributes = soil_feature.attributes()
                    
                    # Map soil properties (assuming standard field names)
                    soil_type = soil_feature.attribute('SOIL_TYPE') or 'unknown'
                    clay_percent = soil_feature.attribute('CLAY_PCT') or 30
                    sand_percent = soil_feature.attribute('SAND_PCT') or 40
                    organic_matter = soil_feature.attribute('ORG_MATTER') or 2
                    
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
        
        # =================================================================
        # 5. HYDROLOGICAL ANALYSIS AND CATCHMENT DELINEATION
        # =================================================================
        
        # Create watershed analysis buffer
        analysis_buffer = shapely_site_point.buffer(analysis_radius / 111000)  # Convert to degrees
        
        # Flow direction and accumulation analysis
        if dem_path and os.path.exists(dem_path):
            flow_dir_path = str(output_path / "flow_direction.tif")
            flow_acc_path = str(output_path / "flow_accumulation.tif")
            
            # Use QGIS processing algorithms
            processing.run("gdal:fillnodata", {
                'INPUT': dem_path,
                'OUTPUT': str(output_path / "filled_dem.tif")
            })
            
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
    
    finally:
        # Clean up QGIS
        qgs.exitQgis()


# =================================================================
# HELPER FUNCTIONS
# =================================================================

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
            
            bars = ax.bar(factor_names, factor_scores, color=['red' if score < 4 else 'yellow' if score < 7 else 'green' for score in factor_scores])
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
        
        # Elevation profile (if topographic data available)
        if "topographic_analysis" in results:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Elevation and slope profile
            topo = results["topographic_analysis"]
            
            # Create synthetic profile data (in real implementation, extract from DEM)
            profile_distance = np.linspace(0, radius * 2, 100)
            site_elevation = topo.get("elevation_m", 100)
            site_slope = topo.get("slope_degrees", 2)
            
            # Synthetic elevation profile
            elevation_profile = site_elevation + np.sin(profile_distance / 200) * 10 + np.random.normal(0, 2, 100)
            slope_profile = np.gradient(elevation_profile) * 180 / np.pi + np.random.normal(0, 1, 100)
            
            ax1.plot(profile_distance, elevation_profile, 'b-', linewidth=2, label='Elevation')
            ax1.axhline(y=site_elevation, color='r', linestyle='--', label=f'Site Elevation ({site_elevation:.1f}m)')
            ax1.set_xlabel('Distance (m)')
            ax1.set_ylabel('Elevation (m)')
            ax1.set_title('Elevation Profile')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            ax2.plot(profile_distance, np.abs(slope_profile), 'g-', linewidth=2, label='Slope')
            ax2.axhline(y=site_slope, color='r', linestyle='--', label=f'Site Slope ({site_slope:.1f}°)')
            ax2.set_xlabel('Distance (m)')
            ax2.set_ylabel('Slope (degrees)')
            ax2.set_title('Slope Profile')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            elevation_profile_path = output_path / "elevation_profile.png"
            plt.savefig(elevation_profile_path, dpi=300, bbox_inches='tight')
            plt.close()
            viz_paths["elevation_profile"] = elevation_profile_path
        
        # Flow analysis diagram
        if "hydrological_analysis" in results:
            fig, ax = plt.subplots(figsize=(10, 8))
            
            hydro = results["hydrological_analysis"]
            
            # Create flow direction arrows (simplified)
            x_center, y_center = 0.5, 0.5
            arrow_length = 0.15
            
            # Simulate flow directions based on topography
            directions = [(0.3, 0.7), (0.7, 0.7), (0.3, 0.3), (0.7, 0.3)]
            flows = [(x_center, y_center), (x_center, y_center), (x_center, y_center), (x_center, y_center)]
            
            for i, (start_x, start_y) in enumerate(directions):
                end_x, end_y = flows[i]
                ax.arrow(start_x, start_y, end_x - start_x, end_y - start_y,
                        head_width=0.03, head_length=0.02, fc='blue', ec='blue', alpha=0.7)
            
            # Site point
            ax.scatter(x_center, y_center, c='red', s=300, marker='*', label='Site', zorder=5)
            
            # Contributing area circle
            contributing_circle = plt.Circle((x_center, y_center), 0.3, fill=False,
                                           linestyle='-', color='green', linewidth=2,
                                           label=f'Contributing Area: {hydro.get("contributing_area_ha", 0):.1f} ha')
            ax.add_patch(contributing_circle)
            
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_aspect('equal')
            ax.set_title('Hydrological Flow Analysis')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Add text annotations
            ax.text(0.05, 0.95, f"Runoff Coefficient: {hydro.get('runoff_coefficient', 0):.2f}", 
                   transform=ax.transAxes, fontsize=10, bbox=dict(boxstyle="round", facecolor='wheat'))
            ax.text(0.05, 0.88, f"Time of Concentration: {hydro.get('time_of_concentration_min', 0):.0f} min", 
                   transform=ax.transAxes, fontsize=10, bbox=dict(boxstyle="round", facecolor='wheat'))
            
            flow_analysis_path = output_path / "flow_analysis.png"
            plt.savefig(flow_analysis_path, dpi=300, bbox_inches='tight')
            plt.close()
            viz_paths["flow_analysis"] = flow_analysis_path
        
        # Soil analysis visualization
        if "soil_analysis" in results:
            soil = results["soil_analysis"]
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Soil composition pie chart
            soil_components = [
                soil.get("clay_percentage", 30),
                soil.get("sand_percentage", 40), 
                soil.get("silt_percentage", 30)
            ]
            soil_labels = ['Clay', 'Sand', 'Silt']
            colors = ['#8B4513', '#F4A460', '#D2691E']
            
            ax1.pie(soil_components, labels=soil_labels, colors=colors, autopct='%1.1f%%',
                   startangle=90, explode=(0.05, 0, 0))
            ax1.set_title('Soil Composition')
            
            # Infiltration rate comparison
            infiltration_categories = ['Very Low\n(<1)', 'Low\n(1-5)', 'Moderate\n(5-15)', 
                                     'High\n(15-50)', 'Very High\n(>50)']
            infiltration_ranges = [1, 5, 15, 50, 100]
            site_infiltration = soil.get("infiltration_rate_mmh", 10)
            
            colors = ['red' if site_infiltration < r else 'lightblue' for r in infiltration_ranges]
            colors[min(len(colors)-1, max(0, int(np.log10(max(site_infiltration, 0.1)) + 1)))] = 'green'
            
            ax2.bar(infiltration_categories, infiltration_ranges, color=colors, alpha=0.7)
            ax2.axhline(y=site_infiltration, color='red', linestyle='-', linewidth=3, 
                       label=f'Site Rate: {site_infiltration:.1f} mm/h')
            ax2.set_ylabel('Infiltration Rate (mm/h)')
            ax2.set_title('Infiltration Rate Classification')
            ax2.legend()
            ax2.tick_params(axis='x', rotation=45)
            
            soil_analysis_path = output_path / "soil_analysis.png"
            plt.savefig(soil_analysis_path, dpi=300, bbox_inches='tight')
            plt.close()
            viz_paths["soil_analysis"] = soil_analysis_path
        
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
    
    # Risk mitigation measures
    risks = []
    
    if results.get("topographic_analysis", {}).get("slope_degrees", 0) > 15:
        risks.append("Install slope stabilization measures")
        risks.append("Implement erosion control during construction")
    
    if results.get("soil_analysis", {}).get("infiltration_rate_mmh", 10) < 2:
        risks.append("Install overflow management system")
        risks.append("Consider waterproofing for storage structures")
    
    if results.get("hydrological_analysis", {}).get("runoff_coefficient", 0.5) > 0.7:
        risks.append("Design for high-intensity rainfall events")
        risks.append("Install additional drainage capacity")
    
    recommendations["risk_mitigation"] = risks
    
    # Monitoring requirements
    monitoring = [
        "Monthly water level monitoring in storage tank",
        "Quarterly infiltration rate testing",
        "Annual system efficiency assessment",
        "Water quality testing (if for potable use)",
        "Structural integrity inspection (annual)"
    ]
    
    # Add specific monitoring based on site conditions
    if results.get("soil_analysis", {}).get("clay_percentage", 30) > 35:
        monitoring.append("Seasonal soil stability monitoring")
    
    if results.get("spatial_suitability", {}).get("overall_score", 5) < 6:
        monitoring.append("Enhanced performance monitoring for first two years")
    
    recommendations["monitoring_requirements"] = monitoring
    
    # Cost optimization suggestions
    cost_optimizations = []
    
    if results.get("optimization_results", {}).get("excavation_suitability", {}).get("excavation_difficulty") == "easy":
        cost_optimizations.append("Consider manual excavation to reduce costs")
    
    if len(results.get("optimization_results", {}).get("optimal_recharge_locations", [])) > 2:
        cost_optimizations.append("Phase implementation of recharge structures")
    
    recommendations["cost_optimization"] = cost_optimizations
    
    return recommendations


# Additional utility functions for specialized GIS operations

def create_watershed_boundary(site_coords: Tuple[float, float], dem_path: str) -> Polygon:
    """Create watershed boundary using flow direction analysis"""
    try:
        # Open DEM
        with rasterio.open(dem_path) as dem:
            # Get flow direction (simplified - in practice use D8 or D-infinity)
            elevation = dem.read(1)
            
            # Simple watershed approximation using topographic analysis
            lat, lon = site_coords
            
            # Convert to raster coordinates
            row, col = dem.index(lon, lat)
            
            # Create approximate watershed boundary (circular buffer modified by elevation)
            center_elevation = elevation[row, col] if 0 <= row < elevation.shape[0] and 0 <= col < elevation.shape[1] else 0
            
            # Generate points around site and adjust based on elevation gradients
            angles = np.linspace(0, 2*np.pi, 36)
            boundary_points = []
            
            for angle in angles:
                # Base radius
                base_radius = 500  # meters
                
                # Sample elevation in this direction
                sample_row = int(row + np.sin(angle) * 20)
                sample_col = int(col + np.cos(angle) * 20)
                
                if 0 <= sample_row < elevation.shape[0] and 0 <= sample_col < elevation.shape[1]:
                    sample_elevation = elevation[sample_row, sample_col]
                    elevation_factor = max(0.5, min(2.0, center_elevation / max(sample_elevation, 1)))
                else:
                    elevation_factor = 1.0
                
                # Adjust radius based on elevation
                adjusted_radius = base_radius * elevation_factor
                
                # Convert back to geographic coordinates
                point_x = lon + np.cos(angle) * adjusted_radius / 111000  # Rough conversion to degrees
                point_y = lat + np.sin(angle) * adjusted_radius / 111000
                
                boundary_points.append((point_x, point_y))
            
            return Polygon(boundary_points)
    
    except Exception as e:
        print(f"Watershed boundary creation error: {str(e)}")
        # Fallback to circular buffer
        return shapely_site_point.buffer(500 / 111000)  # 500m buffer


def analyze_land_use_impacts(site_coords: Tuple[float, float], 
                           land_use_path: str, radius: float) -> Dict[str, Any]:
    """Analyze land use patterns around the site"""
    try:
        # Load land use data
        land_use_gdf = gpd.read_file(land_use_path)
        
        # Create analysis buffer
        lat, lon = site_coords
        site_buffer = shapely_box(lon - radius/111000, lat - radius/111000,
                                 lon + radius/111000, lat + radius/111000)
        
        # Spatial intersection
        intersecting_features = land_use_gdf[land_use_gdf.geometry.intersects(site_buffer)]
        
        # Calculate land use percentages
        land_use_stats = {}
        total_area = site_buffer.area
        
        for _, feature in intersecting_features.iterrows():
            land_use_type = feature.get('land_use', feature.get('class', 'unknown'))
            intersection = feature.geometry.intersection(site_buffer)
            area_fraction = intersection.area / total_area
            
            if land_use_type in land_use_stats:
                land_use_stats[land_use_type] += area_fraction
            else:
                land_use_stats[land_use_type] = area_fraction
        
        # Analyze implications for RTRWH
        runoff_implications = {}
        for land_use, fraction in land_use_stats.items():
            if 'urban' in land_use.lower() or 'built' in land_use.lower():
                runoff_implications['urban_runoff'] = fraction
            elif 'forest' in land_use.lower() or 'vegetation' in land_use.lower():
                runoff_implications['natural_infiltration'] = fraction
            elif 'agriculture' in land_use.lower():
                runoff_implications['agricultural_runoff'] = fraction
        
        return {
            "land_use_distribution": land_use_stats,
            "runoff_implications": runoff_implications,
            "dominant_land_use": max(land_use_stats.items(), key=lambda x: x[1]) if land_use_stats else ("unknown", 0)
        }
    
    except Exception as e:
        print(f"Land use analysis error: {str(e)}")
        return {"error": str(e)}


def calculate_optimal_pipe_routing(start_point: Tuple[float, float], 
                                 end_points: List[Tuple[float, float]],
                                 obstacles: Optional[List[Polygon]] = None) -> Dict[str, Any]:
    """Calculate optimal pipe routing using shortest path algorithms"""
    
    try:
        from scipy.spatial.distance import pdist, squareform
        from scipy.sparse.csgraph import minimum_spanning_tree
        
        # Create points array
        all_points = [start_point] + end_points
        points_array = np.array(all_points)
        
        # Calculate distance matrix
        distances = squareform(pdist(points_array))
        
        # Apply obstacle penalties (simplified)
        if obstacles:
            for i, point1 in enumerate(all_points):
                for j, point2 in enumerate(all_points):
                    if i != j:
                        line = LineString([point1, point2])
                        for obstacle in obstacles:
                            if line.intersects(obstacle):
                                distances[i, j] *= 1.5  # Penalty for crossing obstacles
        
        # Find minimum spanning tree for pipe network
        mst = minimum_spanning_tree(distances).toarray()
        
        # Extract routing information
        routing_plan = {
            "total_length_m": np.sum(mst[mst > 0]),
            "connections": [],
            "main_trunk": None,
            "branches": []
        }
        
        # Identify connections
        for i in range(len(all_points)):
            for j in range(i+1, len(all_points)):
                if mst[i, j] > 0:
                    routing_plan["connections"].append({
                        "from": all_points[i],
                        "to": all_points[j], 
                        "length_m": mst[i, j] * 111000,  # Convert to meters
                        "pipe_diameter": estimate_pipe_diameter(mst[i, j])
                    })
        
        return routing_plan
    
    except Exception as e:
        print(f"Pipe routing calculation error: {str(e)}")
        return {"error": str(e)}


def estimate_pipe_diameter(length_m: float, flow_rate: float = 10) -> str:
    """Estimate required pipe diameter based on length and flow rate"""
    # Simplified pipe sizing (in practice use hydraulic calculations)
    if length_m < 50:
        return "100mm"
    elif length_m < 100:
        return "150mm"
    elif length_m < 200:
        return "200mm"
    else:
        return "250mm"


def perform_seasonal_analysis(site_coords: Tuple[float, float],
                            rainfall_data: Dict[str, float]) -> Dict[str, Any]:
    """Perform seasonal analysis for RTRWH optimization"""
    
    seasonal_analysis = {
        "monsoon_optimization": {},
        "dry_season_strategy": {},
        "storage_sizing": {},
        "maintenance_schedule": {}
    }
    
    # Analyze monthly rainfall patterns
    monthly_data = rainfall_data.get("monthly", {})
    if monthly_data:
        monsoon_months = [month for month, rainfall in monthly_data.items() 
                         if rainfall > np.mean(list(monthly_data.values())) * 1.5]
        
        total_monsoon_rainfall = sum(monthly_data[month] for month in monsoon_months)
        total_annual_rainfall = sum(monthly_data.values())
        
        seasonal_analysis["monsoon_optimization"] = {
            "peak_months": monsoon_months,
            "monsoon_percentage": total_monsoon_rainfall / total_annual_rainfall * 100,
            "storage_strategy": "maximize_capture" if total_monsoon_rainfall > 800 else "distributed_capture"
        }
        
        # Dry season analysis
        dry_months = [month for month in monthly_data.keys() if month not in monsoon_months]
        dry_season_demand = len(dry_months) * 30  # Assume 30 days per month storage needed
        
        seasonal_analysis["dry_season_strategy"] = {
            "storage_requirement_days": dry_season_demand,
            "conservation_priority": "high" if dry_season_demand > 120 else "moderate",
            "alternative_sources": ["groundwater", "municipal_supply"] if dry_season_demand > 180 else ["groundwater"]
        }
    
    return seasonal_analysis


results = advanced_gis_analysis_for_rtrwh(
    site_coordinates=(28.6139, 77.2090),
    roof_polygon=[(28.614, 77.209), (28.615, 77.209), (28.615, 77.210), (28.614, 77.210)],
    analysis_radius=1000.0,
    dem_path="./data/elevation.tif",
    soil_data_path="./data/soil_types.shp",
    output_dir="./gis_analysis"
)

print(results)