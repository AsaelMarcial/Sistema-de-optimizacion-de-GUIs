class EnergyModel:
    """
    Clase para calcular el consumo energético de una GUI en pantallas OLED.
    """
    def __init__(self, coefficients_r, coefficients_g, coefficients_b, constant_c, emission_factor=0.4):
        self.coefficients_r = coefficients_r
        self.coefficients_g = coefficients_g
        self.coefficients_b = coefficients_b
        self.constant_c = constant_c
        self.emission_factor = emission_factor  # Factores de emisión de CO₂ por Wh

    def f(self, R):
        a, b, c, d = self.coefficients_r
        return a * R**3 + b * R**2 + c * R + d if R > 0 else d

    def g(self, G):
        a, b, c, d = self.coefficients_g
        return a * G**3 + b * G**2 + c * G + d if G > 0 else d

    def h(self, B):
        a, b, c, d = self.coefficients_b
        return a * B**3 + b * B**2 + c * B + d if B > 0 else d

    def calculate_power(self, pixel_data, usage_time=1):
        """
        Calcula el consumo energético total basado en los datos de los píxeles.

        Args:
            pixel_data (list): Lista de píxeles {"color": [R, G, B], "count": n}.
            usage_time (float): Tiempo de uso en horas.

        Returns:
            tuple: Consumo energético total (W) y huella de carbono (gr).
        """
        total_pixels = sum(pixel["count"] for pixel in pixel_data)
        total_power = 0

        for pixel in pixel_data:
            R, G, B = pixel["color"]
            count = pixel["count"]
            power_pixel = count * (self.f(R) + self.g(G) + self.h(B))
            total_power += power_pixel

        # Agregar el consumo base por toda la pantalla
        total_power += self.constant_c * total_pixels

        # Convertir a huella de carbono
        total_power_wh = total_power * usage_time
        carbon_footprint = total_power_wh * self.emission_factor

        return total_power, carbon_footprint
