from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class MaterialQuantizationAssessment:
    recommended: bool
    summary: str
    resize_before_quantization: bool
    recommended_size: tuple[int, int]
    recommended_quantizer: str
    recommended_max_colors: int
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def get_material_quantization_assessment() -> MaterialQuantizationAssessment:
    return MaterialQuantizationAssessment(
        recommended=True,
        summary=(
            "La cuantización tipo Material Color Utilities sí aplica, pero no debe ejecutarse sobre "
            "la captura completa sin filtrado previo."
        ),
        resize_before_quantization=True,
        recommended_size=(128, 128),
        recommended_quantizer="QuantizerCelebi (Wu + Wsmeans)",
        recommended_max_colors=128,
        notes=(
            "La guía de MCU reduce la imagen a 128x128 antes de cuantizar para acelerar el proceso.",
            "QuantizerCelebi usa Wu para semillas iniciales y Wsmeans para refinar clusters estables.",
            "Para reconstruir la paleta del diseño conviene excluir ruido visual: fotos, video, gifs y sombras decorativas.",
            "La estimación energética puede seguir usando la captura completa; la reconstrucción de paleta debe usar una entrada filtrada o una segunda captura especializada.",
        ),
    )
