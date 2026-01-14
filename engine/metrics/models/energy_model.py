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

    def f(self, r_value):
        r_linear = self.linear_rgb(r_value)
        a, b, c = self.coefficients_r
        return a * r_linear**3 + b * r_linear**2 + c * r_linear

    def g(self, g_value):
        g_linear = self.linear_rgb(g_value)
        a, b, c = self.coefficients_g
        return a * g_linear**3 + b * g_linear**2 + c * g_linear

    def h(self, b_value):
        b_linear = self.linear_rgb(b_value)
        a, b, c = self.coefficients_b
        return a * b_linear**3 + b * b_linear**2 + c * b_linear

    def calculate_power(self, pixel_data):
        total_power = 0
        for pixel in pixel_data:
            red, green, blue = pixel["color"]
            count = pixel["count"]
            power_pixel = self.f(red) + self.g(green) + self.h(blue)
            total_power += power_pixel * count
        total_power += self.constant_c
        return total_power
