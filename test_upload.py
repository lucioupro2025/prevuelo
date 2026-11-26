import urllib.request, urllib.parse, json
url = 'http://localhost:8080/api/import_kml'
# Crear el multipart/form-data
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gL'
body = f"------WebKitFormBoundary7MA4YWxkTrZu0gL\r\nContent-Disposition: form-data; name=\"kml_file\"\r\n\r\n"
with open('test_mapa.kml', 'rb') as f:
    data = f.read()
body += data.decode('utf-8', errors='ignore')
body += f"\r\n------WebKitFormBoundary7MA4YWxkTrZu0gL--\r\n"
# Enviar solicitud
req = urllib.request.Request(url, data=body.encode('utf-8'), headers={'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gL'})
try:
    with urllib.request.urlopen(req) as response:
        print('Status:', response.getcode())
        print('Response:', response.read().decode('utf-8'))
except Exception as e:
    print('Error:', e)