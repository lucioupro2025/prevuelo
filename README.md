# Reporte Predictivo de Rentabilidad Agrícola

Herramienta de análisis pre-aplicación: toma un **lote real en formato KML** (QGIS, WebODM, DJI Terra, Mavic 3M) y entrega, antes de mover un solo litro de caldo, la **superficie, el volumen necesario, el tiempo de labor, el costo operativo, el ahorro estimado, el ROI, el riesgo de deriva por viento y la configuración ideal de aplicación**.

El resultado se muestra en pantalla desde el primer segundo y puede descargarse como **informe PDF**.

> 🌐 **Demo online (gratis, sin instalar nada):** [https://prevuelo.onrender.com](https://prevuelo.onrender.com)
>
> Cada visitante tiene una **sesión independiente**: puede cargar su propio KML y mover las variables sin afectar a los demás. El servidor gratuito se duerme tras ~15 min de inactividad; la primera visita puede tardar ~30 s en despertar.

---

## Índice

1. [Qué hace](#1-qué-hace)
2. [Interfaz](#2-interfaz)
3. [Métricas y fórmulas](#3-métricas-y-fórmulas)
4. [Configuración ideal de aplicación](#4-configuración-ideal-de-aplicación)
5. [Carga de lotes KML](#5-carga-de-lotes-kml)
6. [API REST](#6-api-rest)
7. [Estructura del proyecto](#7-estructura-del-proyecto)
8. [Instalación y puesta en marcha](#8-instalación-y-puesta-en-marcha)
9. [Problemas comunes](#9-problemas-comunes)
10. [Documentación adicional](#10-documentación-adicional)

---

## 1. Qué hace

El flujo de trabajo es deliberadamente corto:

1. **Cargar el lote** — `test_mapa.kml` se analiza automáticamente al iniciar el servidor, o se sube cualquier otro KML.
2. **Ver el mapa** — la geometría real del KML se dibuja sobre imagen satelital o callejero, con ambientes, obstáculos y punto base.
3. **Ajustar variables** — viento, separación entre pasadas, velocidad de avance, precio por hectárea y ahorro de caldo, desde desplegables. El informe se recalcula solo.
4. **Leer el reporte** — ROI, superficie, caldo total, costo operativo, ahorro y detalle por ambiente.
5. **Descargar** — botón **Descargar PDF** con el resumen y la configuración recomendada.

El cálculo se ejecuta en el servidor (`calcular_informe_predictivo()` en `main.py`) y se guarda en el estado privado de cada visitante, por lo que viaja en cada respuesta de `/api/report` y se mantiene sincronizado con la interfaz. Dos personas pueden usar la herramienta al mismo tiempo sin compartir lote ni variables.

---

## 2. Interfaz

| Elemento | Ubicación | Contenido |
| :--- | :--- | :--- |
| **Encabezado** | Parte superior | Nombre del reporte, carga de KML, lote de ejemplo y descarga de PDF |
| **Mapa del lote** | Columna izquierda | Polígonos del KML sobre satélite/calles, obstáculos, punto base, escala y norte |
| **Detalle por ambiente** | Debajo del mapa | Superficie, dosis, caldo y costo de cada ambiente |
| **Retorno de inversión** | Columna derecha | ROI, superficie, caldo total, costo y ahorro estimado |
| **Configuración ideal de aplicación** | Columna derecha | Altitud, velocidad, separación, caudal, pasadas, distancia, recargas, baterías y avisos |
| **Detalle del cálculo** | Columna derecha | Dosis promedio, tiempo de labor, ancho de faja, ahorro, deriva, ambientes y obstáculos |
| **Variables del cálculo** | Columna derecha | Desplegables de viento, separación y velocidad; campos de precio y ahorro |

Valores del lote por defecto (`test_mapa.kml`):

```
Superficie:       30,87 ha
Ambientes:        2 (16 y 24 L/ha)
Dosis promedio:   19,99 L/ha
Caldo total:      617,2 L
Tiempo de labor:  1,82 h (a 6,5 m/s y 8 m de separación)
Costo operativo:  USD 6.174 (200 USD/ha)
Ahorro estimado:  92,6 L / USD 926,1
ROI:              15,0 %
Deriva:           20,0 % (viento 4 m/s)
```

---

## 3. Métricas y fórmulas

Todas las métricas se calculan en `calcular_informe_predictivo()` (`main.py`).

| Métrica | Campo JSON | Cálculo |
| :--- | :--- | :--- |
| Superficie | `hectares` | Área de los polígonos KML proyectada a metros |
| Dosis promedio | `target_dose` | `Σ(ha × dosis) / ha totales` |
| Caldo total | `total_liters` | `Σ(ha de cada ambiente × su dosis)` |
| Tiempo de labor | `application_time_hours` | `pasadas × largo / (velocidad × 3600)` |
| Ancho de faja | `swath_width` | Separación entre pasadas elegida (8 m por defecto) |
| Costo operativo | `cost_total_usd` | `hectáreas × precio por hectárea` |
| Ahorro de caldo | `savings_liters` | `caldo total × % de ahorro` |
| Ahorro económico | `cost_savings_usd` | `ahorro de caldo × (precio / dosis promedio)` |
| ROI | `roi_percent` | `ahorro económico / costo operativo × 100` |
| Deriva por viento | `drift_estimate_percent` | `clamp(viento × 5, 5, 30)` |
| Ambientes | `zone_count` | Cantidad de polígonos con dosis |
| Obstáculos | `obstacle_count` | Árboles y postes detectados |

El caldo total **no** usa una dosis única: suma el volumen de cada ambiente según su propia prescripción. Por eso `test_mapa.kml` da 617,2 L y no 493,9 L.

**Nota sobre el ROI:** con los valores por defecto el ahorro es un porcentaje fijo del costo (15 %), por lo que el ROI resultante también es 15 %. Los parámetros se editan desde la interfaz y el cálculo se actualiza automáticamente.

---

## 4. Configuración ideal de aplicación

El backend devuelve el bloque `report.recommended` con una recomendación operativa derivada del viento, la dosis promedio y la geometría del lote:

| Campo | Descripción |
| :--- | :--- |
| `altitude_m` | Altitud de aplicación sugerida (2,5 a 3,5 m; baja con viento fuerte) |
| `speed_m_s` | Velocidad de avance recomendada según el viento (0 = no aplicar) |
| `swath_width_m` | Separación entre pasadas recomendada según la dosis |
| `flow_rate_l_min` | Caudal requerido: `dosis × separación × velocidad × 0,006` |
| `passes` | Cantidad de pasadas: `ceil(lado corto / separación)` |
| `distance_km` | Distancia total estimada de labor |
| `tank_refills` | Recargas de tanque de 40 L |
| `battery_cycles` | Baterías estimadas (12 min de autonomía) |
| `wind_status` | `optimo`, `aceptable`, `precaucion` o `no_aplicar` |
| `wind_label` | Texto legible del estado del viento |
| `notes` | Avisos operativos (deriva, recargas, dosis variable, caudal) |

La tarjeta se actualiza junto con el resto del informe y también se incluye en el PDF.

---

## 5. Carga de lotes KML

- **Formatos aceptados:** `.kml` y `.xml` (hasta 15 MB).
- **Lote por defecto:** `test_mapa.kml` se carga automáticamente al arrancar `main.py`.
- **Recarga:** botón **Lote de ejemplo** → `POST /api/load_default_kml`.
- **Carga manual:** botón **Cargar KML** → `POST /api/import_kml` (multipart, campo `kml_file`).

### Datos que extrae el parser (`core/kml_parser.py`)

| Campo | Descripción |
| :--- | :--- |
| `doc_name` | Nombre del documento KML |
| `description` | Descripción del lote |
| `hectares` | Superficie calculada con Shapely |
| `width` / `height` | Dimensiones del lote en metros |
| `zones` | Ambientes con dosis, ancho de faja, color y coordenadas locales |
| `obstacles` | Árboles y postes con radio y altura |
| `home_point` | Punto base declarado en el KML |
| `gps_bounds` | Límites geográficos del lote (se usan para el mapa satelital) |
| `overlays` | Imágenes superpuestas del KML (si existen) |

Cada ambiente puede declarar `target_dose_l_ha` (o `dosis_l_ha`, `dosis`, `rate`, `target_dose`, `dose`) y `effective_swath_width`. El informe respeta la dosis de cada ambiente.

---

## 6. API REST

| Endpoint | Método | Descripción |
| :--- | :--- | :--- |
| `/` | `GET` | Sirve la interfaz web. |
| `/api/report` | `GET` | Informe actual: lote, parámetros y métricas. |
| `/api/status` | `GET` | Alias de compatibilidad de `/api/report`. |
| `/api/import_kml` | `POST` | Importa un KML (multipart `kml_file`) y devuelve el informe. |
| `/api/load_default_kml` | `POST` | Recarga `test_mapa.kml` y devuelve el informe. |
| `/api/report/config` | `POST` | Actualiza variables y recalcula el informe (JSON). |
| `/api/report_pdf` | `GET` | Genera y descarga el informe PDF del lote actual. |

Todos los ejemplos usan `localhost:8080` para desarrollo local. En la demo online, reemplazalo por `https://prevuelo.onrender.com`.

### Ejemplo: consumir el informe

```bash
curl http://localhost:8080/api/report
```

```json
{
  "source_file": "test_mapa.kml",
  "report": {
    "hectares": 30.87,
    "target_dose": 19.99,
    "total_liters": 617.2,
    "application_time_hours": 1.82,
    "swath_width": 8.0,
    "cost_total_usd": 6174.0,
    "savings_liters": 92.6,
    "cost_savings_usd": 926.1,
    "roi_percent": 15.0,
    "drift_estimate_percent": 20.0,
    "zone_count": 2,
    "obstacle_count": 2,
    "recommended": {
      "altitude_m": 3.0,
      "speed_m_s": 6.5,
      "swath_width_m": 8.0,
      "flow_rate_l_min": 6.2,
      "passes": 64,
      "distance_km": 42.6,
      "tank_refills": 16,
      "battery_cycles": 10,
      "wind_status": "optimo",
      "wind_label": "Optimo para aplicar"
    }
  }
}
```

### Ejemplo: cambiar variables y recalcular

```bash
curl -X POST http://localhost:8080/api/report/config \
  -H "Content-Type: application/json" \
  -d "{\"wind_speed\": 7, \"swath_width\": 10, \"application_speed\": 5.5, \"price_per_hectare\": 250, \"savings_percent\": 20}"
```

| Variable | Rango |
| :--- | :--- |
| `wind_speed` | 0 a 15 m/s |
| `swath_width` | 4 a 14 m |
| `application_speed` | 0,5 a 20 m/s |
| `price_per_hectare` | Mayor a 0 |
| `savings_percent` | 0 a 100 |

### Ejemplo: subir un KML

```bash
curl -X POST -F "kml_file=@mi_lote.kml" http://localhost:8080/api/import_kml
```

---

## 7. Estructura del proyecto

```
prevuelo/
├── main.py                  # Servidor Flask, sesiones, cálculo del informe y PDF
├── requirements.txt         # Dependencias de producción
├── README.md                # Este documento
├── Que es esto.md           # Descripción para operadores
├── test_mapa.kml            # Lote real por defecto (San Luis)
├── templates/
│   └── index.html           # Interfaz: mapa, KPIs, configuración ideal y variables
├── static/
│   └── logo-prevuelo.png    # Logo de la aplicación
└── core/
    └── kml_parser.py        # Parseo y proyección de KML (Shapely)
```

### Tecnologías

- **Backend:** Python 3.10+, Flask, Flask-CORS.
- **Servidor WSGI:** Gunicorn (despliegue en Render.com).
- **Geometría:** Shapely (proyección WGS84 → metros y cálculo de superficies).
- **Reportes:** ReportLab + Pillow (PDF A4).
- **Frontend:** HTML5, CSS3 y JavaScript sin dependencias; mapa en canvas con tiles de Esri/OpenStreetMap.

---

## 8. Instalación y puesta en marcha

### 1. Requisitos

- Python 3.10 o superior.
- Las dependencias de `requirements.txt` (`flask`, `flask-cors`, `shapely`, `reportlab`, `pillow` y `gunicorn`).

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Ejecutar

```bash
python main.py
```

### 4. Abrir en el navegador

```
http://localhost:8080
```

Al iniciar, el servidor carga `test_mapa.kml` y calcula el informe automáticamente, por lo que la pantalla ya muestra el mapa y los KPIs sin necesidad de subir ningún archivo.

> El servidor corre con `DEBUG = False` y escucha en `0.0.0.0`. El puerto se toma de la variable de entorno `PORT` (por defecto `8080`), lo que permite el despliegue en Render. Para desarrollo local podés cambiar `DEBUG = True` en `main.py` si querés recarga automática; los cambios en `templates/index.html` solo requieren refrescar el navegador.

### 5. Despliegue (Render.com)

El repositorio está conectado a Render con esta configuración:

| Campo | Valor |
| :--- | :--- |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn main:app --bind 0.0.0.0:$PORT` |
| **Plan** | Free |

Cada push a `main` dispara un deploy automático. La URL pública es [https://prevuelo.onrender.com](https://prevuelo.onrender.com).

---

## 9. Problemas comunes

| Síntoma | Causa probable | Solución |
| :--- | :--- | :--- |
| No veo los cambios en la interfaz | Caché del navegador | `Ctrl + Shift + R` (o `Ctrl + F5`). |
| El mapa no muestra imagen satelital | Sin conexión a internet o tiles bloqueados | Cambiar el fondo a **Calles** o **Sin fondo**; los polígonos se siguen dibujando. |
| `POST /api/import_kml` devuelve 400 | El KML no contiene polígonos válidos | Verificar que el archivo tenga `Polygon` y coordenadas WGS84. |
| `GET /api/report_pdf` devuelve 400 | No hay informe calculado | Cargar un KML (o recargar el lote de ejemplo) primero. |
| El puerto 8080 está ocupado | Proceso anterior activo | `netstat -ano | findstr :8080` y cerrar el PID con `taskkill /F /PID <pid>`. |
| Error al importar `reportlab` / `shapely` | Dependencias faltantes | `pip install -r requirements.txt`. |
| La demo online tarda en abrir | El plan gratuito duerme el servidor tras ~15 min | Esperar ~30 s; despierta automáticamente. |
| Otro usuario cambió mis variables | No aplica: cada visitante tiene sesión propia | Si volviste a abrir el navegador, se creó una sesión nueva con el lote de ejemplo. |

---

## 10. Documentación adicional

- **[Que es esto.md](Que%20es%20esto.md)** — descripción del proyecto para operadores.

---

*Herramienta de análisis para agricultura de precisión · Desarrollada por [guruweb.com.ar](https://guruweb.com.ar) · WhatsApp: +54 9 2657 284903*
