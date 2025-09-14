# services/dimensions.py
import requests
import json
import numpy as np
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
from io import BytesIO
import cv2
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RooftopDimensionsCalculator:
    """
    FastAPI-compatible rainwater harvesting calculator that extracts roof dimensions
    from satellite imagery and calculates harvesting potential.
    """
    
    def __init__(self):
        self.roof_area = 0
        self.rainfall_data = {}
        self.original_image = None
        self.marked_image = None
        
    def get_satellite_image(self, lat: float, lon: float, zoom: int = 18) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Get satellite image using free OpenStreetMap tiles
        Returns the image and temporary file path
        """
        try:
            logger.info(f"Fetching satellite image for coordinates: {lat}, {lon}")
            
            # Calculate tile coordinates
            tile_x, tile_y = self._deg2tile(lat, lon, zoom)
            
            # Get multiple tiles to create a larger image
            tiles = []
            for dx in range(-1, 2):  # 3x3 grid of tiles
                row = []
                for dy in range(-1, 2):
                    tile_url = f"https://tile.openstreetmap.org/{zoom}/{tile_x + dx}/{tile_y + dy}.png"
                    try:
                        response = requests.get(
                            tile_url, 
                            headers={'User-Agent': 'RainwaterCalculator/1.0'},
                            timeout=10
                        )
                        if response.status_code == 200:
                            tile_img = Image.open(BytesIO(response.content))
                            row.append(tile_img)
                        else:
                            # Create blank tile if failed
                            row.append(Image.new('RGB', (256, 256), color='gray'))
                    except Exception as e:
                        logger.warning(f"Failed to fetch tile: {e}")
                        row.append(Image.new('RGB', (256, 256), color='gray'))
                tiles.append(row)
            
            # Combine tiles
            combined_img = self._combine_tiles(tiles)
            self.original_image = combined_img
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f"_satellite_{lat}_{lon}.png",
                delete=False
            )
            combined_img.save(temp_file.name)
            
            logger.info(f"Satellite image saved to: {temp_file.name}")
            return combined_img, temp_file.name
            
        except Exception as e:
            logger.error(f"Error getting satellite image: {e}")
            return None, None
    
    def _deg2tile(self, lat: float, lon: float, zoom: int) -> Tuple[int, int]:
        """Convert latitude/longitude to tile coordinates"""
        lat_rad = np.radians(lat)
        n = 2.0 ** zoom
        tile_x = int((lon + 180.0) / 360.0 * n)
        tile_y = int((1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n)
        return tile_x, tile_y
    
    def _combine_tiles(self, tiles) -> Image.Image:
        """Combine 3x3 grid of tiles into single image"""
        tile_size = 256
        combined_width = tile_size * 3
        combined_height = tile_size * 3
        
        combined_img = Image.new('RGB', (combined_width, combined_height))
        
        for row_idx, row in enumerate(tiles):
            for col_idx, tile in enumerate(row):
                x_offset = col_idx * tile_size
                y_offset = row_idx * tile_size
                combined_img.paste(tile, (x_offset, y_offset))
        
        return combined_img
    
    def process_marked_image(self, image_path: str, lat: float, lon: float, session_dir: str = None) -> Dict[str, Any]:
        """
        Process uploaded image with marked rooftop and return analysis results
        """
        try:
            logger.info(f"Processing marked image: {image_path}")
            
            # Load the marked image
            marked_img = Image.open(image_path)
            self.marked_image = marked_img
            
            # Extract red markings and calculate area
            analysis_result = self._extract_red_markings(marked_img, lat, session_dir)
            
            if analysis_result["roof_area"] > 0:
                self.roof_area = analysis_result["roof_area"]
                logger.info(f"Detected roof area: {self.roof_area:.2f} square meters")
                
                # Get rainfall data and calculate potential
                rainfall_success = self._get_rainfall_data(lat, lon)
                harvest_potential = self._calculate_harvest_potential()
                
                return {
                    "success": True,
                    "roof_area": self.roof_area,
                    "rainfall_data": self.rainfall_data,
                    "harvest_potential": harvest_potential,
                    "analysis_details": analysis_result,
                    "rainfall_data_available": rainfall_success
                }
            else:
                logger.warning("No red markings detected in uploaded image")
                return {
                    "success": False,
                    "error": "No red markings detected. Please ensure you marked the roof with RED color.",
                    "roof_area": 0
                }
                
        except Exception as e:
            logger.error(f"Error processing marked image: {e}")
            return {
                "success": False,
                "error": f"Error processing image: {str(e)}",
                "roof_area": 0
            }
    
    def _extract_red_markings(self, image: Image.Image, lat: float, session_dir: str = None) -> Dict[str, Any]:
        """
        Extract red markings from the uploaded image and calculate area
        """
        try:
            # Convert PIL to numpy array
            img_array = np.array(image)
            
            # Convert RGB to HSV for better red detection
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # Define range for red color in HSV
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 255])
            
            # Create masks for red color
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = mask1 + mask2
            
            # Apply morphological operations to clean up the mask
            kernel = np.ones((3,3), np.uint8)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
            
            # Save the red mask image if session directory is provided
            if session_dir:
                try:
                    mask_path = Path(session_dir) / "cv2_red_mask.png"
                    cv2.imwrite(str(mask_path), red_mask)
                    logger.info(f"Saved red mask image to: {mask_path}")
                except Exception as e:
                    logger.warning(f"Failed to save red mask: {e}")
            
            # Find contours
            contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return {"roof_area": 0, "contour_count": 0}
            
            # Find the largest contour (assuming it's the roof)
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Create contour visualization
            contour_img = img_array.copy()
            cv2.drawContours(contour_img, [largest_contour], -1, (0, 255, 0), 3)
            
            # Save the contour visualization if session directory is provided
            if session_dir:
                try:
                    contour_path = Path(session_dir) / "cv2_contour_analysis.png"
                    cv2.imwrite(str(contour_path), cv2.cvtColor(contour_img, cv2.COLOR_RGB2BGR))
                    logger.info(f"Saved contour analysis image to: {contour_path}")
                except Exception as e:
                    logger.warning(f"Failed to save contour image: {e}")
            
            # Calculate area in pixels
            pixel_area = cv2.contourArea(largest_contour)
            
            # Convert to square meters
            # At zoom level 18, each pixel represents about 0.6 meters
            pixel_to_meter = 0.6 * np.cos(np.radians(lat))
            area_sqm = pixel_area * (pixel_to_meter ** 2)
            
            return {
                "roof_area": area_sqm,
                "pixel_area": pixel_area,
                "contour_count": len(contours),
                "largest_contour_area": cv2.contourArea(largest_contour),
                "conversion_factor": pixel_to_meter
            }
            
        except Exception as e:
            logger.error(f"Error extracting red markings: {e}")
            return {"roof_area": 0, "error": str(e)}
    
    def _get_rainfall_data(self, lat: float, lon: float) -> bool:
        """Get rainfall data from free weather API"""
        try:
            logger.info(f"Fetching rainfall data for coordinates: {lat}, {lon}")
            
            # Using Open-Meteo (free weather API)
            url = "https://archive-api.open-meteo.com/v1/era5"
            params = {
                'latitude': lat,
                'longitude': lon,
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'daily': 'precipitation_sum',
                'timezone': 'auto'
            }
            
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                daily_precip = data['daily']['precipitation_sum']
                
                # Calculate monthly averages
                monthly_rainfall = []
                for month in range(12):
                    month_start = month * 30
                    month_end = min((month + 1) * 30, len(daily_precip))
                    month_data = [x for x in daily_precip[month_start:month_end] if x is not None]
                    monthly_rainfall.append(sum(month_data))
                
                self.rainfall_data = {
                    'monthly': monthly_rainfall,
                    'annual': sum(monthly_rainfall),
                    'daily_data': daily_precip,
                    'source': 'open-meteo'
                }
                
                logger.info(f"Rainfall data fetched successfully. Annual rainfall: {self.rainfall_data['annual']:.2f} mm")
                return True
                
        except Exception as e:
            logger.warning(f"Error getting rainfall data from API: {e}")
            
        # Use default rainfall data if API fails
        logger.info("Using default rainfall data")
        self.rainfall_data = {
            'monthly': [50, 40, 60, 80, 120, 150, 200, 180, 140, 100, 70, 55],
            'annual': 1245,
            'daily_data': [],
            'source': 'default'
        }
        return False
    
    def _calculate_harvest_potential(self) -> Dict[str, Any]:
        """Calculate rainwater harvesting potential"""
        if self.roof_area == 0 or not self.rainfall_data:
            return {"error": "Missing roof area or rainfall data"}
        
        # Harvesting efficiency (typically 70-90%)
        efficiency = 0.8
        
        # Calculate monthly and annual harvest potential
        annual_rainfall_m = self.rainfall_data['annual'] / 1000  # Convert mm to meters
        annual_harvest = self.roof_area * annual_rainfall_m * efficiency
        
        monthly_harvest = []
        for monthly_mm in self.rainfall_data['monthly']:
            monthly_m = monthly_mm / 1000
            monthly_harvest.append(self.roof_area * monthly_m * efficiency)
        
        return {
            "annual_harvest_liters": round(annual_harvest),
            "annual_harvest_cubic_meters": round(annual_harvest / 1000, 2),
            "daily_average_liters": round(annual_harvest / 365),
            "monthly_harvest_liters": [round(x) for x in monthly_harvest],
            "efficiency_factor": efficiency,
            "roof_area_used": self.roof_area,
            "annual_rainfall_mm": self.rainfall_data['annual']
        }
    
    def create_drawing_template(self, lat: float, lon: float) -> Optional[str]:
        """Create a template image with instructions for manual marking"""
        try:
            if not self.original_image:
                logger.error("No satellite image available for template creation")
                return None
            
            # Create a copy of the original image
            template = self.original_image.copy()
            draw = ImageDraw.Draw(template)
            
            # Add instructions text
            instructions = [
                "INSTRUCTIONS:",
                "1. Use RED color to outline your rooftop",
                "2. Draw lines around the roof perimeter", 
                "3. Save and upload the marked image"
            ]
            
            # Add semi-transparent background for text
            text_bg = Image.new('RGBA', template.size, (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_bg)
            text_draw.rectangle([10, 10, 400, 100], fill=(255, 255, 255, 200))
            
            template = Image.alpha_composite(template.convert('RGBA'), text_bg)
            template = template.convert('RGB')
            
            # Add text
            draw = ImageDraw.Draw(template)
            y_offset = 15
            for instruction in instructions:
                draw.text((15, y_offset), instruction, fill=(0, 0, 0))
                y_offset += 20
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f"_template_{lat}_{lon}.png",
                delete=False
            )
            template.save(temp_file.name)
            
            logger.info(f"Drawing template created: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Error creating drawing template: {e}")
            return None
    
    def cleanup_temp_files(self, *file_paths: str) -> None:
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file_path}: {e}")
    
    def get_comprehensive_analysis(self, lat: float, lon: float, marked_image_path: str, session_dir: str = None) -> Dict[str, Any]:
        """
        Complete workflow: get satellite image, process marked image, and return comprehensive analysis
        """
        try:
            # Step 1: Get satellite image
            original_img, temp_satellite_path = self.get_satellite_image(lat, lon)
            if not original_img:
                return {
                    "success": False,
                    "error": "Failed to fetch satellite image",
                    "step": "satellite_fetch"
                }
            
            # Step 2: Process marked image
            analysis_result = self.process_marked_image(marked_image_path, lat, lon, session_dir)
            
            if analysis_result["success"]:
                # Add satellite image info to result
                analysis_result["satellite_image_path"] = temp_satellite_path
                analysis_result["coordinates"] = {"latitude": lat, "longitude": lon}
                analysis_result["processing_timestamp"] = datetime.now().isoformat()
                
                return analysis_result
            else:
                # Cleanup on failure
                self.cleanup_temp_files(temp_satellite_path)
                return analysis_result
                
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            return {
                "success": False,
                "error": f"Comprehensive analysis failed: {str(e)}",
                "step": "comprehensive_analysis"
            }


# FastAPI-compatible service functions
class DimensionsService:
    """Service class for FastAPI integration"""
    
    def __init__(self):
        self.calculator = RooftopDimensionsCalculator()
    
    async def get_satellite_image_for_location(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Get satellite image for given coordinates"""
        try:
            image, temp_path = self.calculator.get_satellite_image(latitude, longitude)
            
            if image and temp_path:
                return {
                    "success": True,
                    "image_path": temp_path,
                    "coordinates": {"latitude": latitude, "longitude": longitude},
                    "instructions": [
                        "Download the satellite image",
                        "Use any image editor to mark your rooftop with RED color",
                        "Upload the marked image for analysis"
                    ]
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to fetch satellite image for the given coordinates"
                }
                
        except Exception as e:
            logger.error(f"Error in get_satellite_image_for_location: {e}")
            return {
                "success": False,
                "error": f"Service error: {str(e)}"
            }
    
    async def analyze_marked_rooftop(self, latitude: float, longitude: float, marked_image_path: str, session_dir: str = None) -> Dict[str, Any]:
        """Analyze marked rooftop image and calculate harvesting potential"""
        try:
            result = self.calculator.get_comprehensive_analysis(latitude, longitude, marked_image_path, session_dir)
            return result
            
        except Exception as e:
            logger.error(f"Error in analyze_marked_rooftop: {e}")
            return {
                "success": False,
                "error": f"Analysis service error: {str(e)}"
            }
    
    async def create_template_image(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Create a template image with marking instructions"""
        try:
            # First get satellite image
            image, _ = self.calculator.get_satellite_image(latitude, longitude)
            if not image:
                return {
                    "success": False,
                    "error": "Failed to fetch satellite image for template creation"
                }
            
            # Create template
            template_path = self.calculator.create_drawing_template(latitude, longitude)
            
            if template_path:
                return {
                    "success": True,
                    "template_path": template_path,
                    "coordinates": {"latitude": latitude, "longitude": longitude}
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create drawing template"
                }
                
        except Exception as e:
            logger.error(f"Error in create_template_image: {e}")
            return {
                "success": False,
                "error": f"Template service error: {str(e)}"
            }
    
    def cleanup_files(self, *file_paths: str) -> None:
        """Cleanup temporary files"""
        self.calculator.cleanup_temp_files(*file_paths)


# Global service instance for FastAPI
dimensions_service = DimensionsService()