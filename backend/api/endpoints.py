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

router = APIRouter()
calculator = RTRWHCalculator()

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

        # Serve file with response cleanup
        async def cleanup():
            try:
                if pdf_file.exists():
                    pdf_file.unlink()
                    logging.info(f"Cleaned up temporary file {pdf_path}")
            except Exception as e:
                logging.warning(f"Failed to clean up {pdf_path}: {str(e)}")

        return FileResponse(
            pdf_path,
            media_type='application/pdf',
            filename=f"RTRWH_Assessment_{assessment.site_name}_{assessment_id[:8]}.pdf",
            headers={"Content-Disposition": f"attachment; filename=RTRWH_Assessment_{assessment.site_name}_{assessment_id[:8]}.pdf"},
            background=cleanup  # Delay cleanup until response is sent
        )
    except Exception as e:
        logging.error(f"Error serving PDF for assessment {assessment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

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