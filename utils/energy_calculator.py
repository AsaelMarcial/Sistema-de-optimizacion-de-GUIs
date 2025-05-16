class EnergyModel:
    """
    Energy consumption model for OLED screens (Pixel 4) based on Dong et al. (2012),
    improved with LinearRGB conversion and real measured data.
    """

    def __init__(self, coefficients_r, coefficients_g, coefficients_b, constant_c):
        self.coefficients_r = coefficients_r  # [a, b, c]
        self.coefficients_g = coefficients_g  # [a, b, c]
        self.coefficients_b = coefficients_b  # [a, b, c]
        self.constant_c = constant_c  # Base consumption (A)

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
    def __init__(self, voltage=3.7, emission_factor=0.000475, reference_reduction=0.5):
        self.voltage = voltage
        self.emission_factor = emission_factor
        self.reference_reduction = reference_reduction

    def calculate(self, current_a, time_hours, num_users, daily_uses):
        energy_wh = current_a * self.voltage * time_hours
        co2eq = energy_wh * self.emission_factor
        co2eq_total = co2eq * num_users
        co2eq_annual_per_user = co2eq * daily_uses * 365
        reference_energy = energy_wh * self.reference_reduction
        sci_score = energy_wh / reference_energy if reference_energy != 0 else float('inf')

        return {
            "energy_wh": energy_wh,
            "co2eq_per_use": co2eq,
            "co2eq_total_users": co2eq_total,
            "co2eq_annual_per_user": co2eq_annual_per_user,
            "sci_score": sci_score
        }
