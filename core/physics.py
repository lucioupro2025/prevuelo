import math

class PhysicsEngine:
    """
    Motor de física para el simulador de drones.
    Maneja la dinámica de vuelo, consumo de energía y estabilidad.
    """
    def __init__(self, gravity=9.81, air_density=1.225):
        self.gravity = gravity
        self.air_density = air_density
        self.time_step = 0.1 # 100ms per update
        
    def calculate_thrust(self, mass, throttle):
        """Calcula el empuje basado en el peso y aceleración"""
        return mass * self.gravity * throttle
        
    def calculate_drag(self, velocity, drag_coefficient, frontal_area):
        """Calcula la resistencia del aire"""
        return 0.5 * self.air_density * (velocity ** 2) * drag_coefficient * frontal_area
        
    def update_position(self, current_pos, velocity, dt):
        """Actualiza la posición basada en la velocidad y tiempo"""
        new_pos = {
            "x": current_pos["x"] + velocity["x"] * dt,
            "y": current_pos["y"] + velocity["y"] * dt,
            "z": current_pos["z"] + velocity["z"] * dt
        }
        return new_pos
        
    def calculate_battery_drain(self, drone_state, env_state, mass_kg=None):
        """
        Estimacion realista del consumo de la bateria DJI DB1560.

        Solo consume energia cuando la aeronave esta en vuelo. El consumo
        depende de:
          - Velocidad de translacion (resistencia aerodinamica).
          - Masa total de vuelo (el caldo del tanque pesa 1 kg por litro).
          - Viento: intensidad y componente de cara / de cola respecto al rumbo.
          - Temperatura ambiente (frio y calor extremo penalizan la bateria).

        Devuelve el porcentaje de bateria consumido en este paso de tiempo.
        """
        # En tierra, en base o aterrizando no se consume bateria de vuelo.
        if drone_state.get('status') != "flying":
            return 0.0

        # Consumo de referencia en hover con masa y viento neutros (%/segundo).
        base_drain_per_sec = 0.060

        # 1. Factor de velocidad (crece de forma cuadratica con la resistencia).
        speed = float(drone_state.get('speed', 0.0) or 0.0)
        speed_factor = 1.0 + 0.012 * (speed ** 2)

        # 2. Factor de masa: 39 kg vacio -> 92 kg a plena carga.
        if mass_kg is None:
            mass_kg = 79.0
        mass = max(39.0, min(92.0, float(mass_kg)))
        mass_factor = 0.70 + (mass / 92.0) * 0.40

        # 3. Factor de viento. wind_direction es la direccion HACIA donde sopla.
        #    tailwind = +1 (viento de cola), -1 (viento de cara).
        wind_speed = float(env_state.get('wind_speed', 0.0) or 0.0)
        wind_dir = math.radians(float(env_state.get('wind_direction', 0.0) or 0.0))
        yaw = math.radians(float(drone_state.get('yaw', 0.0) or 0.0))
        tailwind = math.cos(wind_dir - yaw)
        wind_factor = 1.0 + 0.05 * wind_speed - 0.035 * wind_speed * tailwind
        wind_factor = max(0.85, wind_factor)

        # 4. Factor de temperatura.
        temp = float(env_state.get('temperature', 24) or 24)
        temp_factor = 1.0
        if temp > 40:
            temp_factor = 1.0 + (temp - 40) * 0.005
        elif temp < 0:
            temp_factor = 1.0 + abs(temp) * 0.004

        # 5. Consumo adicional de las bombas de pulverizacion cuando hay flujo.
        pump_factor = 1.08 if float(drone_state.get('flow_rate', 0) or 0) > 0 else 1.0

        drain_per_sec = (
            base_drain_per_sec
            * speed_factor
            * mass_factor
            * wind_factor
            * temp_factor
            * pump_factor
        )
        return drain_per_sec * self.time_step

    def update_flight_dynamics(self, drone, env, mass_kg=None):
        """Simulación de un paso de tiempo de vuelo."""
        drain = self.calculate_battery_drain(drone, env, mass_kg=mass_kg)
        new_battery = max(0.0, drone['battery'] - drain)
        return new_battery
