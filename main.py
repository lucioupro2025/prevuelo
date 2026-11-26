"""
Reporte Predictivo de Rentabilidad Agricola
===========================================

Servidor Flask que analiza un lote real en formato KML y calcula un informe
de rentabilidad pre-aplicacion: superficie, caldo necesario, tiempo de labor,
costo operativo, ahorro estimado, ROI y riesgo de deriva.

No incluye simulacion de vuelo ni control de aeronave.
"""

import io
import math
import os
import re
from datetime import datetime
from xml.sax.saxutils import escape

from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image

from core.kml_parser import parse_kml

import os
# ... (resto de los imports)

app = Flask(__name__)
CORS(app)

# Puerto dinámico para Render, por defecto 8080
PORT = int(os.environ.get("PORT", 8080))
DEBUG = False # Siempre false en produccion

DEFAULT_PARAMETERS = {
    "price_per_hectare": 200.0,   # USD por hectarea
    "savings_percent": 15.0,      # % de ahorro de caldo
    "application_speed": 6.5,     # m/s
    "swath_width": 8.0,           # m entre lineas de pasada
    "wind_speed": 4.0,            # m/s
}

DEFAULT_DOSE = 15.0               # L/ha si el KML no declara dosis
DEFAULT_SWATH = 8.0               # m si el KML no declara ancho de faja

report_state = {
    "field": {},
    "parameters": dict(DEFAULT_PARAMETERS),
    "predictive_report": None,
    "source_file": "test_mapa.kml",
}


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def _as_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, low, high):
    return max(low, min(high, value))


def _slug(text):
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", (text or "lote")).strip("_")
    return clean or "lote"


# ----------------------------------------------------------------------
# Motor de calculo
# ----------------------------------------------------------------------
def calcular_informe_predictivo(parsed_kml, parameters, wind_speed):
    """
    Calcula el informe de rentabilidad y la configuracion ideal de aplicacion.

    - El caldo total se obtiene sumando hectarea por dosis de cada ambiente.
    - El costo operativo usa el precio por hectarea configurado.
    - El ahorro aplica el porcentaje de ahorro sobre el caldo total.
    - El ROI relaciona el ahorro economico con el costo operativo.
    """
    hectares = max(0.0, _as_float(parsed_kml.get("hectares"), 0.0))
    zones = parsed_kml.get("zones") or []
    obstacles = parsed_kml.get("obstacles") or []

    price = max(0.01, _as_float(parameters.get("price_per_hectare"), 200.0))
    savings_pct = _clamp(_as_float(parameters.get("savings_percent"), 15.0), 0.0, 100.0)
    speed = max(0.5, _as_float(parameters.get("application_speed"), 6.5))
    swath = _clamp(_as_float(parameters.get("swath_width"), DEFAULT_SWATH), 4.0, 14.0)
    wind = max(0.0, _as_float(wind_speed, 4.0))

    total_liters = 0.0
    total_area_m2 = 0.0
    zone_breakdown = []

    for zone in zones:
        zone_ha = max(0.0, _as_float(zone.get("hectares"), 0.0))
        zone_dose = max(0.0, _as_float(zone.get("target_dose_l_ha"), DEFAULT_DOSE))
        zone_liters = zone_ha * zone_dose

        total_liters += zone_liters
        total_area_m2 += zone_ha * 10000.0
        zone_breakdown.append({
            "name": zone.get("name") or "Ambiente",
            "hectares": round(zone_ha, 2),
            "target_dose": round(zone_dose, 2),
            "liters": round(zone_liters, 1),
            "cost_usd": round(zone_ha * price, 2),
            "color": zone.get("color") or "#4cc38a",
        })

    if not zone_breakdown:
        total_liters = hectares * DEFAULT_DOSE
        total_area_m2 = hectares * 10000.0
        zone_breakdown.append({
            "name": "Lote completo",
            "hectares": round(hectares, 2),
            "target_dose": DEFAULT_DOSE,
            "liters": round(total_liters, 1),
            "cost_usd": round(hectares * price, 2),
            "color": "#4cc38a",
        })

    average_dose = (total_liters / hectares) if hectares > 0 else 0.0
    cost_total = hectares * price
    savings_liters = total_liters * (savings_pct / 100.0)
    price_per_liter = (price / average_dose) if average_dose > 0 else 0.0
    cost_savings = savings_liters * price_per_liter
    roi_percent = (cost_savings / cost_total * 100.0) if cost_total > 0 else 0.0
    drift_estimate = _clamp(wind * 5.0, 5.0, 30.0)

    # Dimensiones reales del lote (el parser agrega 25 m de margen por lado).
    field_width = max(0.0, _as_float(parsed_kml.get("width"), 0.0) - 50.0)
    field_height = max(0.0, _as_float(parsed_kml.get("height"), 0.0) - 50.0)

    passes = 0
    distance_km = 0.0
    if field_width > 0 and field_height > 0:
        short_side = min(field_width, field_height)
        long_side = max(field_width, field_height)
        passes = int(math.ceil(short_side / swath))
        distance_km = passes * long_side / 1000.0
        application_time_hours = distance_km * 1000.0 / (speed * 3600.0)
    else:
        application_time_hours = total_area_m2 / max(0.1, swath * speed) / 3600.0

    # Configuracion ideal de aplicacion segun viento y dosis.
    if wind <= 4:
        wind_status, wind_label = "optimo", "Optimo para aplicar"
    elif wind <= 6:
        wind_status, wind_label = "aceptable", "Aceptable con control de deriva"
    elif wind <= 8:
        wind_status, wind_label = "precaucion", "Precaucion: viento alto"
    else:
        wind_status, wind_label = "no_aplicar", "No aplicar con este viento"

    if wind <= 3:
        recommended_speed = 7.0
    elif wind <= 5:
        recommended_speed = 6.5
    elif wind <= 7:
        recommended_speed = 6.0
    elif wind <= 8:
        recommended_speed = 5.5
    else:
        recommended_speed = 0.0

    if average_dose >= 22:
        recommended_swath = 7.0
    elif average_dose >= 18:
        recommended_swath = 8.0
    elif average_dose >= 14:
        recommended_swath = 9.0
    else:
        recommended_swath = 10.0

    altitude = 3.0
    if recommended_swath <= 7:
        altitude = 2.5
    elif recommended_swath >= 10:
        altitude = 3.5
    if wind > 6:
        altitude = max(2.0, altitude - 0.5)

    flow_rate = average_dose * swath * speed * 0.006
    tank_refills = int(math.ceil(total_liters / 40.0)) if total_liters > 0 else 0
    battery_cycles = int(math.ceil(application_time_hours * 60.0 / 12.0)) if application_time_hours > 0 else 0

    notes = []
    if wind > 8:
        notes.append("Viento por encima del limite operativo de 8 m/s: suspender la aplicacion.")
    elif wind > 5:
        notes.append("Reducir la altura de aplicacion y priorizar horarios de bajo viento.")
    if drift_estimate > 20:
        notes.append("Deriva estimada alta: usar boquillas antideriva y verificar la direccion del viento.")
    if tank_refills > 0:
        notes.append(f"Prever {tank_refills} recargas de tanque de 40 L.")
    if len(zone_breakdown) > 1:
        notes.append("El lote tiene dosis variables por ambiente: respetar la prescripcion de cada zona.")
    if flow_rate > 24:
        notes.append("El caudal requerido supera el maximo de la maquina: reducir velocidad o dosis.")

    return {
        "hectares": round(hectares, 2),
        "target_dose": round(average_dose, 2),
        "total_liters": round(total_liters, 1),
        "application_time_hours": round(application_time_hours, 2),
        "swath_width": round(swath, 2),
        "cost_total_usd": round(cost_total, 2),
        "savings_liters": round(savings_liters, 1),
        "cost_savings_usd": round(cost_savings, 2),
        "roi_percent": round(roi_percent, 1),
        "drift_estimate_percent": round(drift_estimate, 1),
        "zone_count": len(zones),
        "obstacle_count": len(obstacles),
        "zones": zone_breakdown,
        "price_per_hectare": round(price, 2),
        "savings_percent": round(savings_pct, 1),
        "wind_speed": round(wind, 1),
        "application_speed": round(speed, 2),
        "field_width_m": round(field_width, 1),
        "field_height_m": round(field_height, 1),
        "recommended": {
            "altitude_m": round(altitude, 1),
            "speed_m_s": round(recommended_speed, 1),
            "swath_width_m": round(recommended_swath, 1),
            "flow_rate_l_min": round(flow_rate, 1),
            "passes": passes,
            "distance_km": round(distance_km, 2),
            "tank_refills": tank_refills,
            "battery_cycles": battery_cycles,
            "wind_status": wind_status,
            "wind_label": wind_label,
            "notes": notes,
        },
    }


def build_payload(message=None):
    field = report_state["field"]
    return {
        "status": "success",
        "message": message,
        "doc_name": field.get("doc_name", ""),
        "description": field.get("description", ""),
        "field": field,
        "parameters": report_state["parameters"],
        "predictive_report": report_state["predictive_report"],
        "report": report_state["predictive_report"],
        "source_file": report_state["source_file"],
    }


def load_kml(kml_source, filename):
    """Parsea el KML, actualiza el estado y recalcula el informe."""
    parsed = parse_kml(kml_source, default_name=filename)
    report_state["field"] = {
        "doc_name": parsed["doc_name"],
        "description": parsed["description"],
        "hectares": parsed["hectares"],
        "width": parsed["width"],
        "height": parsed["height"],
        "size": parsed["size"],
        "total_area_m2": parsed["total_area_m2"],
        "zones": parsed["zones"],
        "obstacles": parsed["obstacles"],
        "home_point": parsed["home_point"],
        "gps_bounds": parsed["gps_bounds"],
        "overlays": parsed.get("overlays", []),
    }
    report_state["source_file"] = filename
    report_state["predictive_report"] = calcular_informe_predictivo(
        parsed,
        report_state["parameters"],
        report_state["parameters"]["wind_speed"],
    )
    return build_payload()


def recompute_report():
    report_state["predictive_report"] = calcular_informe_predictivo(
        report_state["field"],
        report_state["parameters"],
        report_state["parameters"]["wind_speed"],
    )
    return build_payload()


# ----------------------------------------------------------------------
# Rutas
# ----------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/report", methods=["GET"])
def get_report():
    """Informe actual: lote, parametros y metricas de rentabilidad."""
    return jsonify(build_payload())


@app.route("/api/status", methods=["GET"])
def get_status():
    """Alias de compatibilidad de /api/report."""
    return jsonify(build_payload())


@app.route("/api/import_kml", methods=["POST"])
def import_kml():
    """Importa un KML (multipart, campo kml_file) y devuelve el informe."""
    file = request.files.get("kml_file")
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "No se recibio ningun archivo KML."}), 400

    try:
        payload = load_kml(file, file.filename)
        payload["message"] = (
            f"KML '{payload['doc_name']}' analizado: "
            f"{payload['report']['hectares']} ha, "
            f"{payload['report']['zone_count']} ambientes."
        )
        return jsonify(payload)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"No se pudo interpretar el KML: {exc}",
        }), 400


@app.route("/api/load_default_kml", methods=["POST"])
def load_default_kml():
    """Recarga el lote de ejemplo test_mapa.kml."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_mapa.kml")
    if not os.path.isfile(path):
        return jsonify({"status": "error", "message": "No se encontro test_mapa.kml."}), 400

    try:
        payload = load_kml(path, "test_mapa.kml")
        payload["message"] = "Lote de ejemplo test_mapa.kml cargado."
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Error al cargar el lote: {exc}"}), 400


@app.route("/api/report/config", methods=["POST"])
def configure_report():
    """Actualiza precio, ahorro, velocidad y viento; recalcula el informe."""
    if not report_state["field"]:
        return jsonify({"status": "error", "message": "Cargue un KML antes de configurar."}), 400

    data = request.get_json(silent=True) or {}

    if "price_per_hectare" in data:
        price = _as_float(data.get("price_per_hectare"), None)
        if price is None or price <= 0 or price > 100000:
            return jsonify({"status": "error", "message": "Precio por hectarea invalido."}), 400
        report_state["parameters"]["price_per_hectare"] = round(price, 2)

    if "savings_percent" in data:
        savings = _as_float(data.get("savings_percent"), None)
        if savings is None or savings < 0 or savings > 100:
            return jsonify({"status": "error", "message": "Porcentaje de ahorro invalido."}), 400
        report_state["parameters"]["savings_percent"] = round(savings, 1)

    if "application_speed" in data:
        speed = _as_float(data.get("application_speed"), None)
        if speed is None or speed < 0.5 or speed > 20:
            return jsonify({"status": "error", "message": "Velocidad de labor invalida."}), 400
        report_state["parameters"]["application_speed"] = round(speed, 2)

    if "swath_width" in data:
        swath = _as_float(data.get("swath_width"), None)
        if swath is None or swath < 4 or swath > 14:
            return jsonify({"status": "error", "message": "Separacion entre pasadas invalida."}), 400
        report_state["parameters"]["swath_width"] = round(swath, 2)

    if "wind_speed" in data:
        wind = _as_float(data.get("wind_speed"), None)
        if wind is None or wind < 0 or wind > 15:
            return jsonify({"status": "error", "message": "Velocidad de viento invalida."}), 400
        report_state["parameters"]["wind_speed"] = round(wind, 1)

    payload = recompute_report()
    payload["message"] = "Parametros actualizados y reporte recalculado."
    return jsonify(payload)


@app.route("/api/report_pdf", methods=["GET"])
def report_pdf():
    """Genera y descarga el informe PDF del lote actual."""
    report = report_state.get("predictive_report")
    field = report_state.get("field") or {}
    if not report or not field:
        return jsonify({"status": "error", "message": "No hay informe disponible. Cargue un KML."}), 400

    params = report_state["parameters"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        title="Reporte Predictivo de Rentabilidad",
    )
    styles = getSampleStyleSheet()
    elements = []
    
    # Agregar Logo
    if os.path.exists("static/logo-prevuelo.png"):
        elements.append(Image("static/logo-prevuelo.png", width=40*mm, height=40*mm))
        elements.append(Spacer(1, 10))

    title_style = styles["Title"]
    title_style.textColor = colors.HexColor("#1F3B2C")
    title_style.fontSize = 20
    title_style.spaceAfter = 4

    elements.append(Paragraph("Reporte Predictivo de Rentabilidad", title_style))
    elements.append(Paragraph(
        f"<font color='#5B6B63'>{escape(field.get('doc_name', 'Lote sin nombre'))} &nbsp;|&nbsp; "
        f"{report['hectares']} ha &nbsp;|&nbsp; {datetime.now().strftime('%d/%m/%Y %H:%M')}</font>",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 10))

    description = field.get("description") or ""
    if description:
        elements.append(Paragraph(
            f"<font size=8.5 color='#5B6B63'>{escape(description[:400])}</font>",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 10))

    summary = [
        ["Indicador", "Valor"],
        ["Superficie del lote", f"{report['hectares']} ha"],
        ["Dosis promedio", f"{report['target_dose']} L/ha"],
        ["Caldo total requerido", f"{report['total_liters']} L"],
        ["Tiempo de labor estimado", f"{report['application_time_hours']} h"],
        ["Ancho de faja", f"{report['swath_width']} m"],
        ["Costo operativo total", f"USD {report['cost_total_usd']}"],
        [f"Ahorro de caldo ({report['savings_percent']}%)", f"{report['savings_liters']} L"],
        ["Ahorro economico estimado", f"USD {report['cost_savings_usd']}"],
        ["ROI / Retorno de inversion", f"{report['roi_percent']} %"],
        ["Riesgo de deriva por viento", f"{report['drift_estimate_percent']} %"],
        ["Ambientes / obstaculos", f"{report['zone_count']} / {report['obstacle_count']}"],
    ]
    summary_table = Table(summary, colWidths=[100 * mm, 62 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3B2C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9C7BF")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7F4")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    recommended = report.get("recommended") or {}
    if recommended:
        elements.append(Paragraph(
            "<font color='#1F3B2C' size=11><b>Configuracion ideal de aplicacion</b></font>",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 6))
        rec_rows = [
            ["Variable", "Valor recomendado"],
            ["Altitud de aplicacion", f"{recommended.get('altitude_m', 0)} m"],
            ["Velocidad de avance", f"{recommended.get('speed_m_s', 0)} m/s"],
            ["Separacion entre pasadas", f"{recommended.get('swath_width_m', 0)} m"],
            ["Caudal requerido", f"{recommended.get('flow_rate_l_min', 0)} L/min"],
            ["Cantidad de pasadas", f"{recommended.get('passes', 0)}"],
            ["Distancia estimada", f"{recommended.get('distance_km', 0)} km"],
            ["Recargas de tanque (40 L)", f"{recommended.get('tank_refills', 0)}"],
            ["Baterias estimadas (12 min)", f"{recommended.get('battery_cycles', 0)}"],
            ["Estado del viento", recommended.get("wind_label", "-")],
        ]
        rec_table = Table(rec_rows, colWidths=[100 * mm, 62 * mm])
        rec_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E5C45")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9C7BF")),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7F4")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(rec_table)
        elements.append(Spacer(1, 8))

        for note in recommended.get("notes", []):
            elements.append(Paragraph(
                f"<font size=8.5 color='#5B6B63'>- {escape(note)}</font>",
                styles["Normal"],
            ))
        elements.append(Spacer(1, 14))

    if report.get("zones"):
        elements.append(Paragraph(
            "<font color='#1F3B2C' size=11><b>Detalle por ambiente</b></font>",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 6))
        zone_rows = [["Ambiente", "Superficie", "Dosis", "Caldo", "Costo"]]
        for zone in report["zones"]:
            zone_rows.append([
                zone["name"],
                f"{zone['hectares']} ha",
                f"{zone['target_dose']} L/ha",
                f"{zone['liters']} L",
                f"USD {zone['cost_usd']}",
            ])
        zone_table = Table(zone_rows, colWidths=[56 * mm, 26 * mm, 26 * mm, 26 * mm, 28 * mm])
        zone_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E5C45")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9C7BF")),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7F4")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(zone_table)
        elements.append(Spacer(1, 14))

    elements.append(Paragraph(
        "<font size=8 color='#5B6B63'>Parametros: "
        f"USD {params['price_per_hectare']}/ha &nbsp;|&nbsp; "
        f"ahorro {params['savings_percent']}% &nbsp;|&nbsp; "
        f"velocidad {params['application_speed']} m/s &nbsp;|&nbsp; "
        f"pasadas {params.get('swath_width', 8)} m &nbsp;|&nbsp; "
        f"viento {params['wind_speed']} m/s</font>",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "<font size=8 color='#8A9A91'>Generado por el Reporte Predictivo de Rentabilidad Agricola. "
        "Los valores son estimaciones pre-aplicacion y no reemplazan una prescripcion agronomica.</font>",
        styles["Normal"],
    ))
    
    # Agregar Footer con datos de la agencia
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "<hr color='#B9C7BF' size=0.5>",
        styles["Normal"]
    ))
    elements.append(Paragraph(
        "Desarrollado por <b>guruweb.com.ar</b> | WhatsApp: +54 9 2657 284903",
        styles["Normal"]
    ))

    doc.build(elements)
    buf.seek(0)
    filename = f"Reporte_Rentabilidad_{_slug(field.get('doc_name'))}.pdf"
    return send_file(buf, as_attachment=True, download_name=filename, mimetype="application/pdf")


# ----------------------------------------------------------------------
# Carga inicial del lote de ejemplo
# ----------------------------------------------------------------------
def _bootstrap():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_mapa.kml")
    if not os.path.isfile(path):
        print("Aviso: no se encontro test_mapa.kml; cargue un KML desde la interfaz.")
        return
    try:
        load_kml(path, "test_mapa.kml")
        report = report_state["predictive_report"]
        print(
            f"Lote inicial cargado: {report['hectares']} ha, "
            f"{report['total_liters']} L, ROI {report['roi_percent']}%."
        )
    except Exception as exc:
        print(f"Aviso: no se pudo cargar test_mapa.kml: {exc}")


_bootstrap()


if __name__ == "__main__":
    print(f"Reporte Predictivo de Rentabilidad en http://localhost:{PORT}")
    app.run(port=PORT, debug=DEBUG)
