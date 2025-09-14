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

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_str(value, default='N/A'):
    """Safely convert value to string"""
    try:
        if value is None:
            return default
        return str(value)
    except (ValueError, TypeError):
        return default

async def generate_assessment_pdf(assessment: Assessment) -> str:
    """Generate a simple PDF report for RTRWH assessment"""
    try:
        # Validate assessment object
        if not isinstance(assessment, Assessment):
            logger.error("Invalid assessment object provided")
            raise ValueError("Assessment must be an instance of Assessment model")

        # Log assessment data for debugging
        logger.info(f"Assessment data: {assessment.__dict__}")

        # Create unique temporary file path
        temp_dir = Path("rtrwh_reports")
        temp_dir.mkdir(exist_ok=True)
        pdf_path = temp_dir / f"assessment_{assessment.id}_{uuid.uuid4().hex}.pdf"

        # Initialize document with proper error handling
        try:
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
        except Exception as e:
            logger.error(f"Error creating SimpleDocTemplate: {e}")
            raise

        styles = getSampleStyleSheet()

        # Custom styles with error handling
        try:
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=20,
                alignment=1,
                textColor=colors.darkblue,
                fontName='Helvetica-Bold'
            )
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Heading2'],
                fontSize=16,
                spaceAfter=12,
                textColor=colors.darkgrey,
                fontName='Helvetica-Bold'
            )
        except Exception as e:
            logger.error(f"Error creating paragraph styles: {e}")
            # Fall back to default styles
            title_style = styles['Title']
            subtitle_style = styles['Heading2']

        story = []

        # Title - with safe string handling
        try:
            story.append(Paragraph("Rainwater Harvesting Assessment Report", title_style))
            story.append(Paragraph(f"Assessment ID: {safe_str(assessment.id)}", styles['Normal']))
            story.append(Spacer(1, 0.5*cm))
        except Exception as e:
            logger.error(f"Error adding title: {e}")
            # Add basic title without custom styling
            story.append(Paragraph("Rainwater Harvesting Assessment Report", styles['Title']))
            story.append(Spacer(1, 0.5*cm))

        # Site Details - with safe data handling
        try:
            story.append(Paragraph("Site Details", subtitle_style))
            
            # Safely handle location data
            lat = safe_float(assessment.latitude)
            lon = safe_float(assessment.longitude)
            location = f"{lat:.6f}, {lon:.6f}" if lat != 0.0 and lon != 0.0 else 'N/A'
            
            site_data = [
                ['Parameter', 'Value'],
                ['Site Name', safe_str(assessment.site_name)],
                ['Location', location],
                ['Roof Area', f"{safe_float(assessment.roof_area):.2f} m²"],
                ['Roof Material', safe_str(assessment.roof_material).title()],
                ['Roof Condition', safe_str(assessment.roof_condition).title()],
                ['Soil Type', safe_str(assessment.soil_type).title()],
                ['Annual Rainfall', f"{safe_float(assessment.annual_rainfall):.2f} mm"],
                ['Daily Water Demand', f"{safe_float(assessment.water_demand):.2f} L/day"]
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
        except Exception as e:
            logger.error(f"Error adding site details: {e}")
            story.append(Paragraph("Site Details: Error loading data", styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

        # Assessment Results - with safe data handling
        try:
            story.append(Paragraph("Assessment Results", subtitle_style))
            assessment_data = assessment.assessment_data or {}
            recommendations = assessment.recommendations or {}
            
            harvestable = safe_float(assessment_data.get('harvestable_volume', 0))
            recommendation = safe_str(recommendations.get('recommended_option', 'Unknown')).replace('_', ' ').title()
            storage_req = assessment_data.get('storage_recommendation', {}) or {}
            recharge_req = assessment_data.get('recharge_recommendation', {}) or {}
            recharge_pit = recharge_req.get('recharge_pit', {}) or {}
            recharge_trench = recharge_req.get('recharge_trench', {}) or {}
            
            results_data = [
                ['Parameter', 'Value'],
                ['Harvestable Volume', f"{harvestable:.2f} m³/year"],
                ['Recommended Option', recommendation],
                ['Storage Volume', f"{safe_float(storage_req.get('recommended_volume')):.2f} m³"],
                ['Storage Days', f"{int(safe_float(storage_req.get('storage_days')))} days"],
                ['Recharge Pit Area', f"{safe_float(recharge_pit.get('area')):.2f} m²"],
                ['Recharge Trench', f"{safe_float(recharge_trench.get('length')):.2f}m x {safe_float(recharge_trench.get('width')):.2f}m x {safe_float(recharge_trench.get('depth')):.2f}m"],
                ['Infiltration Rate', f"{safe_float(recharge_req.get('infiltration_rate')):.2f} mm/hr"],
                ['Suitability Score', f"{int(safe_float(recharge_req.get('suitability_score')))}/10"]
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
        except Exception as e:
            logger.error(f"Error adding assessment results: {e}")
            story.append(Paragraph("Assessment Results: Error loading data", styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

        # Cost Analysis - with safe data handling
        try:
            story.append(Paragraph("Cost Analysis", subtitle_style))
            costs = recommendations.get('cost_analysis', {}) or {}
            
            cost_data = [
                ['Component', 'Cost (INR)'],
                ['Storage System', f"₹{safe_float(costs.get('storage_tank_cost')):,.2f}"],
                ['Recharge Structure', f"₹{safe_float(costs.get('recharge_structure_cost')):,.2f}"],
                ['Piping & Fittings', f"₹{safe_float(costs.get('piping_cost')):,.2f}"],
                ['Filtration System', f"₹{safe_float(costs.get('filtration_cost')):,.2f}"],
                ['Labor Cost', f"₹{safe_float(costs.get('labor_cost')):,.2f}"],
                ['Material Contingency', f"₹{safe_float(costs.get('material_contingency')):,.2f}"],
                ['Tax (GST)', f"₹{safe_float(costs.get('tax')):,.2f}"],
                ['Total Cost', f"₹{safe_float(costs.get('total_cost')):,.2f}"]
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
        except Exception as e:
            logger.error(f"Error adding cost analysis: {e}")
            story.append(Paragraph("Cost Analysis: Error loading data", styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

        # Savings Analysis - with safe data handling
        try:
            story.append(Paragraph("Savings Analysis", subtitle_style))
            savings = recommendations.get('savings_analysis', {}) or {}
            payback_period = safe_str(recommendations.get('payback_period'))
            
            savings_data = [
                ['Parameter', 'Value'],
                ['Annual Water Saved', f"{safe_float(savings.get('annual_water_saved')):.2f} m³"],
                ['Annual Cost Savings', f"₹{safe_float(savings.get('annual_cost_savings')):,.2f}"],
                ['Monthly Savings', f"₹{safe_float(savings.get('monthly_savings')):,.2f}"],
                ['Water Tariff Used', f"₹{safe_float(savings.get('water_tariff_used')):.2f}/m³"],
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
        except Exception as e:
            logger.error(f"Error adding savings analysis: {e}")
            story.append(Paragraph("Savings Analysis: Error loading data", styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

        # Bill of Quantities - with safe data handling
        try:
            boq = recommendations.get('bill_of_quantities', {'items': [], 'total_cost': 0}) or {'items': [], 'total_cost': 0}
            if not isinstance(boq, dict):
                logger.warning(f"Invalid bill_of_quantities for assessment {assessment.id}")
                boq = {'items': [], 'total_cost': 0}
                
            items = boq.get('items', [])
            if items and isinstance(items, list):
                story.append(Paragraph("Bill of Quantities", subtitle_style))
                boq_data = [['Item', 'Quantity', 'Rate (INR)', 'Amount (INR)']]
                
                for item in items:
                    if isinstance(item, dict):
                        try:
                            boq_data.append([
                                safe_str(item.get('item')),
                                safe_str(item.get('quantity')),
                                f"₹{safe_float(item.get('rate')):,.2f}",
                                f"₹{safe_float(item.get('amount')):,.2f}"
                            ])
                        except Exception as item_error:
                            logger.warning(f"Error processing BOQ item: {item_error}")
                            continue
                
                boq_data.append(['Total', '', '', f"₹{safe_float(boq.get('total_cost')):,.2f}"])
                
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
        except Exception as e:
            logger.error(f"Error adding bill of quantities: {e}")

        # Safety Checks - with safe data handling
        try:
            safety_checks = recommendations.get('safety_checks', []) or []
            if safety_checks and isinstance(safety_checks, list):
                story.append(Paragraph("Safety and Compliance Checks", subtitle_style))
                for check in safety_checks:
                    try:
                        if isinstance(check, str) and check.strip():
                            check_text = safe_str(check)
                            prefix = check_text.split(':')[0].strip().upper()
                            color = colors.red if 'CRITICAL' in prefix else colors.orange if 'WARNING' in prefix else colors.black
                            
                            check_style = ParagraphStyle(
                                'CheckStyle',
                                parent=styles['Normal'],
                                textColor=color,
                                fontSize=10,
                                leading=12
                            )
                            story.append(Paragraph(check_text, check_style))
                            story.append(Spacer(1, 0.3*cm))
                    except Exception as check_error:
                        logger.warning(f"Error processing safety check: {check_error}")
                        continue
        except Exception as e:
            logger.error(f"Error adding safety checks: {e}")

        # Build PDF with comprehensive error handling
        try:
            logger.info(f"Building PDF for assessment {assessment.id} at {pdf_path}")
            
            # Ensure the story has content
            if not story:
                logger.warning("PDF story is empty, adding basic content")
                story.append(Paragraph("Assessment Report", title_style))
                story.append(Paragraph("No data available", styles['Normal']))
            
            # Build the PDF
            doc.build(story)
            
            # Ensure the file is properly closed and flushed
            doc = None  # Force cleanup of the document object
            
            # Wait a moment to ensure file is fully written
            import time
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error building PDF document: {e}")
            raise ValueError(f"Failed to build PDF document: {e}")

        # Validate the generated file
        if not pdf_path.exists():
            logger.error(f"PDF file was not created at {pdf_path}")
            raise FileNotFoundError(f"PDF file was not created at {pdf_path}")

        file_size = pdf_path.stat().st_size
        if file_size < 100:  # Lowered threshold for minimal PDFs
            logger.error(f"PDF file at {pdf_path} is too small ({file_size} bytes)")
            raise ValueError(f"Generated PDF is too small ({file_size} bytes), likely corrupted")

        # Additional validation - check if file is readable
        try:
            with open(pdf_path, 'rb') as f:
                header = f.read(4)
                if not header.startswith(b'%PDF'):
                    logger.error(f"PDF file at {pdf_path} does not have valid PDF header")
                    raise ValueError("Generated file is not a valid PDF")
        except Exception as e:
            logger.error(f"Error validating PDF file: {e}")
            raise ValueError(f"PDF validation failed: {e}")

        logger.info(f"PDF generated successfully at {pdf_path}, size: {file_size} bytes")
        return str(pdf_path)

    except Exception as e:
        logger.error(f"Error generating PDF for assessment {assessment.id}: {str(e)}", exc_info=True)
        raise