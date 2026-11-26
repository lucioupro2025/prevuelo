import math
import os
import re
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, Point

def kml_color_to_hex(kml_color):
    if not kml_color or len(kml_color.strip()) < 6:
        return None, 0.6
    clean = kml_color.strip()
    if len(clean) == 8:
        a_hex = clean[0:2]
        b_hex = clean[2:4]
        g_hex = clean[4:6]
        r_hex = clean[6:8]
        alpha = int(a_hex, 16) / 255.0
        hex_color = f"#{r_hex}{g_hex}{b_hex}"
        return hex_color, round(alpha, 2)
    elif len(clean) == 6:
        b_hex = clean[0:2]
        g_hex = clean[2:4]
        r_hex = clean[4:6]
        return f"#{r_hex}{g_hex}{b_hex}", 0.7
    return None, 0.6

def parse_kml(kml_source, default_name="test_mapa.kml"):
    if hasattr(kml_source, 'read'):
        raw = kml_source.read()
        if isinstance(raw, bytes):
            text = raw.decode('utf-8', errors='ignore')
        else:
            text = str(raw)
    elif isinstance(kml_source, bytes):
        text = kml_source.decode('utf-8', errors='ignore')
    elif os.path.isfile(str(kml_source)):
        with open(str(kml_source), 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    else:
        text = str(kml_source)

    text = text.strip()
    if text.startswith('<?xml'):
        end_decl = text.find('?>')
        if end_decl != -1:
            text = text[end_decl + 2:].strip()

    root = ET.fromstring(text)

    ns = ''
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'

    doc_name = root.findtext(f'.//{ns}Document/{ns}name') or default_name
    doc_desc = root.findtext(f'.//{ns}Document/{ns}description') or ""

    styles = {}
    for style_el in root.findall(f'.//{ns}Style'):
        sid = style_el.attrib.get('id')
        if not sid:
            continue
        poly_col = style_el.findtext(f'.//{ns}PolyStyle/{ns}color')
        line_col = style_el.findtext(f'.//{ns}LineStyle/{ns}color')
        hex_c, alpha = kml_color_to_hex(poly_col)
        line_hex, _ = kml_color_to_hex(line_col)
        styles['#' + sid] = {
            'color': hex_c,
            'alpha': alpha,
            'line_color': line_hex
        }

    placemarks = root.findall(f'.//{ns}Placemark')
    ground_overlays = root.findall(f'.//{ns}GroundOverlay')

    parsed_polygons = []
    parsed_points = []
    parsed_overlays = []

    palette = ['#27ae60', '#f39c12', '#2980b9', '#8e44ad', '#d35400', '#16a085']

    for pm in placemarks:
        name = pm.findtext(f'{ns}name', '').strip()
        desc = pm.findtext(f'{ns}description', '').strip()
        style_url = pm.findtext(f'{ns}styleUrl', '').strip()
        style_info = styles.get(style_url, {})
        ext_data = {}
        for data_el in pm.findall(f'.//{ns}ExtendedData/{ns}Data'):
            att_name = data_el.attrib.get('name')
            val = data_el.findtext(f'{ns}value')
            if att_name and val:
                ext_data[att_name.lower()] = val.strip()
        poly_el = pm.find(f'.//{ns}Polygon')
        if poly_el is not None:
            coord_str = poly_el.findtext(f'.//{ns}outerBoundaryIs/{ns}LinearRing/{ns}coordinates')
            if coord_str:
                raw_coords = []
                for token in coord_str.strip().split():
                    parts = token.split(',')
                    if len(parts) >= 2:
                        try:
                            raw_coords.append((float(parts[0]), float(parts[1])))
                        except ValueError:
                            pass
                if len(raw_coords) >= 3:
                    parsed_polygons.append({
                        'name': name or f"Ambiente {len(parsed_polygons)+1}",
                        'desc': desc,
                        'coords': raw_coords,
                        'ext_data': ext_data,
                        'style': style_info
                    })
        pt_el = pm.find(f'.//{ns}Point')
        if pt_el is not None:
            coord_str = pt_el.findtext(f'{ns}coordinates')
            if coord_str:
                parts = coord_str.strip().split(',')
                if len(parts) >= 2:
                    try:
                        parsed_points.append({
                            'name': name or f"Punto {len(parsed_points)+1}",
                            'desc': desc,
                            'coord': (float(parts[0]), float(parts[1])),
                            'ext_data': ext_data,
                            'style': style_info
                        })
                    except ValueError:
                        pass

    for go in ground_overlays:
        icon = go.find(f'{ns}Icon/{ns}href')
        if icon is not None and icon.text:
            href = icon.text.strip()
        else:
            continue
        lon_box = go.find(f'{ns}LatLonBox')
        if lon_box is None:
            continue
        north = float(lon_box.findtext(f'{ns}north'))
        south = float(lon_box.findtext(f'{ns}south'))
        east = float(lon_box.findtext(f'{ns}east'))
        west = float(lon_box.findtext(f'{ns}west'))
        rotation = float(lon_box.findtext(f'{ns}rotation') or 0)
        parsed_overlays.append({
            'href': href,
            'north': north,
            'south': south,
            'east': east,
            'west': west,
            'rotation': rotation
        })

    all_lons = []
    all_lats = []
    for p in parsed_polygons:
        for c in p['coords']:
            all_lons.append(c[0])
            all_lats.append(c[1])
    for pt in parsed_points:
        all_lons.append(pt['coord'][0])
        all_lats.append(pt['coord'][1])

    if not all_lons:
        raise ValueError("El archivo KML no contiene geometrías válidas (polígonos o puntos).")

    min_lon = min(all_lons)
    max_lon = max(all_lons)
    min_lat = min(all_lats)
    max_lat = max(all_lats)

    lat0 = (min_lat + max_lat) / 2.0
    lat0_rad = math.radians(lat0)

    m_per_lat = 111132.92 - 559.82 * math.cos(2 * lat0_rad) + 1.175 * math.cos(4 * lat0_rad)
    m_per_lon = 111412.84 * math.cos(lat0_rad) - 93.5 * math.cos(3 * lat0_rad)

    MARGIN = 25.0

    def to_metric(lon, lat):
        x = (lon - min_lon) * m_per_lon + MARGIN
        y = (lat - min_lat) * m_per_lat + MARGIN
        return round(x, 2), round(y, 2)

    zones = []
    total_area_m2 = 0.0

    for idx, p in enumerate(parsed_polygons):
        local_coords = [to_metric(c[0], c[1]) for c in p['coords']]
        poly = Polygon(local_coords)
        area_m2 = abs(poly.area)
        total_area_m2 += area_m2
        ha = round(area_m2 / 10000.0, 2)
        dose = 15.0
        ext = p['ext_data']
        for k in ['dosis_l_ha', 'dosis', 'rate', 'target_dose', 'dose']:
            if k in ext:
                try:
                    dose = float(ext[k])
                    break
                except ValueError:
                    pass
        else:
            match = re.search(r'(\d+(?:\.\d+)?)\s*L/ha', p['desc'], re.IGNORECASE)
            if match:
                try:
                    dose = float(match.group(1))
                except ValueError:
                    pass
        color = p['style'].get('color') or palette[idx % len(palette)]
        alpha = p['style'].get('alpha') or 0.65
        zones.append({
            'name': p['name'],
            'description': p['desc'],
            'center_x': round(poly.centroid.x, 2),
            'center_y': round(poly.centroid.y, 2),
            'area_m2': round(area_m2, 1),
            'hectares': ha,
            'target_dose_l_ha': dose,
            'color': color,
            'fill_opacity': alpha,
            'coordinates': local_coords,
            'gps_coordinates': p['coords'],
            'type': 'variable_dose'
        })

    home_point = None
    obstacles = []

    for pt in parsed_points:
        name_lower = pt['name'].lower()
        lx, ly = to_metric(pt['coord'][0], pt['coord'][1])
        if any(k in name_lower for k in ['home', 'base', 'despegue', 'helipad', 'salida', 'trailer']):
            home_point = {
                'x': lx,
                'y': ly,
                'label': pt['name'] or 'Home Base',
                'description': pt['desc'],
                'gps': [round(pt['coord'][0], 6), round(pt['coord'][1], 6)]
            }
        else:
            obs_type = 'pole' if any(k in name_lower for k in ['poste', 'luz', 'cable', 'pole', 'linea', 'columna']) else 'tree'
            radius = 3.5 if obs_type == 'pole' else 5.0
            height = 10.0 if obs_type == 'pole' else 8.5
            if 'radius_m' in pt['ext_data']:
                try: radius = float(pt['ext_data']['radius_m'])
                except ValueError: pass
            if 'height_m' in pt['ext_data']:
                try: height = float(pt['ext_data']['height_m'])
                except ValueError: pass
            obstacles.append({
                'id': re.sub(r'[^a-zA-Z0-9_]', '_', pt['name'].lower()),
                'label': pt['name'],
                'description': pt['desc'],
                'type': obs_type,
                'x': lx,
                'y': ly,
                'radius': radius,
                'height': height,
                'gps': [round(pt['coord'][0], 6), round(pt['coord'][1], 6)]
            })

    if not home_point:
        home_point = {
            'x': MARGIN,
            'y': MARGIN,
            'label': 'Home Base (Margen)',
            'description': 'Punto de despegue en cabecera',
            'gps': [round(min_lon, 6), round(min_lat, 6)]
        }

    field_width = round((max_lon - min_lon) * m_per_lon + MARGIN * 2, 1)
    field_height = round((max_lat - min_lat) * m_per_lat + MARGIN * 2, 1)

    return {
        'status': 'success',
        'doc_name': doc_name,
        'description': doc_desc,
        'width': field_width,
        'height': field_height,
        'size': {'width': field_width, 'height': field_height},
        'hectares': round(total_area_m2 / 10000.0, 2),
        'total_area_m2': round(total_area_m2, 1),
        'zones': zones,
        'obstacles': obstacles,
        'home_point': home_point,
        'overlays': parsed_overlays,
        'gps_bounds': {
            'min_lon': round(min_lon, 6),
            'max_lon': round(max_lon, 6),
            'min_lat': round(min_lat, 6),
            'max_lat': round(max_lat, 6)
        }
    }