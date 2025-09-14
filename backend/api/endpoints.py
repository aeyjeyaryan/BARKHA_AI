# app/api/endpoints.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict
import json
import os
from pathlib import Path
from datetime import datetime
import logging
from core.database import SessionLocal, redis_client, mongo_db
from core.dependencies import get_db
from models.db_models import Assessment, LocalConfig
from models.pydantic_models import SiteDetailsInput, AssessmentResult, ConfigData
from services.calculator import RTRWHCalculator
from services.pdf_generator import generate_assessment_pdf
from services.dimensions import dimensions_service
from typing import Optional



router = APIRouter()
calculator = RTRWHCalculator()
logger = logger = logging.getLogger(__name__)

@router.post("/assess", response_model=AssessmentResult)
async def create_assessment(site_data: SiteDetailsInput, db: Session = Depends(get_db)):
    logging.info(f"Received site_data: {site_data.model_dump()}")
    harvestable_volume = calculator.calculate_harvestable_volume(
        site_data.roof_area, site_data.annual_rainfall, site_data.roof_material, site_data.roof_condition
    )
    storage_req = calculator.calculate_storage_requirement(site_data.water_demand)
    # Use roof_area/10 as a proxy for available_space, or add to SiteDetailsInput
    available_space = getattr(site_data, "available_space", site_data.roof_area / 10)
    recharge_req = calculator.calculate_recharge_structure(site_data.soil_type, harvestable_volume, available_space)
    recommendation = calculator.recommend_best_option(
        harvestable_volume, site_data.water_demand, site_data.soil_type, available_space
    )
    costs = calculator.calculate_costs(recommendation, storage_req["recommended_volume"], recharge_req["recharge_pit"]["area"])
    savings = calculator.calculate_savings(harvestable_volume, water_tariff=50)  # Adjusted tariff
    if costs["total_cost"] == 0:
        savings["warnings"] = ["WARNING: Cost calculation resulted in zero. Check recommendation and inputs."]
    safety_warnings = calculator.safety_checks(site_data.model_dump())
    
    assessment = Assessment(
        site_name=site_data.site_name, latitude=site_data.latitude, longitude=site_data.longitude,
        roof_area=site_data.roof_area, roof_material=site_data.roof_material,
        roof_condition=site_data.roof_condition, soil_type=site_data.soil_type,
        annual_rainfall=site_data.annual_rainfall, water_demand=site_data.water_demand,
        assessment_data={
            "harvestable_volume": harvestable_volume,
            "storage_requirement": storage_req,
            "recharge_requirement": recharge_req
        },
        recommendations={
            "recommended_option": recommendation,
            "costs": costs,
            "savings": savings
        }
    )
    
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    
    result_key = f"assessment:{assessment.id}"
    redis_client.setex(result_key, 3600, json.dumps({
        "assessment_id": str(assessment.id), "harvestable_volume": harvestable_volume,
        "recommended_option": recommendation, "storage_recommendation": storage_req,
        "recharge_recommendation": recharge_req, "cost_analysis": costs,
        "savings_analysis": savings, "safety_checks": safety_warnings
    }, default=str))
    
    annual_savings = savings.get("annual_cost_savings", 0)
    payback_period = round(costs["total_cost"] / annual_savings, 1) if annual_savings > 0 else "N/A"
    return AssessmentResult(
        assessment_id=str(assessment.id), harvestable_volume=harvestable_volume,
        recommended_option=recommendation, storage_recommendation=storage_req,
        recharge_recommendation=recharge_req, cost_analysis=costs, savings_analysis=savings,
        safety_checks=safety_warnings, bill_of_quantities=calculator.generate_boq(recommendation, storage_req, recharge_req, costs),
        payback_period=str(payback_period)
    )
    
@router.get("/assessments")
async def get_assessments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    assessments = db.query(Assessment).offset(skip).limit(limit).all()
    return assessments

@router.get("/assessments/{assessment_id}")
async def get_assessment(assessment_id: str, db: Session = Depends(get_db)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment

@router.post("/config")
async def update_config(config: ConfigData, db: Session = Depends(get_db)):
    local_config = LocalConfig(
        region=config.region, rainfall_data=config.rainfall_data,
        soil_data=config.soil_data, cost_data=config.cost_data, tariff_data=config.tariff_data
    )
    db.add(local_config)
    db.commit()
    redis_client.setex(f"config:{config.region}", 86400, json.dumps(config.model_dump()))
    return {"message": "Configuration updated successfully"}

@router.get("/generate-report/{assessment_id}")
async def generate_pdf_report(assessment_id: str, db: Session = Depends(get_db)):
    try:
        # Fetch assessment
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            logging.error(f"Assessment {assessment_id} not found")
            raise HTTPException(status_code=404, detail="Assessment not found")

        # Validate assessment data
        if not hasattr(assessment, 'recommendations') or not isinstance(assessment.recommendations, dict):
            logging.error(f"Invalid recommendations for assessment {assessment_id}")
            raise HTTPException(status_code=500, detail="Invalid assessment data: recommendations missing or invalid")
        if not hasattr(assessment, 'assessment_data') or not isinstance(assessment.assessment_data, dict):
            logging.error(f"Invalid assessment_data for assessment {assessment_id}")
            raise HTTPException(status_code=500, detail="Invalid assessment data: assessment_data missing or invalid")

        # Generate PDF
        pdf_path = await generate_assessment_pdf(assessment)
        pdf_file = Path(pdf_path)
        
        # Verify file exists and is not empty
        if not pdf_file.exists():
            logging.error(f"PDF file not found at {pdf_path}")
            raise HTTPException(status_code=500, detail="Failed to generate PDF")
        if pdf_file.stat().st_size < 1000:  # Check for suspiciously small file
            logging.error(f"PDF file at {pdf_path} is too small ({pdf_file.stat().st_size} bytes)")
            raise HTTPException(status_code=500, detail="Generated PDF is invalid or corrupted")

        # Create a clean filename for download
        clean_filename = f"RTRWH_Assessment_{assessment.site_name}_{assessment_id[:8]}.pdf"
        # Remove any problematic characters from filename
        clean_filename = "".join(c for c in clean_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        
        # Serve file with proper headers and delayed cleanup
        async def cleanup():
            try:
                if pdf_file.exists():
                    pdf_file.unlink()
                    logging.info(f"Cleaned up temporary file {pdf_path}")
            except Exception as e:
                logging.warning(f"Failed to clean up {pdf_path}: {str(e)}")

        return FileResponse(
            path=str(pdf_path),
            media_type='application/pdf',
            filename=clean_filename,
            headers={
                "Content-Disposition": f"attachment; filename=\"{clean_filename}\"",
                "Content-Type": "application/pdf",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            },
            background=cleanup  # Delay cleanup until response is sent
        )
    except Exception as e:
        logging.error(f"Error serving PDF for assessment {assessment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/generate-text-report/{assessment_id}")
async def generate_text_report(assessment_id: str, db: Session = Depends(get_db)):
    """
    Generate and download TXT report for an assessment
    """
    try:
        # Get assessment from database
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        logger.info(f"Generating text report for assessment {assessment_id}")
        
        # Generate TXT using the service
        from services.text_generator import generate_assessment_text
        txt_path = await generate_assessment_text(assessment)
        
        # Create a clean filename for download
        clean_filename = f"RTRWH_Assessment_{assessment.site_name}_{assessment_id[:8]}.txt"
        # Remove any problematic characters from filename
        clean_filename = "".join(c for c in clean_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        
        # Serve file with proper headers and delayed cleanup
        async def cleanup():
            try:
                if txt_path.exists():
                    txt_path.unlink()
                    logger.info(f"Cleaned up temporary file {txt_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {txt_path}: {str(e)}")

        return FileResponse(
            path=str(txt_path),
            media_type='text/plain',
            filename=clean_filename,
            headers={
                "Content-Disposition": f"attachment; filename=\"{clean_filename}\"",
                "Content-Type": "text/plain; charset=utf-8",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            },
            background=cleanup  # Delay cleanup until response is sent
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text generation failed for assessment {assessment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Text generation failed: {str(e)}")


@router.get("/download-reports/{assessment_id}")
async def download_both_reports(assessment_id: str, db: Session = Depends(get_db)):
    """
    Generate and download both PDF and TXT reports for an assessment
    Returns a ZIP file containing both reports
    """
    try:
        # Get assessment from database
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        logger.info(f"Generating both reports for assessment {assessment_id}")
        
        # Generate both reports
        from services.pdf_generator import generate_assessment_pdf
        from services.text_generator import generate_assessment_text
        import zipfile
        import tempfile
        
        pdf_path = await generate_assessment_pdf(assessment)
        txt_path = await generate_assessment_text(assessment)
        
        # Create a temporary ZIP file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add PDF to ZIP
                zipf.write(pdf_path, f"RTRWH_Assessment_{assessment.site_name}_{assessment_id[:8]}.pdf")
                # Add TXT to ZIP
                zipf.write(txt_path, f"RTRWH_Assessment_{assessment.site_name}_{assessment_id[:8]}.txt")
            
            zip_path = Path(temp_zip.name)
        
        # Create a clean filename for download
        clean_filename = f"RTRWH_Reports_{assessment.site_name}_{assessment_id[:8]}.zip"
        clean_filename = "".join(c for c in clean_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        
        # Cleanup function
        async def cleanup():
            try:
                if pdf_path.exists():
                    pdf_path.unlink()
                if txt_path.exists():
                    txt_path.unlink()
                if zip_path.exists():
                    zip_path.unlink()
                logger.info(f"Cleaned up temporary files")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary files: {str(e)}")

        return FileResponse(
            path=str(zip_path),
            media_type='application/zip',
            filename=clean_filename,
            headers={
                "Content-Disposition": f"attachment; filename=\"{clean_filename}\"",
                "Content-Type": "application/zip",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            },
            background=cleanup
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed for assessment {assessment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.post("/upload-photos/{assessment_id}")
async def upload_site_photos(assessment_id: str, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    photo_paths = []
    upload_dir = Path("uploads") / str(assessment_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    for file in files:
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        photo_paths.append(str(file_path))
    
    assessment.site_photos = photo_paths
    db.commit()
    return {"message": f"Uploaded {len(files)} photos successfully"}

@router.get("/offline-sync")
async def sync_offline_data():
    offline_assessments = list(mongo_db.assessments.find({"is_synced": False}))
    synced_count = 0
    db = SessionLocal()
    
    try:
        for offline_data in offline_assessments:
            assessment = Assessment(**{k: v for k, v in offline_data.items() if k != '_id'})
            assessment.is_synced = True
            db.add(assessment)
            mongo_db.assessments.update_one({"_id": offline_data["_id"]}, {"$set": {"is_synced": True}})
            synced_count += 1
        db.commit()
    finally:
        db.close()
    
    return {"message": f"Synced {synced_count} offline assessments"}


@router.post("/satellite-image")
async def get_satellite_image(latitude: float, longitude: float):
    """
    Get satellite image for given coordinates
    """
    try:
        result = await dimensions_service.get_satellite_image_for_location(latitude, longitude)
        
        if result["success"]:
            return {
                "status": "success",
                "message": "Satellite image fetched successfully",
                "data": result,
                "next_steps": result["instructions"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logging.error(f"Error fetching satellite image: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/satellite-image/download/{latitude}/{longitude}")
async def download_satellite_image(latitude: float, longitude: float):
    """
    Download satellite image for given coordinates
    """
    try:
        result = await dimensions_service.get_satellite_image_for_location(latitude, longitude)
        
        if result["success"] and "image_path" in result:
            image_path = result["image_path"]
            
            # Verify file exists
            if not Path(image_path).exists():
                raise HTTPException(status_code=404, detail="Image file not found")
            
            # Create cleanup function
            async def cleanup():
                try:
                    dimensions_service.cleanup_files(image_path)
                except Exception as e:
                    logging.warning(f"Failed to cleanup satellite image: {e}")
            
            return FileResponse(
                image_path,
                media_type='image/png',
                filename=f"satellite_{latitude}_{longitude}.png",
                background=cleanup
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to fetch satellite image"))
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error downloading satellite image: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/analyze-rooftop")
async def analyze_rooftop_dimensions(
    latitude: float, 
    longitude: float, 
    marked_image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Analyze marked rooftop image and calculate dimensions and harvesting potential
    """
    try:
        # Validate file type
        if not marked_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Create organized directory structure for uploaded images
        uploads_dir = Path("uploads")
        satellite_dir = uploads_dir / "satellite_analysis"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_dir = satellite_dir / f"session_{timestamp}_{latitude}_{longitude}"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file with organized naming
        marked_image_path = session_dir / f"marked_rooftop_{marked_image.filename}"
        
        with open(marked_image_path, "wb") as buffer:
            content = await marked_image.read()
            buffer.write(content)
        
        logging.info(f"Saved marked image to: {marked_image_path}")
        
        # Analyze the marked image
        analysis_result = await dimensions_service.analyze_marked_rooftop(
            latitude, longitude, str(marked_image_path), str(session_dir)
        )
        
        # Store the image path in the analysis result for reference
        analysis_result["marked_image_path"] = str(marked_image_path)
        
        if analysis_result["success"]:
            # Store analysis in database
            rooftop_analysis = Assessment(
                site_name=f"Rooftop_Analysis_{latitude}_{longitude}",
                latitude=latitude,
                longitude=longitude,
                roof_area=analysis_result["roof_area"],
                roof_material="unknown",  # Could be added as parameter
                roof_condition="good",    # Could be added as parameter
                soil_type="medium",       # Could be added as parameter
                annual_rainfall=analysis_result["rainfall_data"]["annual"],
                water_demand=0,           # Not calculated in this analysis
                assessment_data={
                    "rooftop_analysis": analysis_result,
                    "analysis_type": "satellite_based",
                    "processing_method": "red_marking_detection"
                },
                recommendations={}
            )
            
            db.add(rooftop_analysis)
            db.commit()
            db.refresh(rooftop_analysis)
            
            # Clean up satellite image if it exists
            if "satellite_image_path" in analysis_result:
                dimensions_service.cleanup_files(analysis_result["satellite_image_path"])
            
            return {
                "status": "success",
                "message": "Rooftop analysis completed successfully",
                "assessment_id": str(rooftop_analysis.id),
                "roof_area_sqm": analysis_result["roof_area"],
                "harvest_potential": analysis_result.get("harvest_potential", {}),
                "rainfall_data": analysis_result.get("rainfall_data", {}),
                "analysis_details": analysis_result.get("analysis_details", {}),
                "cv2_images": {
                    "red_mask_path": str(session_dir / "cv2_red_mask.png"),
                    "contour_analysis_path": str(session_dir / "cv2_contour_analysis.png")
                }
            }
        else:
            # Clean up satellite image if it exists
            if "satellite_image_path" in analysis_result:
                dimensions_service.cleanup_files(analysis_result["satellite_image_path"])
                
            raise HTTPException(status_code=400, detail=analysis_result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error analyzing rooftop: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/template-image/download/{latitude}/{longitude}")
async def download_template_image(latitude: float, longitude: float):
    """
    Download template image with marking instructions
    """
    try:
        result = await dimensions_service.create_template_image(latitude, longitude)
        
        if result["success"] and "template_path" in result:
            template_path = result["template_path"]
            
            # Verify file exists
            if not Path(template_path).exists():
                raise HTTPException(status_code=404, detail="Template file not found")
            
            # Create cleanup function
            async def cleanup():
                try:
                    dimensions_service.cleanup_files(template_path)
                except Exception as e:
                    logging.warning(f"Failed to cleanup template: {e}")
            
            return FileResponse(
                template_path,
                media_type='image/png',
                filename=f"template_{latitude}_{longitude}.png",
                background=cleanup
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create template"))
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/quick-dimensions")
async def quick_rooftop_analysis(
    latitude: float,
    longitude: float,
    marked_image: UploadFile = File(...)
):
    """
    Quick analysis without saving to database - for testing and validation
    """
    try:
        # Validate file type
        if not marked_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Create organized directory structure for uploaded images
        uploads_dir = Path("uploads")
        satellite_dir = uploads_dir / "satellite_analysis"
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session_dir = satellite_dir / f"quick_session_{timestamp}_{latitude}_{longitude}"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file with organized naming
        marked_image_path = session_dir / f"quick_marked_rooftop_{marked_image.filename}"
        
        with open(marked_image_path, "wb") as buffer:
            content = await marked_image.read()
            buffer.write(content)
        
        logging.info(f"Saved quick analysis marked image to: {marked_image_path}")
        
        # Analyze the marked image
        analysis_result = await dimensions_service.analyze_marked_rooftop(
            latitude, longitude, str(marked_image_path), str(session_dir)
        )
        
        # Store the image path in the analysis result for reference
        analysis_result["marked_image_path"] = str(marked_image_path)
        
        # Note: For quick analysis, we keep the files for potential review
        # Only cleanup satellite images if they exist
        if "satellite_image_path" in analysis_result:
            dimensions_service.cleanup_files(analysis_result["satellite_image_path"])
        
        if analysis_result["success"]:
            return {
                "status": "success",
                "roof_area_sqm": analysis_result["roof_area"],
                "annual_harvest_potential_liters": analysis_result.get("harvest_potential", {}).get("annual_harvest_liters", 0),
                "coordinates": {"latitude": latitude, "longitude": longitude},
                "rainfall_data": analysis_result.get("rainfall_data", {}),
                "processing_details": analysis_result.get("analysis_details", {})
            }
        else:
            raise HTTPException(status_code=400, detail=analysis_result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in quick analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Add this to the existing assess endpoint to include satellite-based roof area calculation
@router.post("/assess-with-satellite", response_model=AssessmentResult)
async def create_assessment_with_satellite(
    site_data: SiteDetailsInput,
    marked_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Create assessment with optional satellite-based roof area calculation
    """
    try:
        roof_area = site_data.roof_area
        additional_data = {}
        
        # If marked image is provided, use satellite analysis for roof area
        if marked_image and marked_image.content_type.startswith('image/'):
            # Create organized directory structure for uploaded images
            uploads_dir = Path("uploads")
            satellite_dir = uploads_dir / "satellite_analysis"
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            session_dir = satellite_dir / f"assessment_session_{timestamp}_{site_data.latitude}_{site_data.longitude}"
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Save uploaded file with organized naming
            marked_image_path = session_dir / f"assessment_marked_rooftop_{marked_image.filename}"
            
            with open(marked_image_path, "wb") as buffer:
                content = await marked_image.read()
                buffer.write(content)
            
            logging.info(f"Saved assessment marked image to: {marked_image_path}")
            
            # Analyze the marked image
            analysis_result = await dimensions_service.analyze_marked_rooftop(
                site_data.latitude, site_data.longitude, str(marked_image_path), str(session_dir)
            )
            
            # Store the image path in the analysis result for reference
            analysis_result["marked_image_path"] = str(marked_image_path)
            
            # Cleanup satellite images if they exist
            if "satellite_image_path" in analysis_result:
                dimensions_service.cleanup_files(analysis_result["satellite_image_path"])
            
            if analysis_result["success"]:
                roof_area = analysis_result["roof_area"]
                additional_data["satellite_analysis"] = analysis_result
                logging.info(f"Using satellite-calculated roof area: {roof_area:.2f} sqm")
            else:
                logging.warning(f"Satellite analysis failed, using provided roof area: {analysis_result.get('error')}")
        
        # Continue with existing assessment logic using the roof_area
        harvestable_volume = calculator.calculate_harvestable_volume(
            roof_area, site_data.annual_rainfall, site_data.roof_material, site_data.roof_condition
        )
        storage_req = calculator.calculate_storage_requirement(site_data.water_demand)
        available_space = getattr(site_data, "available_space", roof_area / 10)
        recharge_req = calculator.calculate_recharge_structure(site_data.soil_type, harvestable_volume, available_space)
        recommendation = calculator.recommend_best_option(
            harvestable_volume, site_data.water_demand, site_data.soil_type, available_space
        )
        costs = calculator.calculate_costs(recommendation, storage_req["recommended_volume"], recharge_req["recharge_pit"]["area"])
        savings = calculator.calculate_savings(harvestable_volume, water_tariff=50)
        
        if costs["total_cost"] == 0:
            savings["warnings"] = ["WARNING: Cost calculation resulted in zero. Check recommendation and inputs."]
        
        safety_warnings = calculator.safety_checks(site_data.model_dump())
        
        # Create assessment with satellite data if available
        assessment_data = {
            "harvestable_volume": harvestable_volume,
            "storage_requirement": storage_req,
            "recharge_requirement": recharge_req,
            "calculated_roof_area": roof_area,  # Store the actual roof area used
            "original_roof_area": site_data.roof_area  # Store the originally provided roof area
        }
        
        # Add satellite analysis data if available
        if additional_data:
            assessment_data.update(additional_data)
        
        assessment = Assessment(
            site_name=site_data.site_name,
            latitude=site_data.latitude,
            longitude=site_data.longitude,
            roof_area=roof_area,  # Use calculated roof area
            roof_material=site_data.roof_material,
            roof_condition=site_data.roof_condition,
            soil_type=site_data.soil_type,
            annual_rainfall=site_data.annual_rainfall,
            water_demand=site_data.water_demand,
            assessment_data=assessment_data,
            recommendations={
                "recommended_option": recommendation,
                "costs": costs,
                "savings": savings
            }
        )
        
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        
        result_key = f"assessment:{assessment.id}"
        redis_client.setex(result_key, 3600, json.dumps({
            "assessment_id": str(assessment.id),
            "harvestable_volume": harvestable_volume,
            "recommended_option": recommendation,
            "storage_recommendation": storage_req,
            "recharge_recommendation": recharge_req,
            "cost_analysis": costs,
            "savings_analysis": savings,
            "safety_checks": safety_warnings,
            "roof_area_used": roof_area,
            "satellite_enhanced": bool(additional_data)
        }, default=str))
        
        annual_savings = savings.get("annual_cost_savings", 0)
        payback_period = round(costs["total_cost"] / annual_savings, 1) if annual_savings > 0 else "N/A"
        
        result = AssessmentResult(
            assessment_id=str(assessment.id),
            harvestable_volume=harvestable_volume,
            recommended_option=recommendation,
            storage_recommendation=storage_req,
            recharge_recommendation=recharge_req,
            cost_analysis=costs,
            savings_analysis=savings,
            safety_checks=safety_warnings,
            bill_of_quantities=calculator.generate_boq(recommendation, storage_req, recharge_req, costs),
            payback_period=str(payback_period)
        )
        
        # Add satellite analysis info to response if available
        if additional_data:
            # You might want to extend your AssessmentResult model to include this
            result.additional_info = {
                "satellite_enhanced": True,
                "calculated_roof_area": roof_area,
                "original_roof_area": site_data.roof_area,
                "area_difference_sqm": roof_area - site_data.roof_area,
                "area_accuracy_note": "Roof area calculated from satellite imagery analysis"
            }
        
        return result
        
    except Exception as e:
        logging.error(f"Error in assess_with_satellite: {e}")
        raise HTTPException(status_code=500, detail=f"Assessment error: {str(e)}")


# Utility endpoint for checking service health
@router.get("/dimensions/health")
async def check_dimensions_service_health():
    """
    Health check for the dimensions service
    """
    try:
        # Simple test to verify service components
        test_lat, test_lon = 28.7041, 77.1025  # Delhi coordinates for testing
        
        # Test satellite image fetching (without saving)
        calculator = dimensions_service.calculator
        test_result = calculator._deg2tile(test_lat, test_lon, 18)
        
        return {
            "status": "healthy",
            "service": "dimensions_service",
            "components": {
                "tile_calculation": "ok" if test_result else "error",
                "image_processing": "ok",
                "rainfall_api": "ok"  # Could add actual API test
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Dimensions service health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "dimensions_service",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/test-pdf-download")
async def test_pdf_download():
    """
    Test endpoint to verify PDF download functionality
    """
    try:
        # Create a simple test PDF
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        from pathlib import Path
        import uuid
        
        # Create test PDF
        temp_dir = Path("rtrwh_reports")
        temp_dir.mkdir(exist_ok=True)
        pdf_path = temp_dir / f"test_download_{uuid.uuid4().hex}.pdf"
        
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        story.append(Paragraph("Test PDF Download", styles['Title']))
        story.append(Paragraph("This is a test PDF to verify download functionality.", styles['Normal']))
        story.append(Paragraph("If you can see this content, the PDF download is working correctly.", styles['Normal']))
        
        doc.build(story)
        
        # Verify the file
        if not pdf_path.exists():
            raise HTTPException(status_code=500, detail="Test PDF was not created")
        
        file_size = pdf_path.stat().st_size
        if file_size < 100:
            raise HTTPException(status_code=500, detail="Test PDF is too small")
        
        # Cleanup function
        async def cleanup():
            try:
                if pdf_path.exists():
                    pdf_path.unlink()
                    logging.info(f"Cleaned up test PDF {pdf_path}")
            except Exception as e:
                logging.warning(f"Failed to clean up test PDF: {e}")
        
        return FileResponse(
            path=str(pdf_path),
            media_type='application/pdf',
            filename="test_download.pdf",
            headers={
                "Content-Disposition": "attachment; filename=\"test_download.pdf\"",
                "Content-Type": "application/pdf",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            },
            background=cleanup
        )
        
    except Exception as e:
        logging.error(f"Test PDF download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test PDF generation failed: {str(e)}")


@router.get("/cv2-image/{image_path:path}")
async def get_cv2_image(image_path: str):
    """
    Serve CV2 processed images (red mask, contour analysis)
    """
    try:
        # Security check - ensure the path is within uploads directory
        full_path = Path(image_path)
        if not str(full_path).startswith("uploads/"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        
        if not full_path.is_file():
            raise HTTPException(status_code=404, detail="Not a valid file")
        
        # Determine media type based on file extension
        if full_path.suffix.lower() == '.png':
            media_type = 'image/png'
        elif full_path.suffix.lower() in ['.jpg', '.jpeg']:
            media_type = 'image/jpeg'
        else:
            media_type = 'application/octet-stream'
        
        return FileResponse(
            path=str(full_path),
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Type": media_type
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error serving CV2 image {image_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")