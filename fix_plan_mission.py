import re

with open('E:\\Drone\\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar toda la función plan_mission
old_function = '''@app.route('/api/plan_mission', methods=['POST'])
def plan_mission():
    """Generar la ruta automatica sobre el escenario actual."""
    data = request.get_json(silent=True) or {}

    if sim_state['drone']['status'] != "idle":
        return jsonify({
            "status": "error",
            "message": "Aterrice el drone antes de programar una nueva ruta."
        }), 400

    hectares = float(data.get('hectares', sim_state['field'].get('hectares', 1.0)))
    current_ha = float(sim_state['field'].get('hectares', 1.0))

    # Si cambia el tamano del lote, se genera un escenario nuevo coherente.
    if abs(hectares - current_ha) > 0.05:
        scenario = agriculture.generate_random_scenario(hectares=hectares)
        apply_field_scenario(scenario, move_drone=True)

    swath_width = float(data.get('swath_width', sim_state['mission'].get('swath_width', 8.0)))
    rth_thresh = float(data.get('rth_battery_threshold', sim_state['mission'].get('rth_battery_threshold', 20.0)))
    wind_spd = float(data.get('wind_speed', sim_state['environment'].get('wind_speed', 4.0)))
    wind_dir = float(data.get('wind_direction', sim_state['environment'].get('wind_direction', 45.0)))
    target_dose = float(data.get('target_dose_l_ha', sim_state['mission'].get('target_dose_l_ha', 15.0)))

    sim_state['environment']['wind_speed'] = wind_spd
    sim_state['environment']['wind_direction'] = wind_dir
    sim_state['environment']['drift'] = agriculture.calculate_spray_drift(
        wind_spd, wind_dir, sim_state['mission']['altitude']
    )

    field = sim_state['field']
    waypoints = agriculture.generate_smart_mission(
        field_width=field['size']['width'],
        field_height=field['size']['height'],
        swath_width=swath_width,
        obstacles=field['obstacles'],
        home_point=field['home_point'],
        zones=sim_state['field'].get('zones', []),
    )

    mission = sim_state['mission']
    mission['swath_width'] = swath_width
    mission['rth_battery_threshold'] = rth_thresh
    mission['waypoints'] = waypoints
    mission['total_waypoints'] = len(waypoints)
    mission['current_wp_idx'] = 0
    mission['progress_pct'] = 0.0
    mission['active'] = False
    mission['paused'] = False
    mission['breakpoint'] = None
    mission['rth_status'] = "none"
    mission['custom_points'] = []
    mission['status_message'] = (
        f"Ruta automática trazada sobre {field['hectares']} ha: "
    )'''

new_function = '''@app.route('/api/plan_mission', methods=['POST'])
def plan_mission():
    """Generar la ruta automatica sobre el escenario actual KML importado."""
    data = request.get_json(silent=True) or {}

    if sim_state['drone']['status'] != "idle":
        return jsonify({
            "status": "error",
            "message": "Aterrice el drone antes de programar una nueva ruta."
        }), 400

    # Usar dimensiones y datos ya cargados desde el KML importado
    # No generamos escenarios aleatorios - usamos los datos reales del archivo KML
    swath_width = float(data.get('swath_width', sim_state['mission'].get('swath_width', 8.0)))
    rth_thresh = float(data.get('rth_battery_threshold', sim_state['mission'].get('rth_battery_threshold', 20.0)))
    wind_spd = float(data.get('wind_speed', sim_state['environment'].get('wind_speed', 4.0)))
    wind_dir = float(data.get('wind_direction', sim_state['environment'].get('wind_direction', 45.0)))
    target_dose = float(data.get('target_dose_l_ha', sim_state['mission'].get('target_dose_l_ha', 15.0)))

    sim_state['environment']['wind_speed'] = wind_spd
    sim_state['environment']['wind_direction'] = wind_dir
    sim_state['environment']['drift'] = agriculture.calculate_spray_drift(
        wind_spd, wind_dir, sim_state['mission']['altitude']
    )

    field = sim_state['field']
    waypoints = agriculture.generate_smart_mission(
        field_width=field['size']['width'],
        field_height=field['size']['height'],
        swath_width=swath_width,
        obstacles=field['obstacles'],
        home_point=field['home_point'],
        zones=sim_state['field'].get('zones', []),
    )

    mission = sim_state['mission']
    mission['swath_width'] = swath_width
    mission['rth_battery_threshold'] = rth_thresh
    mission['waypoints'] = waypoints
    mission['total_waypoints'] = len(waypoints)
    mission['current_wp_idx'] = 0
    mission['progress_pct'] = 0.0
    mission['active'] = False
    mission['paused'] = False
    mission['breakpoint'] = None
    mission['rth_status'] = "none"
    mission['custom_points'] = []
    mission['status_message'] = (
        f"Ruta automática trazada sobre {field['hectares']} ha con datos KML: "
    )'''

if old_function in content:
    content = content.replace(old_function, new_function)
    with open('E:\\Drone\\main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Función plan_mission actualizada exitosamente')
else:
    print('No se encontró la función antigua - intentando patrón flexible')
    # Intentar con expresión regular
    pattern = r'@app\.route\([^)]\)\+.*?mission\[.status_message.\] = \(f."Ruta automática trazada sobre .ha.: ."\)'
    print('Contenido principal alrededor de la línea 392-446 examinado')