from __future__ import annotations

from typing import Iterable, Iterator, Mapping, Sequence


class EnergyModel:
    """
    Energy consumption model for OLED screens (Pixel 4) based on Dong et al. (2012),
    improved with LinearRGB conversion and real measured data.
    """

    def __init__(
        self,
        coefficients_r: Sequence[float],
        coefficients_g: Sequence[float],
        coefficients_b: Sequence[float],
        constant_c: float,
    ) -> None:
        self.coefficients_r = tuple(float(value) for value in coefficients_r)
        self.coefficients_g = tuple(float(value) for value in coefficients_g)
        self.coefficients_b = tuple(float(value) for value in coefficients_b)
        self.constant_c = float(constant_c)

    @classmethod
    def build(
        cls,
        coefficients_r: Sequence[float],
        coefficients_g: Sequence[float],
        coefficients_b: Sequence[float],
        constant_c: float,
    ) -> "EnergyModel":
        return cls(coefficients_r, coefficients_g, coefficients_b, constant_c)

    def __iter__(self) -> Iterator[tuple[float, float, float]]:
        yield self.coefficients_r
        yield self.coefficients_g
        yield self.coefficients_b

    def linear_rgb(self, value: float) -> float:
        return (value / 255.0) ** 2.2

    def f(self, r_value: float) -> float:
        r_linear = self.linear_rgb(r_value)
        a_value, b_value, c_value = self.coefficients_r
        return a_value * r_linear**3 + b_value * r_linear**2 + c_value * r_linear

    def g(self, g_value: float) -> float:
        g_linear = self.linear_rgb(g_value)
        a_value, b_value, c_value = self.coefficients_g
        return a_value * g_linear**3 + b_value * g_linear**2 + c_value * g_linear

    def h(self, b_value: float) -> float:
        b_linear = self.linear_rgb(b_value)
        a_value, b_coeff, c_value = self.coefficients_b
        return a_value * b_linear**3 + b_coeff * b_linear**2 + c_value * b_linear

    def calculate_power(self, pixel_data: Iterable[Mapping[str, object]]) -> float:
        total_power = 0.0
        for pixel in pixel_data:
            red, green, blue = pixel["color"]  # type: ignore[index]
            count = int(pixel["count"])  # type: ignore[index]
            power_pixel = self.f(float(red)) + self.g(float(green)) + self.h(float(blue))
            total_power += power_pixel * count
        total_power += self.constant_c
        return total_power
