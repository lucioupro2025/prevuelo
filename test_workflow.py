import requests

# Paso 1: Importar KML
url = 'http://localhost:8080/api/import_kml'
with open('E:\\Drone\\test_mapa.kml', 'rb') as f:
    files = {'kml_file': ('test_mapa.kml', f, 'application/xml')}
    response = requests.post(url, files=files)

print('=== PASO 1: Importar KML ===')
print('Status code:', response.status_code)
resp = response.json()
print('Message:', resp.get('message'))
print('Status:', resp.get('status'))
print('Zones loaded:', len(resp.get('zones', [])))
print('Obstacles loaded:', len(resp.get('obstacles', [])))
print('Home point:', resp.get('home_point'))
print('Field dims:', resp.get('field_dimensions'))
print()

# Paso 2: Generar misión
url2 = 'http://localhost:8080/api/plan_mission'
response2 = requests.post(url2, json={})

print('=== PASO 2: Generar Misión ===')
print('Status code:', response2.status_code)
data = response2.json()

# Mostrar información clave
if 'mission' in data:
    mission = data['mission']
    print(f'Waypoints: {mission.get("total_waypoints", "N/A")}')
    print(f'Status msg: {mission.get("status_message", "N/A")[:60]}...')
    print(f'Dosis objetivo: {mission.get("target_dose_l_ha", "N/A")} L/ha')
    print(f'Swath width: {mission.get("swath_width", "N/A")} m')
    
# Mostrar estado del drone
if 'drone' in data:
    drone = data['drone']
    print(f'Drone status: {drone.get("status", "N/A")}')
    print(f'Battery: {drone.get("battery", "N/A")}%')
    print(f'Tank level: {drone.get("tank_level", "N/A")} L')
    
# Mostrar dimensiones del campo
if 'field' in data:
    field = data['field']
    print(f'Field dimensions: {field.get("width", "N/A")}x{field.get("height", "N/A")} m')
    print(f'Field size: {field.get("hectares", "N/A")} ha')
    print(f'Obstacles detected: {len(field.get("obstacles", []))}')
    print(f'Zones detected: {len(field.get("zones", []))}')