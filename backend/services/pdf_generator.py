import tempfile
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
import logging
from typing import Dict, Any
from models.db_models import Assessment
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_assessment_pdf(assessment: Assessment) -> str:
    """Generate a simple PDF report for RTRWH assessment"""
    try:
        # Validate assessment object
        if not isinstance(assessment, Assessment):
            logger.error("Invalid assessment object provided")
            raise ValueError("Assessment must be an instance of Assessment model")

        # Validate required data
        if not hasattr(assessment, 'recommendations') or not isinstance(assessment.recommendations, dict):
            logger.error(f"Invalid recommendations for assessment {assessment.id}")
            raise ValueError("Recommendations must be a dictionary")
        if not hasattr(assessment, 'assessment_data') or not isinstance(assessment.assessment_data, dict):
            logger.error(f"Invalid assessment_data for assessment {assessment.id}")
            raise ValueError("Assessment_data must be a dictionary")

        # Create unique temporary file path
        temp_dir = Path(tempfile.gettempdir()) / "rtrwh_reports"
        temp_dir.mkdir(exist_ok=True)
        pdf_path = temp_dir / f"assessment_{assessment.id}_{uuid.uuid4().hex}.pdf"

        # Initialize document
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            alignment=1,
            textColor=colors.darkblue
        )
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkgrey
        )
        normal_bold_style = ParagraphStyle(
            'NormalBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11
        )

        story = []

        # Title
        story.append(Paragraph("Rainwater Harvesting Assessment Report", title_style))
        story.append(Paragraph(f"Assessment ID: {assessment.id}", styles['Normal']))
        story.append(Spacer(1, 0.5*cm))

        # Site Details
        story.append(Paragraph("Site Details", subtitle_style))
        site_data = [
            ['Parameter', 'Value'],
            ['Site Name', str(assessment.site_name or 'N/A')],
            ['Location', f"{float(assessment.latitude):.6f}, {float(assessment.longitude):.6f}" if assessment.latitude is not None and assessment.longitude is not None else 'N/A'],
            ['Roof Area', f"{float(assessment.roof_area):.2f} m²" if assessment.roof_area is not None else 'N/A'],
            ['Roof Material', str(assessment.roof_material).title() if assessment.roof_material else 'N/A'],
            ['Roof Condition', str(assessment.roof_condition).title() if assessment.roof_condition else 'N/A'],
            ['Soil Type', str(assessment.soil_type).title() if assessment.soil_type else 'N/A'],
            ['Annual Rainfall', f"{float(assessment.annual_rainfall):.2f} mm" if assessment.annual_rainfall is not None else 'N/A'],
            ['Daily Water Demand', f"{float(assessment.water_demand):.2f} L/day" if assessment.water_demand is not None else 'N/A']
        ]
        site_table = Table(site_data, colWidths=[8*cm, 8*cm])
        site_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 10)
        ]))
        story.append(site_table)
        story.append(Spacer(1, 0.5*cm))

        # Assessment Results
        story.append(Paragraph("Assessment Results", subtitle_style))
        assessment_data = assessment.assessment_data or {}
        recommendations = assessment.recommendations or {}
        harvestable = float(assessment_data.get('harvestable_volume', 0.0))
        recommendation = str(recommendations.get('recommended_option', 'Unknown')).replace('_', ' ').title()
        storage_req = assessment_data.get('storage_recommendation', {})
        recharge_req = assessment_data.get('recharge_recommendation', {})
        recharge_pit = recharge_req.get('recharge_pit', {})
        results_data = [
            ['Parameter', 'Value'],
            ['Harvestable Volume', f"{harvestable:.2f} m³/year"],
            ['Recommended Option', recommendation],
            ['Storage Volume', f"{float(storage_req.get('recommended_volume', 0)):.2f} m³"],
            ['Storage Days', f"{int(storage_req.get('storage_days', 0))} days"],
            ['Recharge Pit Area', f"{float(recharge_pit.get('area', 0)):.2f} m²"],
            ['Infiltration Rate', f"{float(recharge_req.get('infiltration_rate', 0)):.2f} mm/hr"],
            ['Suitability Score', f"{int(recharge_req.get('suitability_score', 0))}/10"]
        ]
        results_table = Table(results_data, colWidths=[8*cm, 8*cm])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 10)
        ]))
        story.append(results_table)
        story.append(Spacer(1, 0.5*cm))

        # Cost Analysis
        story.append(Paragraph("Cost Analysis", subtitle_style))
        costs = recommendations.get('cost_analysis', {})
        cost_data = [
            ['Component', 'Cost (INR)'],
            ['Storage System', f"₹{float(costs.get('storage_tank_cost', 0)):,.2f}"],
            ['Recharge Structure', f"₹{float(costs.get('recharge_structure_cost', 0)):,.2f}"],
            ['Piping & Fittings', f"₹{float(costs.get('piping_cost', 0)):,.2f}"],
            ['Filtration System', f"₹{float(costs.get('filtration_cost', 0)):,.2f}"],
            ['Labor Cost', f"₹{float(costs.get('labor_cost', 0)):,.2f}"],
            ['Material Contingency', f"₹{float(costs.get('material_contingency', 0)):,.2f}"],
            ['Tax (GST)', f"₹{float(costs.get('tax', 0)):,.2f}"],
            ['Total Cost', f"₹{float(costs.get('total_cost', 0)):,.2f}"]
        ]
        cost_table = Table(cost_data, colWidths=[8*cm, 8*cm])
        cost_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 10)
        ]))
        story.append(cost_table)
        story.append(Spacer(1, 0.5*cm))

        # Savings Analysis
        story.append(Paragraph("Savings Analysis", subtitle_style))
        savings = recommendations.get('savings_analysis', {})
        payback_period = str(recommendations.get('payback_period', 'N/A'))
        savings_data = [
            ['Parameter', 'Value'],
            ['Annual Water Saved', f"{float(savings.get('annual_water_saved', 0)):.2f} m³"],
            ['Annual Cost Savings', f"₹{float(savings.get('annual_cost_savings', 0)):,.2f}"],
            ['Monthly Savings', f"₹{float(savings.get('monthly_savings', 0)):,.2f}"],
            ['Water Tariff Used', f"₹{float(savings.get('water_tariff_used', 0)):.2f}/m³"],
            ['Payback Period', payback_period]
        ]
        savings_table = Table(savings_data, colWidths=[8*cm, 8*cm])
        savings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 10)
        ]))
        story.append(savings_table)
        story.append(Spacer(1, 0.5*cm))

        # Bill of Quantities
        boq = recommendations.get('bill_of_quantities', {'items': [], 'total_cost': 0})
        if not isinstance(boq, dict):
            logger.warning(f"Invalid bill_of_quantities for assessment {assessment.id}")
            boq = {'items': [], 'total_cost': 0}
        if boq.get('items'):
            story.append(Paragraph("Bill of Quantities", subtitle_style))
            boq_data = [['Item', 'Quantity', 'Rate (INR)', 'Amount (INR)']] + [
                [
                    str(item.get('item', 'N/A')),
                    str(item.get('quantity', 'N/A')),
                    f"₹{float(item.get('rate', 0)):,.2f}",
                    f"₹{float(item.get('amount', 0)):,.2f}"
                ]
                for item in boq.get('items', []) if isinstance(item, dict) and all(k in item for k in ['item', 'quantity', 'rate', 'amount'])
            ]
            boq_data.append(['Total', '', '', f"₹{float(boq.get('total_cost', 0)):,.2f}"])
            boq_table = Table(boq_data, colWidths=[6*cm, 3*cm, 3*cm, 4*cm])
            boq_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 10)
            ]))
            story.append(boq_table)
            story.append(Spacer(1, 0.5*cm))

        # Safety Checks
        safety_checks = recommendations.get('safety_checks', [])
        if safety_checks:
            story.append(Paragraph("Safety and Compliance Checks", subtitle_style))
            for check in safety_checks:
                if not isinstance(check, str):
                    logger.warning(f"Invalid safety check format: {check}")
                    continue
                prefix = check.split(':')[0].strip().upper()
                color = colors.red if 'CRITICAL' in prefix else colors.orange if 'WARNING' in prefix else colors.black
                check_style = ParagraphStyle(
                    'CheckStyle',
                    parent=styles['Normal'],
                    textColor=color,
                    fontSize=10,
                    leading=12
                )
                story.append(Paragraph(str(check), check_style))
                story.append(Spacer(1, 0.3*cm))

        # Build PDF
        logger.info(f"Building PDF for assessment {assessment.id} at {pdf_path}")
        doc.build(story)
        file_size = pdf_path.stat().st_size if pdf_path.exists() else 0
        if file_size < 1000:
            logger.error(f"PDF file at {pdf_path} is too small ({file_size} bytes)")
            raise ValueError("Generated PDF is too small, likely corrupted")
        logger.info(f"PDF generated successfully at {pdf_path}, size: {file_size} bytes")
        return str(pdf_path)

    except Exception as e:
        logger.error(f"Error generating PDF for assessment {assessment.id}: {str(e)}")
        raise