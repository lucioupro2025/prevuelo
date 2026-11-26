import fastkml

with open('E:\\Drone\\test_mapa.kml', 'rb') as f:
    data = f.read()

if data.startswith(b'<?xml'):
    data = data[data.index(b'?>') + 2:].lstrip()

doc = fastkml.KML.from_string(data)

# The Document has its own features list
print('doc.features:', doc.features)
print('Type:', type(doc.features[0]).__name__ if doc.features else 'Empty')
print()

# Access the Document's inner features
if doc.features and hasattr(doc.features[0], 'features'):
    inner_features = doc.features[0].features
    print('Inner features count:', len(inner_features))
    for i, f in enumerate(inner_features):
        print(f'Feature {i}: name={getattr(f, "name", None)}, type={type(f).__name__}')
        if hasattr(f, 'geometry'):
            geom = f.geometry
            print(f'  Geometry: {type(geom).__name__ if geom else None}')
            if hasattr(geom, 'geom_type'):
                print(f'  geom_type: {geom.geom_type}')