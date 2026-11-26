import os
import math
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib.units import mm
import random

def generate_agri_report(kml_data, output_path="agricultural_report.pdf"):
    # Mock data processing (replace with real KML parsing)
    field_data = {
        "hectares": 30.87,
        "obstacles": 12,
        "wind_speed": 4.5,
        "target_dose": 15.0,
        "product_price": 250.0,  # USD per hectare
        "swath_width": 8.0,
        "drone_capacity": 40.0,  # liters
        "application_speed": 6.5,  # m/s
    }

    # Calculate metrics
    field_data["total_area_m2"] = field_data["hectares"] * 10000
    field_data["required_liters"] = field_data["hectares"] * field_data["target_dose"]
    field_data["number_of_passes"] = math.ceil(field_data["hectares"] * 10000 / (field_data["swath_width"] * 10))
    field_data["flight_time_hours"] = (field_data["number_of_passes"] * field_data["total_area_m2"] / (field_data["swath_width"] * 10 * field_data["application_speed"])) / 3600
    field_data["total_cost"] = field_data["hectares"] * field_data["product_price"]
    field_data["drift_estimate"] = min(100, max(5, 100 - (12 - field_data["wind_speed"])))  # Mock formula
    field_data["product_savings"] = field_data["required_liters"] * 0.15  # Assuming 15% savings via precision
    field_data["roi"] = (field_data["product_savings"] / field_data["total_cost"]) * 100

    # Create PDF
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title = Paragraph("<font size=18 color='green'>Reporte Predictivo de Aplicación Agrícola</font>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Field Summary Table
    field_summary_data = [
        ["Superficie Total", f"{field_data['hectares']:.2f} ha"],
        ["Obstáculos Detectados", field_data["obstacles"]],
        ["Velocidad del Viento", f"{field_data['wind_speed']} m/s"],
        ["Dosis Objetivo", f"{field_data['target_dose']} L/ha"],
        ["Ancho de Faja", f"{field_data['swath_width']} m"],
    ]
    field_summary_table = Table(field_summary_data)
    field_summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6F4E6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2C5E1A')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#2C5E1A')),
    ]))
    elements.append(field_summary_table)
    elements.append(Spacer(1, 12))

    # Operational Metrics
    op_data = [
        ["Pasadas Requeridas", field_data["number_of_passes"]],
        ["Tiempo de Vuelo Estimado", f"{field_data['flight_time_hours']:.1f} horas"],
        ["Litros de Producto Necesarios", f"{field_data['required_liters']:.1f} L"],
        ["Costo Total de Aplicación", f"USD {field_data['total_cost']:.2f}"],
    ]
    op_table = Table(op_data)
    op_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6F0FF')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1A4E8E')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1A4E8E')),
    ]))
    elements.append(Paragraph("<font size=12 color='#1A4E8E'>Métricas Operativas</font>", styles["Heading2"]))
    elements.append(op_table)
    elements.append(Spacer(1, 12))

    # Savings and ROI
    savings_data = [
        ["Estimación de Deriva", f"{field_data['drift_estimate']}%"],
        ["Ahorro en Producto", f"{field_data['product_savings']:.1f} L"],
        ["Retorno de Inversión (ROI)", f"{field_data['roi']:.1f}%"],
    ]
    savings_table = Table(savings_data)
    savings_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFE6E6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#8B0000')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.mistyrose),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#8B0000')),
    ]))
    elements.append(Paragraph("<font size=12 color='#8B0000'>Ahorros y Rentabilidad</font>", styles["Heading2"]))
    elements.append(savings_table)

    # Build PDF
    doc.build(elements)
    print(f"Reporte generado: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    # Ejemplo de uso
    generate_agri_report("dummy_kml_data.kml", "Reporte_Predictivo_Lote_SanLuis.pdf")
