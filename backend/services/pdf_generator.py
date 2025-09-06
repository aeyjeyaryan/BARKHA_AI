# app/services/pdf_generator.py
import tempfile
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from models.db_models import Assessment

async def generate_assessment_pdf(assessment: Assessment) -> str:
    """Generate PDF report for assessment"""
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f"assessment_{assessment.id}.pdf")
    
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1
    )
    story.append(Paragraph("RTRWH Assessment Report", title_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Site Details", styles['Heading2']))
    site_data = [
        ['Parameter', 'Value'],
        ['Site Name', assessment.site_name],
        ['Location', f"{assessment.latitude}, {assessment.longitude}"],
        ['Roof Area', f"{assessment.roof_area} m²"],
        ['Roof Material', assessment.roof_material.title()],
        ['Soil Type', assessment.soil_type.title()],
        ['Annual Rainfall', f"{assessment.annual_rainfall} mm"],
        ['Daily Water Demand', f"{assessment.water_demand} L/day"]
    ]
    site_table = Table(site_data)
    site_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(site_table)
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Assessment Results", styles['Heading2']))
    harvestable = assessment.assessment_data.get('harvestable_volume', 0)
    recommendation = assessment.recommendations.get('recommended_option', 'Unknown')
    story.append(Paragraph(f"Harvestable Volume: <b>{harvestable:.2f} m³/year</b>", styles['Normal']))
    story.append(Paragraph(f"Recommended Option: <b>{recommendation.replace('_', ' ').title()}</b>", styles['Normal']))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Cost Analysis", styles['Heading2']))
    costs = assessment.recommendations.get('costs', {})
    cost_data = [
        ['Component', 'Cost (INR)'],
        ['Storage System', f"₹{costs.get('storage_tank_cost', 0):,.2f}"],
        ['Recharge Structure', f"₹{costs.get('recharge_structure_cost', 0):,.2f}"],
        ['Piping & Fittings', f"₹{costs.get('piping_cost', 0):,.2f}"],
        ['Filtration System', f"₹{costs.get('filtration_cost', 0):,.2f}"],
        ['Labor Cost', f"₹{costs.get('labor_cost', 0):,.2f}"],
        ['Total Cost', f"₹{costs.get('total_cost', 0):,.2f}"]
    ]
    cost_table = Table(cost_data)
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(cost_table)
    story.append(Spacer(1, 12))
    
    story.append(Paragraph("Savings Analysis", styles['Heading2']))
    savings = assessment.recommendations.get('savings', {})
    story.append(Paragraph(f"Annual Water Saved: <b>{savings.get('annual_water_saved', 0):.2f} m³</b>", styles['Normal']))
    story.append(Paragraph(f"Annual Cost Savings: <b>₹{savings.get('annual_cost_savings', 0):,.2f}</b>", styles['Normal']))
    story.append(Paragraph(f"Monthly Savings: <b>₹{savings.get('monthly_savings', 0):,.2f}</b>", styles['Normal']))
    
    doc.build(story)
    return pdf_path