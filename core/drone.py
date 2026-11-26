class DJIT50:
    """
    Representación del drone DJI AGRAS con especificaciones reales.
    Basado en el User Manual v1.0 y Quick Start Guide.
    Compatible con modelos: T25P, T55, T70, T100
    """
    # Especificaciones por variante de modelo
    MODEL_SPECS = {
        'T25P': {
            'mass_empty': 39.0,
            'max_takeoff_weight': 92.0,
            'spray_tank_capacity': 20.0,  # L
            'max_spray_flow': 24.0,  # L/min
            'swath_min': 7.0,  # m
            'swath_max': 11.0,  # m
            'flight_speed_min': 3.0,  # m/s
            'flight_speed_max': 15.0,  # m/s
            'tank_capacity_L': 20.0,
            'description': 'Estándar extensivo, 1 solo operador'
        },
        'T55': {
            'mass_empty': 55.0,
            'max_takeoff_weight': 160.0,
            'spray_tank_capacity': 50.0,  # L
            'max_spray_flow': 50.0,  # L/min
            'swath_min': 7.0,
            'swath_max': 15.0,
            'flight_speed_min': 3.0,
            'flight_speed_max': 15.0,
            'tank_capacity_L': 50.0,
            'description': 'Alto volumen, contratista profesional'
        },
        'T70': {
            'mass_empty': 70.0,
            'max_takeoff_weight': 180.0,
            'spray_tank_capacity': 70.0,  # L
            'max_spray_flow': 40.0,  # L/min
            'swath_min': 9.0,
            'swath_max': 20.0,
            'flight_speed_min': 3.0,
            'flight_speed_max': 15.0,
            'tank_capacity_L': 70.0,
            'description': 'Escala industrial'
        },
        'T100': {
            'mass_empty': 100.0,
            'max_takeoff_weight': 250.0,
            'spray_tank_capacity': 100.0,  # L
            'max_spray_flow': 40.0,  # L/min
            'swath_min': 11.0,
            'swath_max': 25.0,
            'flight_speed_min': 3.0,
            'flight_speed_max': 15.0,
            'tank_capacity_L': 100.0,
            'description': 'Fertilización masiva'
        }
    }
    
    def __init__(self, variant='T50'):
        # Cargar especificaciones de la variante
        spec_key = f'{variant}'
        if spec_key in self.MODEL_SPECS:
            spec = self.MODEL_SPECS[spec_key]
            self.mass_empty = spec['mass_empty']
            self.max_takeoff_weight = spec['max_takeoff_weight']
            self.spray_tank_capacity = spec['spray_tank_capacity']
            self.max_spray_flow = spec['max_spray_flow']
            self.min_spray_flow = 2.0
            self.arm_spacing = 2200
            self.effective_swath_width = {
                'min': spec['swath_min'],
                'max': spec['swath_max'],
                'variable': True,
                'dependsOn': ['height', 'speed']
            }
        else:
            # Default T50
            self.mass_empty = 39.0
            self.max_takeoff_weight = 92.0
            self.spray_tank_capacity = 40.0
            self.max_spray_flow = 24.0
            self.min_spray_flow = 2.0
            self.arm_spacing = 2200
            self.effective_swath_width = {
                'min': 7.0,
                'max': 11.0,
                'variable': True,
                'dependsOn': ['height', 'speed']
            }
        
        # Sistema de aspersores centrífugos dobles
        self.spread_pattern = {
            'type': 'double centrifugal atomizers',
            'efficiency': 0.95,
            'coverage': 'uniform'
        }
        
        # Batería inteligente DB1560
        self.battery_model = {
            'model': 'DB1560',
            'capacity_mah': 30000,
            'voltage': 22.8,
            'max_discharge_rate': 1.0,
            'temperature_range': {
                'min': -20,
                'max': 45,
                'optimal': 25
            }
        }
        
        # Límites de vuelo operativo
        self.flight_limits = {
            'max_horizontal_speed': 15.0,  # m/s
            'max_vertical_speed': 10.0,  # m/s
            'max_operation_altitude': 3000,  # msnm
            'max_wind_speed': 10.0,  # m/s (límite de viento seguro)
            'min_wind_speed': 1.0,   # m/s (viento mínimo para aplicación)
            'max_tilt_angle': 30,    # grados
        }
        
        # Estado actual
        self.current_payload = 0.0  # kg
        self.current_tank_level = 40.0  # L (llenode fábrica)
        self.target_dose_l_ha = 15.0  # Dosis objetivo en L/ha
        self.is_spraying = False
        self.is_spreading = False
        self.variant = variant
        
    def calculate_flow_rate_for_dose(self, dose_l_ha, speed_ms, swath_m):
        """
        Sincroniza dinámicamente el caudalímetro ultrasónico (L/min)
        para mantener la dosis elegida (L/ha) fija independientemente
        de las variaciones de velocidad de vuelo (m/s).
        Fórmula: Flow (L/min) = (Dose * Speed_ms * Swath_m * 60) / 10000
        """
        if speed_ms <= 0.1 or dose_l_ha <= 0 or swath_m <= 0:
            return 0.0
        
        # Caudal necesario en L/min
        required_flow = (float(dose_l_ha) * float(speed_ms) * float(swath_m) * 60.0) / 10000.0
        
        # Limitar entre caudal mínimo y máximo del modelo de drone
        clamped_flow = max(self.min_spray_flow, min(self.max_spray_flow, required_flow))
        return round(clamped_flow, 2)

    def get_total_mass(self):
        """Calcula la masa total incluyendo carga útil y combustible."""
        # El consumo de combustible/rociante afecta el peso
        fuel_weight = self.current_tank_level  # 1L ≈ 1kg para agua/pesticidas
        return self.mass_empty + fuel_weight + self.current_payload
        
    def update_application(self, flow_rate_l_min, dt):
        """
        Actualiza el nivel del tanque basado en el flujo.
        Retorna la cantidad aplicada en este paso de tiempo.
        """
        if flow_rate_l_min <= 0:
            return 0.0
            
        # Calcular consumo en litros por segundo
        flow_per_sec = flow_rate_l_min / 60.0
        applied_amount = flow_per_sec * dt
        
        # Actualizar tanque
        if self.current_tank_level > 0:
            actual_applied = min(applied_amount, self.current_tank_level)
            self.current_tank_level -= actual_applied
            return actual_applied
        
        return 0.0

    def set_tank_level(self, liters):
        """
        Fija el nivel de caldo a bordo, como en una recarga de campo.
        El valor se limita entre 0 y la capacidad real del tanque (40 L).
        """
        self.current_tank_level = max(
            0.0, min(self.spray_tank_capacity, float(liters))
        )
        return self.current_tank_level

    def get_specs(self):
        """Retorna un diccionario con las especificaciones para el frontend"""
        return {
            "model": "DJI AGRAS T50",
            "arm_spacing_mm": self.arm_spacing,
            "tank_capacity_L": self.spray_tank_capacity,
            "max_spray_flow_L_min": self.max_spray_flow,
            "min_spray_flow_L_min": self.min_spray_flow,
            "effective_swath_m": self.effective_swath_width,
            "battery_model": self.battery_model['model'],
            "battery_capacity_mah": self.battery_model['capacity_mah'],
            "empty_weight_kg": self.mass_empty,
            "max_takeoff_weight_kg": self.max_takeoff_weight,
            "flight_limits": self.flight_limits
        }