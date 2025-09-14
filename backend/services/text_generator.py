"""
Text Report Generator Service
Generates plain text reports for rainwater harvesting assessments
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from models.db_models import Assessment

logger = logging.getLogger(__name__)

async def generate_assessment_text(assessment: Assessment) -> Path:
    """
    Generate a plain text report for the assessment
    
    Args:
        assessment: Assessment object containing all data
        
    Returns:
        Path to the generated text file
    """
    try:
        logger.info(f"Generating text report for assessment {assessment.id}")
        
        # Create output directory
        output_dir = Path("rtrwh_reports")
        output_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        import uuid
        filename = f"assessment_{assessment.site_name}_{assessment.id[:8]}_{uuid.uuid4().hex[:8]}.txt"
        text_path = output_dir / filename
        
        # Generate text content
        text_content = _generate_text_content(assessment)
        
        # Write to file
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        # Verify file was created
        if not text_path.exists():
            raise Exception("Text file was not created")
        
        file_size = text_path.stat().st_size
        if file_size < 100:
            raise Exception("Text file is too small")
        
        logger.info(f"Text report generated successfully at {text_path}, size: {file_size} bytes")
        return text_path
        
    except Exception as e:
        logger.error(f"Failed to generate text report: {e}")
        raise

def _generate_text_content(assessment: Assessment) -> str:
    """Generate the text content for the assessment report"""
    
    # Get assessment data safely
    assessment_data = assessment.assessment_data or {}
    recommendations = assessment.recommendations or {}
    
    # Header
    content = []
    content.append("=" * 80)
    content.append("RAINWATER HARVESTING ASSESSMENT REPORT")
    content.append("=" * 80)
    content.append(f"Assessment ID: {assessment.id}")
    content.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    
    # Site Details
    content.append("SITE DETAILS")
    content.append("-" * 40)
    content.append(f"Site Name: {assessment.site_name}")
    content.append(f"Location: {assessment.latitude:.6f}, {assessment.longitude:.6f}")
    content.append(f"Roof Area: {assessment.roof_area:.2f} m²")
    content.append(f"Roof Material: {assessment.roof_material.title()}")
    content.append(f"Roof Condition: {assessment.roof_condition.title()}")
    content.append(f"Soil Type: {assessment.soil_type.title()}")
    content.append(f"Annual Rainfall: {assessment.annual_rainfall:.2f} mm")
    content.append(f"Daily Water Demand: {assessment.water_demand:.2f} L/day")
    content.append("")
    
    # Assessment Results
    content.append("ASSESSMENT RESULTS")
    content.append("-" * 40)
    
    # Harvestable volume
    harvestable_volume = assessment_data.get('harvestable_volume', 0)
    content.append(f"Harvestable Volume: {harvestable_volume:.2f} m³/year")
    
    # Storage recommendation
    storage_rec = assessment_data.get('storage_recommendation', {})
    if storage_rec:
        content.append(f"Required Storage Volume: {storage_rec.get('required_volume', 0):.2f} m³")
        content.append(f"Recommended Storage Volume: {storage_rec.get('recommended_volume', 0):.2f} m³")
        content.append(f"Storage Days: {storage_rec.get('storage_days', 0)} days")
    
    # Recharge recommendation
    recharge_rec = assessment_data.get('recharge_recommendation', {})
    if recharge_rec:
        content.append("")
        content.append("RECHARGE STRUCTURE RECOMMENDATIONS")
        content.append("-" * 40)
        
        recharge_pit = recharge_rec.get('recharge_pit', {})
        if recharge_pit:
            content.append(f"Recharge Pit Diameter: {recharge_pit.get('diameter', 0):.2f} m")
            content.append(f"Recharge Pit Depth: {recharge_pit.get('depth', 0):.2f} m")
            content.append(f"Recharge Pit Area: {recharge_pit.get('area', 0):.2f} m²")
        
        recharge_trench = recharge_rec.get('recharge_trench', {})
        if recharge_trench:
            content.append(f"Recharge Trench: {recharge_trench.get('length', 0):.2f}m x {recharge_trench.get('width', 0):.2f}m x {recharge_trench.get('depth', 0):.2f}m")
        
        content.append(f"Infiltration Rate: {recharge_rec.get('infiltration_rate', 0):.2f} mm/hr")
        content.append(f"Suitability Score: {recharge_rec.get('suitability_score', 0)}/10")
    
    content.append("")
    
    # Recommendations
    if recommendations:
        content.append("RECOMMENDATIONS")
        content.append("-" * 40)
        
        # Recommended option
        recommended_option = recommendations.get('recommended_option', 'unknown')
        content.append(f"Recommended Option: {recommended_option.title()}")
        content.append("")
        
        # Cost analysis
        cost_analysis = recommendations.get('cost_analysis', {})
        if cost_analysis:
            content.append("COST ANALYSIS")
            content.append("-" * 20)
            content.append(f"Storage Tank Cost: ₹{cost_analysis.get('storage_tank_cost', 0):,}")
            content.append(f"Recharge Structure Cost: ₹{cost_analysis.get('recharge_structure_cost', 0):,}")
            content.append(f"Piping Cost: ₹{cost_analysis.get('piping_cost', 0):,}")
            content.append(f"Filtration Cost: ₹{cost_analysis.get('filtration_cost', 0):,}")
            content.append(f"Labor Cost: ₹{cost_analysis.get('labor_cost', 0):,}")
            content.append(f"Material Contingency: ₹{cost_analysis.get('material_contingency', 0):,}")
            content.append(f"Tax: ₹{cost_analysis.get('tax', 0):,}")
            content.append(f"TOTAL COST: ₹{cost_analysis.get('total_cost', 0):,}")
            content.append("")
        
        # Savings analysis
        savings_analysis = recommendations.get('savings_analysis', {})
        if savings_analysis:
            content.append("SAVINGS ANALYSIS")
            content.append("-" * 20)
            content.append(f"Annual Water Saved: {savings_analysis.get('annual_water_saved', 0):.2f} m³")
            content.append(f"Annual Cost Savings: ₹{savings_analysis.get('annual_cost_savings', 0):,}")
            content.append(f"Monthly Savings: ₹{savings_analysis.get('monthly_savings', 0):,}")
            content.append(f"Water Tariff Used: ₹{savings_analysis.get('water_tariff_used', 0):.2f}/m³")
            content.append("")
        
        # Payback period
        payback_period = recommendations.get('payback_period', 'N/A')
        content.append(f"PAYBACK PERIOD: {payback_period} years")
        content.append("")
        
        # Safety checks
        safety_checks = recommendations.get('safety_checks', [])
        if safety_checks:
            content.append("SAFETY CHECKS & WARNINGS")
            content.append("-" * 30)
            for check in safety_checks:
                content.append(f"• {check}")
            content.append("")
        
        # Bill of quantities
        bill_of_quantities = recommendations.get('bill_of_quantities', {})
        if bill_of_quantities:
            content.append("BILL OF QUANTITIES")
            content.append("-" * 20)
            items = bill_of_quantities.get('items', [])
            for item in items:
                content.append(f"{item.get('item', 'N/A')}: {item.get('quantity', 'N/A')} @ ₹{item.get('rate', 0):,} = ₹{item.get('amount', 0):,}")
            content.append(f"TOTAL: ₹{bill_of_quantities.get('total_cost', 0):,}")
            content.append("")
    
    # Footer
    content.append("=" * 80)
    content.append("END OF REPORT")
    content.append("=" * 80)
    
    return "\n".join(content)
