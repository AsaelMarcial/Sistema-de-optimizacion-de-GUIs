class EnergyModel:
    """
    Energy consumption model for OLED screens (Pixel 4) based on Dong et al. (2012),
    improved with LinearRGB conversion and real measured data.
    """

    def __init__(self, coefficients_r, coefficients_g, coefficients_b, constant_c):
        self.coefficients_r = coefficients_r
        self.coefficients_g = coefficients_g
        self.coefficients_b = coefficients_b
        self.constant_c = constant_c

    def linear_rgb(self, value):
        return (value / 255.0) ** 2.2

    def f(self, R):
        R_linear = self.linear_rgb(R)
        a, b, c = self.coefficients_r
        return a * R_linear**3 + b * R_linear**2 + c * R_linear

    def g(self, G):
        G_linear = self.linear_rgb(G)
        a, b, c = self.coefficients_g
        return a * G_linear**3 + b * G_linear**2 + c * G_linear

    def h(self, B):
        B_linear = self.linear_rgb(B)
        a, b, c = self.coefficients_b
        return a * B_linear**3 + b * B_linear**2 + c * B_linear

    def calculate_power(self, pixel_data):
        total_power = 0
        for pixel in pixel_data:
            R, G, B = pixel["color"]
            count = pixel["count"]
            power_pixel = self.f(R) + self.g(G) + self.h(B)
            total_power += power_pixel * count
        total_power += self.constant_c
        return total_power


class CarbonFootprintCalculator:
    """
    Calculates energy consumption and SCI score using official Green Software Foundation methodology.
    """

    def __init__(self, voltage=3.7, emission_factor=475, hardware_emissions=0):
        self.voltage = voltage
        self.emission_factor = emission_factor
        self.hardware_emissions = hardware_emissions

    def calculate(self, current_a, time_hours, r=1, user_count=100, usage_hours=24):
        # Calcula energía en Wh y kWh
        energy_wh = current_a * self.voltage * time_hours
        energy_kwh = energy_wh / 1000

        # Calcula CO2eq usando el factor de emisión
        co2eq = energy_kwh * self.emission_factor

        # Calcula SCI Score oficial
        sci_score = (co2eq + self.hardware_emissions) / r

        # Nuevos cálculos extendidos
        co2eq_total = co2eq * user_count * usage_hours
        ahorro = 0  # Se calcula externamente comparando con optimizado

        return {
            "energy_wh": energy_wh,
            "energy_kwh": energy_kwh,
            "co2eq_per_use": co2eq,
            "co2eq_total": co2eq_total,
            "sci_score": sci_score,
            "emission_factor": self.emission_factor,
            "user_count": user_count,
            "usage_hours": usage_hours,
            "ahorro_potencial": ahorro
        }