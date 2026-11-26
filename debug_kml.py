import fastkml

with open('E:\\Drone\\test_mapa.kml', 'rb') as f:
    data = f.read()

# Quitamos declaration  
if data.startswith(b'<?xml'):
    data = data[data.index(b'?>') + 2:].lstrip()

doc = fastkml.KML.from_string(data)

print('Features list:', doc.features)
print('Number of features:', len(doc.features))
print()

for i, feature in enumerate(doc.features):
    print(f'Feature {i}:')
    print(f'  Type: {type(feature).__name__}')
    print(f'  Has name: {hasattr(feature, "name")}')
    if hasattr(feature, 'name'):
        print(f'  Name: {feature.name}')
    print(f'  Has geometry: {hasattr(feature, "geometry")}')
    if hasattr(feature, 'geometry'):
        geom = feature.geometry
        print(f'  Geometry type: {type(geom).__name__}')
        if hasattr(geom, 'geom_type'):
            print(f'  Shapely geom_type: {geom.geom_type}')
        elif geom:
            try:
                from shapely.geometry import shape
                s = shape(geom)
                print(f'  Shapely type: {s.geom_type}')
            except Exception as e:
                print(f'  Shapely error: {e}')