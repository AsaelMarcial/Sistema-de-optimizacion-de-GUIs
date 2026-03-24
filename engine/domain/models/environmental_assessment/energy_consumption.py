from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import ClassVar, Iterable, Iterator, Mapping, Sequence, Self


DEFAULT_COEFFICIENTS_R: tuple[float, float, float] = (
    1.804551146759771e-07,
    -3.0220347704227896e-07,
    1.4154405902803595e-07,
)
DEFAULT_COEFFICIENTS_G: tuple[float, float, float] = (
    9.412383738420182e-08,
    -1.5781520809511624e-07,
    7.546610037732226e-08,
)
DEFAULT_COEFFICIENTS_B: tuple[float, float, float] = (
    1.3946409007268839e-08,
    -2.4495186160412765e-08,
    1.598790315272048e-08,
)
DEFAULT_CONSTANT_C = 0.120833


@dataclass(frozen=True, slots=True)
class EnergyModel:
    """
    Immutable OLED energy profile used by the environmental assessment flow.
    """

    DEFAULT_RED_COEFFICIENTS: ClassVar[tuple[float, float, float]] = DEFAULT_COEFFICIENTS_R
    DEFAULT_GREEN_COEFFICIENTS: ClassVar[tuple[float, float, float]] = DEFAULT_COEFFICIENTS_G
    DEFAULT_BLUE_COEFFICIENTS: ClassVar[tuple[float, float, float]] = DEFAULT_COEFFICIENTS_B
    DEFAULT_CONSTANT_C: ClassVar[float] = DEFAULT_CONSTANT_C

    coefficients_r: tuple[float, float, float]
    coefficients_g: tuple[float, float, float]
    coefficients_b: tuple[float, float, float]
    constant_c: float

    @classmethod
    def build(
        cls,
        coefficients_r: Sequence[float],
        coefficients_g: Sequence[float],
        coefficients_b: Sequence[float],
        constant_c: float,
    ) -> Self:
        return cls(
            coefficients_r=tuple(float(value) for value in coefficients_r),
            coefficients_g=tuple(float(value) for value in coefficients_g),
            coefficients_b=tuple(float(value) for value in coefficients_b),
            constant_c=float(constant_c),
        )

    @classmethod
    def build_default(cls) -> Self:
        return cls.build(
            cls.DEFAULT_RED_COEFFICIENTS,
            cls.DEFAULT_GREEN_COEFFICIENTS,
            cls.DEFAULT_BLUE_COEFFICIENTS,
            cls.DEFAULT_CONSTANT_C,
        )

    def __iter__(self) -> Iterator[tuple[float, float, float]]:
        yield self.coefficients_r
        yield self.coefficients_g
        yield self.coefficients_b

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def linear_rgb(value: float) -> float:
    return (float(value) / 255.0) ** 2.2


def calculate_channel_power(value: float, coefficients: Sequence[float]) -> float:
    channel_value = linear_rgb(value)
    cubic, quadratic, linear = (float(item) for item in coefficients)
    return cubic * channel_value**3 + quadratic * channel_value**2 + linear * channel_value


def calculate_power(
    pixel_data: Iterable[Mapping[str, object]],
    energy_model: EnergyModel,
) -> float:
    total_power = 0.0
    for pixel in pixel_data:
        red, green, blue = pixel["color"]  # type: ignore[index]
        count = int(pixel["count"])  # type: ignore[index]
        pixel_power = (
            calculate_channel_power(float(red), energy_model.coefficients_r)
            + calculate_channel_power(float(green), energy_model.coefficients_g)
            + calculate_channel_power(float(blue), energy_model.coefficients_b)
        )
        total_power += pixel_power * count
    return total_power + energy_model.constant_c


def estimate_current(
    pixel_data: Iterable[Mapping[str, object]],
    energy_model: EnergyModel,
) -> float:
    return calculate_power(pixel_data, energy_model)
