import heapq
import math
import random

# Margen de seguridad alrededor de cada obstaculo (m).
SAFE_MARGIN = 2.5


class ApplicationEngine:
    """
    Motor de aplicación agrícola inteligente para DJI AGRAS T50.
    Maneja planificación de misiones con evasión de obstáculos,
    patrones de pulverización y deriva por viento.
    """

    def __init__(self):
        self.coverage_map = []  # Lista de puntos (x, y, cantidad)
        self.total_applied = 0.0

    # ------------------------------------------------------------------
    # Utilidades geometricas de seguridad
    # ------------------------------------------------------------------
    @staticmethod
    def _obstacle_label(obs):
        if not obs:
            return "obstáculo"
        return obs.get("label") or obs.get("id") or "obstáculo"

    @staticmethod
    def _point_segment_distance(px, py, ax, ay, bx, by):
        """Distancia minima de un punto al segmento AB."""
        dx = bx - ax
        dy = by - ay
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx = ax + t * dx
        cy = ay + t * dy
        return math.hypot(px - cx, py - cy)

    def point_blocked(self, x, y, obstacles, extra=0.0):
        """Devuelve el obstaculo cuyo radio de seguridad contiene el punto."""
        for obs in obstacles or []:
            radius = float(obs.get("radius", 4.0)) + SAFE_MARGIN + extra
            if math.hypot(x - float(obs["x"]), y - float(obs["y"])) < radius:
                return obs
        return None

    def segment_blocked(self, ax, ay, bx, by, obstacles, extra=0.0):
        """Devuelve el primer obstaculo que corta el segmento AB."""
        for obs in obstacles or []:
            radius = float(obs.get("radius", 4.0)) + SAFE_MARGIN + extra
            dist = self._point_segment_distance(
                float(obs["x"]), float(obs["y"]), ax, ay, bx, by
            )
            if dist < radius:
                return obs
        return None

    def safe_transit_altitude(self, obstacles, minimum=8.0):
        """Altitud de transito por encima del obstaculo mas alto."""
        top = minimum - 1.5
        for obs in obstacles or []:
            top = max(top, float(obs.get("height", 8.0)))
        return round(max(minimum, top + 1.5), 2)

    @staticmethod
    def _wp(x, y, alt, action, spray, desc):
        return {
            "x": round(float(x), 2),
            "y": round(float(y), 2),
            "alt": round(float(alt), 2),
            "action": action,
            "spray": bool(spray),
            "desc": desc,
        }

    # ------------------------------------------------------------------
    # Planificador de transito con A* (evita circulos de seguridad)
    # ------------------------------------------------------------------
    def plan_transit(self, start, goal, obstacles, field_width, field_height,
                     alt=10.0, spray=False, label="Tránsito seguro", grid=None):
        """
        Devuelve una lista de waypoints (sin incluir el punto de partida)
        que llevan desde `start` hasta `goal` rodeando los obstáculos.
        """
        sx, sy = float(start["x"]), float(start["y"])
        gx, gy = float(goal["x"]), float(goal["y"])
        goal_wp = self._wp(gx, gy, alt, "transit", spray, label)

        # Si la linea directa esta libre, no hace falta desviarse.
        if not self.segment_blocked(sx, sy, gx, gy, obstacles, extra=0.6):
            return [goal_wp]

        if grid is None:
            longest = max(field_width, field_height)
            grid = 1.5 if longest <= 140.0 else 2.5

        inset = 0.8
        nx = max(2, int(math.floor((field_width - 2 * inset) / grid)) + 1)
        ny = max(2, int(math.floor((field_height - 2 * inset) / grid)) + 1)

        blocked_cache = {}

        def node_xy(i, j):
            return (inset + i * grid, inset + j * grid)

        def node_blocked(i, j):
            key = (i, j)
            if key not in blocked_cache:
                x, y = node_xy(i, j)
                blocked_cache[key] = self.point_blocked(x, y, obstacles, extra=0.9) is not None
            return blocked_cache[key]

        def nearest_visible_node(x, y):
            i0 = int(round((x - inset) / grid))
            j0 = int(round((y - inset) / grid))
            best = None
            for ring in range(0, 12):
                for dj in range(-ring, ring + 1):
                    for di in range(-ring, ring + 1):
                        if max(abs(di), abs(dj)) != ring:
                            continue
                        i, j = i0 + di, j0 + dj
                        if i < 0 or j < 0 or i >= nx or j >= ny:
                            continue
                        if node_blocked(i, j):
                            continue
                        px, py = node_xy(i, j)
                        if self.segment_blocked(x, y, px, py, obstacles, extra=0.6):
                            continue
                        dist = math.hypot(px - x, py - y)
                        if best is None or dist < best[0]:
                            best = (dist, (i, j))
                if best is not None:
                    break
            return best[1] if best else None

        start_node = nearest_visible_node(sx, sy)
        goal_node = nearest_visible_node(gx, gy)
        if start_node is None or goal_node is None:
            # Ultimo recurso: dejar que el controlador de vuelo gestione el tramo.
            return [goal_wp]

        directions = [
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, 1.41421356), (-1, 1, 1.41421356),
            (1, -1, 1.41421356), (1, 1, 1.41421356),
        ]

        def heuristic(node):
            px, py = node_xy(*node)
            return math.hypot(px - gx, py - gy)

        open_heap = [(heuristic(start_node), 0.0, start_node)]
        g_score = {start_node: 0.0}
        came_from = {}
        closed = set()
        found = False

        while open_heap:
            _, g, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            closed.add(current)
            if current == goal_node:
                found = True
                break

            ci, cj = current
            for di, dj, cost in directions:
                ni, nj = ci + di, cj + dj
                if ni < 0 or nj < 0 or ni >= nx or nj >= ny:
                    continue
                if node_blocked(ni, nj):
                    continue
                # Evitar cortar esquinas en diagonal.
                if di and dj and (node_blocked(ci + di, cj) or node_blocked(ci, cj + dj)):
                    continue
                ng = g + cost * grid
                if ng < g_score.get((ni, nj), float("inf")):
                    g_score[(ni, nj)] = ng
                    came_from[(ni, nj)] = current
                    heapq.heappush(
                        open_heap,
                        (ng + heuristic((ni, nj)), ng, (ni, nj)),
                    )

        if not found:
            return [goal_wp]

        nodes = []
        cursor = goal_node
        while cursor != start_node:
            nodes.append(cursor)
            cursor = came_from[cursor]
        nodes.append(start_node)
        nodes.reverse()

        raw = [(sx, sy)] + [node_xy(i, j) for i, j in nodes] + [(gx, gy)]

        cleaned = []
        for point in raw:
            if (not cleaned
                    or math.hypot(point[0] - cleaned[-1][0],
                                  point[1] - cleaned[-1][1]) > 0.05):
                cleaned.append(point)

        # Suavizado por linea de vision.
        simplified = [cleaned[0]]
        i = 0
        while i < len(cleaned) - 1:
            j = len(cleaned) - 1
            while j > i + 1 and self.segment_blocked(
                cleaned[i][0], cleaned[i][1],
                cleaned[j][0], cleaned[j][1],
                obstacles, extra=0.6,
            ):
                j -= 1
            simplified.append(cleaned[j])
            i = j

        out = [
            self._wp(px, py, alt, "transit", spray, label)
            for px, py in simplified[1:]
        ]
        if not out:
            out = [goal_wp]
        else:
            out[-1] = goal_wp
        return out

    # ------------------------------------------------------------------
    # Mision automatica: pasadas paralelas + transitos seguros
    # ------------------------------------------------------------------
    def _spray_row(self, y_row, x_start, x_end, direction_right, obstacles,
                   field_width, field_height, margin, row_index):
        """Genera una pasada de pulverizacion rodeando obstaculos."""
        points = [
            self._wp(x_start, y_row, 3.0, "spray_line", True,
                     f"Pasada {row_index + 1} inicio")
        ]

        lo_x = min(x_start, x_end)
        hi_x = max(x_start, x_end)
        row_obstacles = []
        for obs in obstacles or []:
            clearance = float(obs.get("radius", 4.0)) + SAFE_MARGIN + 0.8
            if abs(float(obs["y"]) - y_row) > clearance:
                continue
            if lo_x - clearance <= float(obs["x"]) <= hi_x + clearance:
                row_obstacles.append(obs)

        row_obstacles.sort(
            key=lambda o: float(o["x"]), reverse=not direction_right
        )

        for obs in row_obstacles:
            ox = float(obs["x"])
            oy = float(obs["y"])
            safe_r = float(obs.get("radius", 4.0)) + SAFE_MARGIN
            d = safe_r + 1.5

            if direction_right:
                before_x, after_x = ox - d, ox + d
            else:
                before_x, after_x = ox + d, ox - d

            # Elegir el lado del obstaculo que quede dentro del lote.
            above_y = oy + d
            below_y = oy - d
            can_above = above_y <= field_height - margin
            can_below = below_y >= margin
            if can_above and can_below:
                detour_y = below_y if abs(below_y - y_row) <= abs(above_y - y_row) else above_y
            elif can_above:
                detour_y = above_y
            elif can_below:
                detour_y = below_y
            else:
                continue

            label = self._obstacle_label(obs)
            detour = [
                (before_x, y_row),
                (before_x, detour_y),
                (after_x, detour_y),
                (after_x, y_row),
            ]
            for px, py in detour:
                points.append(
                    self._wp(px, py, 3.2, "obstacle_bypass", False,
                             f"Evasión de {label}")
                )

        points.append(
            self._wp(x_end, y_row, 3.0, "spray_line", True,
                     f"Pasada {row_index + 1} fin")
        )
        return points

    def generate_smart_mission(self, field_width=100.0, field_height=100.0,
                               swath_width=8.0, obstacles=None,
                               home_point=None, margin=6.0, zones=None):
        """
        Genera una ruta agronómica profesional de pasadas paralelas con
        detección y evasión automática de obstáculos. Los tramos de
        aproximación y retorno usan un planificador A* para no atravesar
        árboles ni postes.
        """
        obstacles = obstacles or []
        zones = zones or []
        
        # --- PROCESAR ZONAS Y AJUSTAR PARÁMETROS ---
        # Diccionarios para mapear la posición centroide a dosis/ancho de faja
        zone_doses = {}
        zone_swaths = {}
        
        for zone in zones:
            # Asignar dosis por defecto si no hay una definida específicamente
            # Debug: print zone keys
            print(f"DEBUG zone keys: {list(zone.keys())}")
            print(f"DEBUG zone: {zone}")
            try:
                zone_doses[zone['center_x']] = zone.get('target_dose_l_ha', 15.0)
            except KeyError as e:
                print(f"KEY ERROR: {e} not in zone keys")
                # Assign default and continue
                zone_doses[0] = zone.get('target_dose_l_ha', 15.0)
            try:
                zone_swaths[zone['center_x']] = zone.get('effective_swath_width', swath_width)
            except KeyError as e:
                print(f"KEY ERROR: {e} not in zone keys")
                zone_swaths[0] = zone.get('effective_swath_width', swath_width)
        
        # Determinar si debemos variar el ancho de faja durante la misión
        use_variable_swath = len(zones) > 1 and any(
            zone.get('target_dose_l_ha', 15.0) != 15.0 for zone in zones
        )
        
        # Optimización: Si el alto es mayor que el ancho, rotamos internamente
        # 90° para que el generador de pasadas (que orienta en X) quede alineado
        # al lado mayor, minimizando el número total de pasadas y giros.
        rotated = False
        if field_height > field_width:
            rotated = True
            field_width, field_height = field_height, field_width
            if home_point:
                home_point = {"x": float(home_point.get("y", 0.0)), "y": float(home_point.get("x", 0.0))}
            obstacles = [
                dict(obs, x=float(obs.get("y", 0.0)), y=float(obs.get("x", 0.0)))
                for obs in (obstacles or [])
            ]
        else:
            if home_point:
                home_point = {"x": float(home_point.get("x", 0.0)), "y": float(home_point.get("y", 0.0))}
            obstacles = [
                dict(obs, x=float(obs.get("x", 0.0)), y=float(obs.get("y", 0.0)))
                for obs in (obstacles or [])
            ]

        if home_point is None:
            home_point = {"x": field_width / 2.0, "y": field_height / 2.0}

        safe_alt = self.safe_transit_altitude(obstacles)
        waypoints = [
            self._wp(home_point["x"], home_point["y"], safe_alt,
                     "takeoff_home", False,
                     "Despegue en base y ascenso a altitud segura")
        ]

        y_start = margin
        y_end = field_height - margin
        rows = max(0, int((y_end - y_start) / swath_width))
        direction_right = True

        for i in range(rows + 1):
            y_row = y_start + (i * swath_width)
            x_start = margin if direction_right else (field_width - margin)
            x_end = (field_width - margin) if direction_right else margin
            current = waypoints[-1]

            if i == 0:
                # Tramo base -> primera pasada: siempre planificado y elevado.
                waypoints.extend(self.plan_transit(
                    current, {"x": x_start, "y": y_row}, obstacles,
                    field_width, field_height, alt=safe_alt, spray=False,
                    label=f"Tránsito seguro a pasada {i + 1}",
                ))
            elif self.segment_blocked(
                current["x"], current["y"], x_start, y_row,
                obstacles, extra=0.6,
            ):
                # Giro bloqueado: rodear el obstáculo antes de entrar.
                waypoints.extend(self.plan_transit(
                    current, {"x": x_start, "y": y_row}, obstacles,
                    field_width, field_height,
                    alt=max(6.0, safe_alt - 2.0), spray=False,
                    label=f"Desvío a pasada {i + 1}",
                ))
            else:
                waypoints.append(
                    self._wp(x_start, y_row, 3.0, "turn", False,
                             f"Giro a pasada {i + 1}")
                )

            waypoints.extend(self._spray_row(
                y_row, x_start, x_end, direction_right, obstacles,
                field_width, field_height, margin, i,
            ))
            direction_right = not direction_right

        # Retorno seguro a base y aterrizaje.
        waypoints.extend(self.plan_transit(
            waypoints[-1], home_point, obstacles,
            field_width, field_height, alt=safe_alt, spray=False,
            label="Retorno seguro a base",
        ))
        waypoints.append(
            self._wp(home_point["x"], home_point["y"], safe_alt,
                     "rth_finish", False,
                     "Misión completada: retorno a base")
        )
        waypoints.append(
            self._wp(home_point["x"], home_point["y"], 0.0,
                     "land_home", False, "Aterrizaje en base")
        )
        if rotated:
            for wp in waypoints:
                wp["x"], wp["y"] = wp["y"], wp["x"]
        return waypoints

    # ------------------------------------------------------------------
    # Ruta manual trazada por el usuario
    # ------------------------------------------------------------------
    def validate_custom_route(self, points, home_point, field_width,
                              field_height, obstacles):
        """
        Valida una ruta manual completa (base -> puntos -> base).
        Devuelve (errores, segmentos_ok).
        """
        errors = []
        segments_ok = []

        for i, point in enumerate(points, start=1):
            x, y = float(point["x"]), float(point["y"])
            if not (1.0 <= x <= field_width - 1.0
                    and 1.0 <= y <= field_height - 1.0):
                errors.append(
                    f"El punto P{i} está fuera del lote. Colóquelo dentro del área verde."
                )
            hit = self.point_blocked(x, y, obstacles, extra=0.6)
            if hit:
                errors.append(
                    f"El punto P{i} está dentro del área de seguridad de "
                    f"'{self._obstacle_label(hit)}'. Aléjelo del obstáculo."
                )

        route = [home_point] + list(points) + [home_point]
        names = ["Base"] + [f"P{i}" for i in range(1, len(points) + 1)] + ["Base"]

        for i in range(len(route) - 1):
            a, b = route[i], route[i + 1]
            hit = self.segment_blocked(
                float(a["x"]), float(a["y"]),
                float(b["x"]), float(b["y"]),
                obstacles, extra=0.6,
            )
            if hit:
                segments_ok.append(False)
                errors.append(
                    f"El tramo {names[i]} -> {names[i + 1]} cruza "
                    f"'{self._obstacle_label(hit)}'. Agregue un punto para rodearlo."
                )
            else:
                segments_ok.append(True)

        return errors, segments_ok

    def build_custom_mission(self, points, home_point, field_width,
                             field_height, obstacles):
        """Convierte los puntos del usuario en waypoints ejecutables."""
        safe_alt = self.safe_transit_altitude(obstacles)
        waypoints = [
            self._wp(home_point["x"], home_point["y"], safe_alt,
                     "takeoff_home", False,
                     "Despegue en base y ascenso a altitud segura")
        ]

        for i, point in enumerate(points, start=1):
            waypoints.append(
                self._wp(point["x"], point["y"], 3.0, "spray_line",
                         bool(point.get("spray", True)),
                         f"Punto {i} de ruta manual")
            )

        waypoints.extend(self.plan_transit(
            waypoints[-1], home_point, obstacles,
            field_width, field_height, alt=safe_alt, spray=False,
            label="Retorno seguro a base",
        ))
        waypoints.append(
            self._wp(home_point["x"], home_point["y"], safe_alt,
                     "rth_finish", False,
                     "Ruta completada: retorno a base")
        )
        waypoints.append(
            self._wp(home_point["x"], home_point["y"], 0.0,
                     "land_home", False, "Aterrizaje en base")
        )
        return waypoints

    # ------------------------------------------------------------------
    # Escenarios aleatorios de entrenamiento
    # ------------------------------------------------------------------
    def generate_random_obstacles(self, field_width, field_height,
                                  home_point, rng=None):
        """Distribuye arboles y postes sin tapar la base ni los bordes."""
        rng = rng or random
        area = field_width * field_height
        count = int(max(2, min(8, round(area / 3500.0))))
        obstacles = []
        edge = 16.0

        for _ in range(900):
            if len(obstacles) >= count:
                break

            kind = rng.choices(["tree", "pole"], weights=[0.78, 0.22])[0]
            if kind == "tree":
                radius = round(rng.uniform(3.0, 5.5), 1)
                height = round(rng.uniform(7.0, 10.5), 1)
            else:
                radius = round(rng.uniform(1.3, 2.3), 1)
                height = round(rng.uniform(8.0, 12.0), 1)

            x = round(rng.uniform(edge, field_width - edge), 1)
            y = round(rng.uniform(edge, field_height - edge), 1)

            if math.hypot(x - home_point["x"], y - home_point["y"]) < radius + 16.0:
                continue

            too_close = False
            for other in obstacles:
                if math.hypot(x - other["x"], y - other["y"]) < (
                    radius + other["radius"] + 9.0
                ):
                    too_close = True
                    break
            if too_close:
                continue

            number = 1 + sum(1 for o in obstacles if o["type"] == kind)
            obstacles.append({
                "id": f"{kind}_{number}",
                "type": kind,
                "x": x,
                "y": y,
                "radius": radius,
                "height": height,
                "label": ("Árbol " if kind == "tree" else "Poste ") + str(number),
            })

        return obstacles

    def generate_random_scenario(self, hectares=None, rng=None):
        """Genera lote, obstaculos, viento y temperatura aleatorios."""
        rng = rng or random
        if hectares is None:
            hectares = float(rng.choice([0.8, 1.0, 1.2, 1.6, 2.0]))
        hectares = max(0.4, min(3.0, float(hectares)))

        side = round(math.sqrt(hectares * 10000.0), 1)
        inset = max(9.0, round(side * 0.10, 1))
        
        # Generar viento temprano para ubicar el Home Point "contra el viento"
        # y evitar que la niebla de deriva afecte la base y el operador.
        wind_direction = float(rng.choice([0, 45, 90, 135, 180, 225, 270, 315]))
        wind_speed = round(rng.uniform(0.0, 8.5), 1)
        
        # Elección inteligente del Home Point: ubicado "contra el viento"
        # para evitar que la niebla de deriva afecte la base y el operador.
        # El viento sopla HACÍA wind_direction. "Contra el viento" es la dirección opuesta.
        
        # Mapear dirección de viento a la esquina "barlevante" (upwind) para el home point
        # 0-90° (NE): home en SW (inset, inset)
        # 90-180° (SE): home en NW (inset, side-inset)
        # 180-270° (SW): home en NE (side-inset, side-inset)
        # 270-360° (NW): home en SE (side-inset, inset)
        
        if wind_direction < 90.0:
            # Viento hacia NE -> Home SW (barlevante)
            home = {"x": round(inset, 1), "y": round(inset, 1)}
        elif wind_direction < 180.0:
            # Viento hacia SE -> Home NW (barlevante)
            home = {"x": round(inset, 1), "y": round(side - inset, 1)}
        elif wind_direction < 270.0:
            # Viento hacia SW -> Home NE (barlevante)
            home = {"x": round(side - inset, 1), "y": round(side - inset, 1)}
        else:
            # Viento hacia NW -> Home SE (barlevante)
            home = {"x": round(side - inset, 1), "y": round(inset, 1)}

        obstacles = self.generate_random_obstacles(side, side, home, rng)
        wind_speed = round(rng.uniform(0.0, 8.5), 1)
        wind_direction = float(rng.choice([0, 45, 90, 135, 180, 225, 270, 315]))
        temperature = int(rng.randint(14, 38))

        return {
            "hectares": round((side * side) / 10000.0, 2),
            "width": side,
            "height": side,
            "size": {"width": side, "height": side},
            "home_point": home,
            "obstacles": obstacles,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "temperature": temperature,
            "weather": "windy" if wind_speed >= 6.0 else "sunny",
        }

    # ------------------------------------------------------------------
    # Aplicacion y deriva
    # ------------------------------------------------------------------
    def add_coverage_point(self, x, y, amount):
        """Registra un punto de aplicación en el campo"""
        self.coverage_map.append({
            "x": round(x, 2),
            "y": round(y, 2),
            "amount": amount
        })
        self.total_applied += amount

    def calculate_efficiency(self, target_area_size):
        """Calcula la eficiencia de la aplicación"""
        if target_area_size <= 0:
            return 0.0
        covered_area = len(self.coverage_map) * 2.0
        return min(1.0, covered_area / target_area_size)

    def calculate_spray_drift(self, wind_speed_ms, wind_dir_deg, altitude_m=3.0):
        """
        Calcula el vector de deriva de gota según viento y altitud.
        Viento mayor a 6 m/s genera deriva crítica fuera de la franja.
        """
        drift_factor = 0.25 * (altitude_m / 3.0)
        drift_distance = wind_speed_ms * drift_factor

        rad = math.radians(wind_dir_deg)
        drift_dx = drift_distance * math.sin(rad)
        drift_dy = -drift_distance * math.cos(rad)

        is_safe = wind_speed_ms <= 8.0

        return {
            "dx": round(drift_dx, 2),
            "dy": round(drift_dy, 2),
            "distance_m": round(drift_distance, 2),
            "is_safe_wind": is_safe
        }
