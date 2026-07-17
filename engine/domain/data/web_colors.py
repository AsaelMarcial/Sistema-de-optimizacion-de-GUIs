from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Iterable

from engine.adapters.color_service import color_registry

WEB_COLOR_SOURCE_TITLE = "Web colors - Wikipedia"
WEB_COLOR_MATCH_METHOD = "2000"


class MultiValueEnum(Enum):
    def __new__(cls, value: Any, *values: Any):
        obj = object.__new__(cls)
        obj._value_ = value
        for alias in values:
            obj._add_value_alias_(alias)
        return obj


class WebColorGroup(StrEnum):
    display_name: str

    def __new__(cls, value: str, display_name: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.display_name = display_name
        return obj

    COLORES_ROJOS = ('Rojo', 'Red')
    COLORES_NARANJAS = ('Naranja', 'Orange')
    COLORES_MARRONES = ('Marrón', 'Brown')
    COLORES_AMARILLOS = ('Amarillo', 'Yellow')
    COLORES_VERDES_AMARILLOS = ('Verde amarillo', 'Lime')
    COLORES_VERDES = ('Verde', 'Green')
    COLORES_ACIANOS_AZUL_VERDES = ('Aciano azul verde', 'Turquoise')
    COLORES_AZULES = ('Azul', 'Blue')
    COLORES_VIOLETAS_Y_PURPURAS = ('Violeta', 'Violet')
    COLORES_ROSAS = ('Rosa', 'Fuchsia / Magenta')
    COLORES_BLANCOS = ('Blanco', 'White')
    COLORES_GRISES = ('Grises', 'Gray')


@dataclass(frozen=True, slots=True)
class WebColorMatch:
    color_name: str
    display_name: str
    group_name: str
    hex_code: str
    rgb: tuple[int, int, int]
    distance: float
    method: str = WEB_COLOR_MATCH_METHOD

    @property
    def wikipedia_family(self) -> str:
        return self.group_name

    @property
    def family_display_name(self) -> str:
        try:
            return WebColorGroup(self.group_name).display_name
        except ValueError:
            return self.display_name

    @property
    def hex_value(self) -> str:
        return f"#{self.hex_code.lower().lstrip('#')}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "color_name": self.color_name,
            "display_name": self.display_name,
            "group_name": self.group_name,
            "hex_code": self.hex_code,
            "rgb": list(self.rgb),
            "distance": round(self.distance, 4),
            "method": self.method,
        }


class WebColor(MultiValueEnum):
    def __new__(
        cls,
        canonical_name: str,
        aliases: tuple[Any, ...],
        html_names: tuple[str, ...],
        group: WebColorGroup,
        hex_code: str,
        rgb: tuple[int, int, int],
        hsl: tuple[int | None, int | None, int],
        hsv: tuple[int | None, int | None, int],
    ):
        obj = object.__new__(cls)
        obj._value_ = canonical_name
        for alias in aliases:
            if alias != canonical_name:
                obj._add_value_alias_(alias)
        obj.canonical_name = canonical_name
        obj.html_names = html_names
        obj.group = group
        obj.hex_code = hex_code
        obj.rgb = rgb
        obj.hsl = hsl
        obj.hsv = hsv
        return obj

    @property
    def display_name(self) -> str:
        return " / ".join(self.html_names)

    @property
    def hex_value(self) -> str:
        return f"#{self.hex_code.lower()}"

    @property
    def wikipedia_family(self) -> str:
        return self.group.value

    @property
    def family_display_name(self) -> str:
        return self.group.display_name

    @property
    def value_map(self) -> dict[str, object]:
        return {
            "canonical_name": self.canonical_name,
            "display_name": self.display_name,
            "html_names": tuple(self.html_names),
            "group": self.wikipedia_family,
            "hex": self.hex_value,
            "rgb": tuple(self.rgb),
            "hsl": tuple(self.hsl),
            "hsv": tuple(self.hsv),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "enum_name": self.name,
            "canonical_name": self.canonical_name,
            "display_name": self.display_name,
            "html_names": list(self.html_names),
            "group_name": self.group.value,
            "hex_code": self.hex_code,
            "rgb": list(self.rgb),
            "hsl": list(self.hsl),
            "hsv": list(self.hsv),
        }

    @classmethod
    def _missing_(cls, value: Any):
        if isinstance(value, str):
            raw = value.strip()
            candidates = (
                raw,
                raw.lower(),
                raw.upper(),
                raw.replace(" ", ""),
                raw.replace(" ", "").lower(),
                raw.lstrip("#").upper(),
                raw.lstrip("#").lower(),
                f"#{raw.lstrip("#").upper()}",
                f"#{raw.lstrip("#").lower()}",
            )
            for candidate in candidates:
                member = cls._value2member_map_.get(candidate)
                if member is not None:
                    return member
            member = cls.__members__.get(raw.upper())
            if member is not None:
                return member
        return None

    LIGHT_CORAL = (
        'lightcoral',
        ('LightCoral', 'lightcoral', 'Light Coral', 'F08080', 'f08080', '#F08080', '#f08080', (240, 128, 128)),
        ('LightCoral',),
        WebColorGroup.COLORES_ROJOS,
        'F08080',
        (240, 128, 128),
        (0, 79, 72),
        (0, 47, 94),
    )
    SALMON = (
        'salmon',
        ('Salmon', 'salmon', 'FA8072', 'fa8072', '#FA8072', '#fa8072', (250, 128, 114)),
        ('Salmon',),
        WebColorGroup.COLORES_ROJOS,
        'FA8072',
        (250, 128, 114),
        (6, 93, 71),
        (6, 55, 98),
    )
    INDIAN_RED = (
        'indianred',
        ('IndianRed', 'indianred', 'Indian Red', 'CD5C5C', 'cd5c5c', '#CD5C5C', '#cd5c5c', (205, 92, 92)),
        ('IndianRed',),
        WebColorGroup.COLORES_ROJOS,
        'CD5C5C',
        (205, 92, 92),
        (0, 53, 58),
        (0, 55, 80),
    )
    RED = (
        'red',
        ('Red', 'red', 'FF0000', 'ff0000', '#FF0000', '#ff0000', (255, 0, 0)),
        ('Red',),
        WebColorGroup.COLORES_ROJOS,
        'FF0000',
        (255, 0, 0),
        (0, 100, 50),
        (0, 100, 100),
    )
    CRIMSON = (
        'crimson',
        ('Crimson', 'crimson', 'DC143C', 'dc143c', '#DC143C', '#dc143c', (220, 20, 60)),
        ('Crimson',),
        WebColorGroup.COLORES_ROJOS,
        'DC143C',
        (220, 20, 60),
        (348, 83, 47),
        (348, 91, 86),
    )
    FIRE_BRICK = (
        'firebrick',
        ('FireBrick', 'firebrick', 'Fire Brick', 'B22222', 'b22222', '#B22222', '#b22222', (178, 34, 34)),
        ('FireBrick',),
        WebColorGroup.COLORES_ROJOS,
        'B22222',
        (178, 34, 34),
        (0, 68, 42),
        (0, 81, 71),
    )
    BROWN = (
        'brown',
        ('Brown', 'brown', 'A52A2A', 'a52a2a', '#A52A2A', '#a52a2a', (165, 42, 42)),
        ('Brown',),
        WebColorGroup.COLORES_ROJOS,
        'A52A2A',
        (165, 42, 42),
        (0, 75, 65),
        (0, 58, 91),
    )
    DARK_RED = (
        'darkred',
        ('DarkRed', 'darkred', 'Dark Red', '8B0000', '8b0000', '#8B0000', '#8b0000', (139, 0, 0)),
        ('DarkRed',),
        WebColorGroup.COLORES_ROJOS,
        '8B0000',
        (139, 0, 0),
        (0, 100, 27),
        (0, 100, 54),
    )
    MAROON = (
        'maroon',
        ('Maroon', 'maroon', '800000', '#800000', (128, 0, 0)),
        ('Maroon',),
        WebColorGroup.COLORES_ROJOS,
        '800000',
        (128, 0, 0),
        (0, 100, 25),
        (0, 100, 50),
    )
    PAPAYA_WHIP = (
        'papayawhip',
        ('PapayaWhip', 'papayawhip', 'Papaya Whip', 'FFEFD5', 'ffefd5', '#FFEFD5', '#ffefd5', (255, 239, 213)),
        ('PapayaWhip',),
        WebColorGroup.COLORES_NARANJAS,
        'FFEFD5',
        (255, 239, 213),
        (37, 100, 92),
        (37, 16, 100),
    )
    BLANCHED_ALMOND = (
        'blanchedalmond',
        ('BlanchedAlmond', 'blanchedalmond', 'Blanched Almond', 'FFEBCD', 'ffebcd', '#FFEBCD', '#ffebcd', (255, 235, 205)),
        ('BlanchedAlmond',),
        WebColorGroup.COLORES_NARANJAS,
        'FFEBCD',
        (255, 235, 205),
        (36, 100, 90),
        (36, 20, 100),
    )
    BISQUE = (
        'bisque',
        ('Bisque', 'bisque', 'FFE4C4', 'ffe4c4', '#FFE4C4', '#ffe4c4', (255, 228, 196)),
        ('Bisque',),
        WebColorGroup.COLORES_NARANJAS,
        'FFE4C4',
        (255, 228, 196),
        (33, 100, 88),
        (33, 24, 100),
    )
    MOCCASIN = (
        'moccasin',
        ('Moccasin', 'moccasin', 'FFE4B5', 'ffe4b5', '#FFE4B5', '#ffe4b5', (255, 228, 181)),
        ('Moccasin',),
        WebColorGroup.COLORES_NARANJAS,
        'FFE4B5',
        (255, 228, 181),
        (38, 100, 85),
        (38, 30, 100),
    )
    PEACH_PUFF = (
        'peachpuff',
        ('PeachPuff', 'peachpuff', 'Peach Puff', 'FFDAB9', 'ffdab9', '#FFDAB9', '#ffdab9', (255, 218, 185)),
        ('PeachPuff',),
        WebColorGroup.COLORES_NARANJAS,
        'FFDAB9',
        (255, 218, 185),
        (28, 100, 86),
        (28, 28, 100),
    )
    NAVAJO_WHITE = (
        'navajowhite',
        ('NavajoWhite', 'navajowhite', 'Navajo White', 'FFDEAD', 'ffdead', '#FFDEAD', '#ffdead', (255, 222, 173)),
        ('NavajoWhite',),
        WebColorGroup.COLORES_NARANJAS,
        'FFDEAD',
        (255, 222, 173),
        (36, 100, 84),
        (36, 32, 100),
    )
    LIGHT_SALMON = (
        'lightsalmon',
        ('LightSalmon', 'lightsalmon', 'Light Salmon', 'FFA07A', 'ffa07a', '#FFA07A', '#ffa07a', (255, 160, 122)),
        ('LightSalmon',),
        WebColorGroup.COLORES_NARANJAS,
        'FFA07A',
        (255, 160, 122),
        (17, 100, 74),
        (17, 52, 100),
    )
    DARK_SALMON = (
        'darksalmon',
        ('DarkSalmon', 'darksalmon', 'Dark Salmon', 'E9967A', 'e9967a', '#E9967A', '#e9967a', (233, 150, 122)),
        ('DarkSalmon',),
        WebColorGroup.COLORES_NARANJAS,
        'E9967A',
        (233, 150, 122),
        (15, 72, 70),
        (15, 47, 92),
    )
    ORANGE = (
        'orange',
        ('Orange', 'orange', 'FFA500', 'ffa500', '#FFA500', '#ffa500', (255, 165, 0)),
        ('Orange',),
        WebColorGroup.COLORES_NARANJAS,
        'FFA500',
        (255, 165, 0),
        (39, 100, 50),
        (39, 100, 100),
    )
    DARK_ORANGE = (
        'darkorange',
        ('DarkOrange', 'darkorange', 'Dark Orange', 'FF8C00', 'ff8c00', '#FF8C00', '#ff8c00', (255, 140, 0)),
        ('DarkOrange',),
        WebColorGroup.COLORES_NARANJAS,
        'FF8C00',
        (255, 140, 0),
        (33, 100, 50),
        (33, 100, 100),
    )
    CORAL = (
        'coral',
        ('Coral', 'coral', 'FF7F50', 'ff7f50', '#FF7F50', '#ff7f50', (255, 127, 80)),
        ('Coral',),
        WebColorGroup.COLORES_NARANJAS,
        'FF7F50',
        (255, 127, 80),
        (16, 100, 66),
        (16, 68, 100),
    )
    TOMATO = (
        'tomato',
        ('Tomato', 'tomato', 'FF6347', 'ff6347', '#FF6347', '#ff6347', (255, 99, 71)),
        ('Tomato',),
        WebColorGroup.COLORES_NARANJAS,
        'FF6347',
        (255, 99, 71),
        (9, 100, 64),
        (9, 72, 100),
    )
    ORANGE_RED = (
        'orangered',
        ('OrangeRed', 'orangered', 'Orange Red', 'FF4500', 'ff4500', '#FF4500', '#ff4500', (255, 69, 0)),
        ('OrangeRed',),
        WebColorGroup.COLORES_NARANJAS,
        'FF4500',
        (255, 69, 0),
        (16, 100, 50),
        (16, 100, 100),
    )
    WHEAT = (
        'wheat',
        ('Wheat', 'wheat', 'F5DEB3', 'f5deb3', '#F5DEB3', '#f5deb3', (245, 222, 179)),
        ('Wheat',),
        WebColorGroup.COLORES_MARRONES,
        'F5DEB3',
        (245, 222, 179),
        (39, 77, 83),
        (39, 27, 96),
    )
    BURLY_WOOD = (
        'burlywood',
        ('BurlyWood', 'burlywood', 'Burly Wood', 'DEB887', 'deb887', '#DEB887', '#deb887', (222, 184, 135)),
        ('BurlyWood',),
        WebColorGroup.COLORES_MARRONES,
        'DEB887',
        (222, 184, 135),
        (34, 57, 70),
        (34, 39, 87),
    )
    TAN = (
        'tan',
        ('Tan', 'tan', 'D2B48C', 'd2b48c', '#D2B48C', '#d2b48c', (210, 180, 140)),
        ('Tan',),
        WebColorGroup.COLORES_MARRONES,
        'D2B48C',
        (210, 180, 140),
        (34, 44, 69),
        (34, 33, 83),
    )
    SANDY_BROWN = (
        'sandybrown',
        ('SandyBrown', 'sandybrown', 'Sandy Brown', 'F4A460', 'f4a460', '#F4A460', '#f4a460', (244, 164, 96)),
        ('SandyBrown',),
        WebColorGroup.COLORES_MARRONES,
        'F4A460',
        (244, 164, 96),
        (28, 87, 67),
        (28, 60, 96),
    )
    GOLDENROD = (
        'goldenrod',
        ('Goldenrod', 'goldenrod', 'DAA520', 'daa520', '#DAA520', '#daa520', (218, 165, 32)),
        ('Goldenrod',),
        WebColorGroup.COLORES_MARRONES,
        'DAA520',
        (218, 165, 32),
        (43, 74, 49),
        (43, 85, 85),
    )
    PERU = (
        'peru',
        ('Peru', 'peru', 'CD853F', 'cd853f', '#CD853F', '#cd853f', (205, 133, 63)),
        ('Peru',),
        WebColorGroup.COLORES_MARRONES,
        'CD853F',
        (205, 133, 63),
        (30, 59, 53),
        (30, 69, 81),
    )
    DARK_GOLDENROD = (
        'darkgoldenrod',
        ('DarkGoldenrod', 'darkgoldenrod', 'Dark Goldenrod', 'B8860B', 'b8860b', '#B8860B', '#b8860b', (184, 134, 11)),
        ('DarkGoldenrod',),
        WebColorGroup.COLORES_MARRONES,
        'B8860B',
        (184, 134, 11),
        (43, 89, 38),
        (43, 94, 72),
    )
    CHOCOLATE = (
        'chocolate',
        ('Chocolate', 'chocolate', 'D2691E', 'd2691e', '#D2691E', '#d2691e', (210, 105, 30)),
        ('Chocolate',),
        WebColorGroup.COLORES_MARRONES,
        'D2691E',
        (210, 105, 30),
        (25, 75, 47),
        (25, 86, 82),
    )
    SIENNA = (
        'sienna',
        ('Sienna', 'sienna', 'A0522D', 'a0522d', '#A0522D', '#a0522d', (160, 82, 45)),
        ('Sienna',),
        WebColorGroup.COLORES_MARRONES,
        'A0522D',
        (160, 82, 45),
        (19, 56, 40),
        (19, 72, 62),
    )
    SADDLE_BROWN = (
        'saddlebrown',
        ('SaddleBrown', 'saddlebrown', 'Saddle Brown', '8B4513', '8b4513', '#8B4513', '#8b4513', (139, 69, 19)),
        ('SaddleBrown',),
        WebColorGroup.COLORES_MARRONES,
        '8B4513',
        (139, 69, 19),
        (25, 76, 31),
        (25, 86, 55),
    )
    LIGHT_YELLOW = (
        'lightyellow',
        ('LightYellow', 'lightyellow', 'Light Yellow', 'FFFFE0', 'ffffe0', '#FFFFE0', '#ffffe0', (255, 255, 224)),
        ('LightYellow',),
        WebColorGroup.COLORES_AMARILLOS,
        'FFFFE0',
        (255, 255, 224),
        (60, 100, 94),
        (60, 12, 100),
    )
    CORNSILK = (
        'cornsilk',
        ('Cornsilk', 'cornsilk', 'FFF8DC', 'fff8dc', '#FFF8DC', '#fff8dc', (255, 248, 220)),
        ('Cornsilk',),
        WebColorGroup.COLORES_AMARILLOS,
        'FFF8DC',
        (255, 248, 220),
        (48, 100, 93),
        (48, 14, 100),
    )
    LEMON_CHIFFON = (
        'lemonchiffon',
        ('LemonChiffon', 'lemonchiffon', 'Lemon Chiffon', 'FFFACD', 'fffacd', '#FFFACD', '#fffacd', (255, 250, 205)),
        ('LemonChiffon',),
        WebColorGroup.COLORES_AMARILLOS,
        'FFFACD',
        (255, 250, 205),
        (54, 100, 90),
        (54, 20, 100),
    )
    LIGHT_GOLDENROD_YELLOW = (
        'lightgoldenrodyellow',
        ('LightGoldenrodYellow', 'lightgoldenrodyellow', 'Light Goldenrod Yellow', 'FAFAD2', 'fafad2', '#FAFAD2', '#fafad2', (250, 250, 210)),
        ('LightGoldenrodYellow',),
        WebColorGroup.COLORES_AMARILLOS,
        'FAFAD2',
        (250, 250, 210),
        (60, 80, 90),
        (60, 16, 98),
    )
    PALE_GOLDENROD = (
        'palegoldenrod',
        ('PaleGoldenrod', 'palegoldenrod', 'Pale Goldenrod', 'EEE8AA', 'eee8aa', '#EEE8AA', '#eee8aa', (238, 232, 170)),
        ('PaleGoldenrod',),
        WebColorGroup.COLORES_AMARILLOS,
        'EEE8AA',
        (238, 232, 170),
        (55, 67, 80),
        (55, 29, 93),
    )
    KHAKI = (
        'khaki',
        ('Khaki', 'khaki', 'F0E68C', 'f0e68c', '#F0E68C', '#f0e68c', (240, 230, 140)),
        ('Khaki',),
        WebColorGroup.COLORES_AMARILLOS,
        'F0E68C',
        (240, 230, 140),
        (54, 77, 75),
        (54, 41, 94),
    )
    YELLOW = (
        'yellow',
        ('Yellow', 'yellow', 'FFFF00', 'ffff00', '#FFFF00', '#ffff00', (255, 255, 0)),
        ('Yellow',),
        WebColorGroup.COLORES_AMARILLOS,
        'FFFF00',
        (255, 255, 0),
        (60, 100, 50),
        (60, 100, 100),
    )
    GOLD = (
        'gold',
        ('Gold', 'gold', 'FFD700', 'ffd700', '#FFD700', '#ffd700', (255, 215, 0)),
        ('Gold',),
        WebColorGroup.COLORES_AMARILLOS,
        'FFD700',
        (255, 215, 0),
        (51, 100, 50),
        (51, 100, 100),
    )
    DARK_KHAKI = (
        'darkkhaki',
        ('DarkKhaki', 'darkkhaki', 'Dark Khaki', 'BDB76B', 'bdb76b', '#BDB76B', '#bdb76b', (189, 183, 107)),
        ('DarkKhaki',),
        WebColorGroup.COLORES_AMARILLOS,
        'BDB76B',
        (189, 183, 107),
        (56, 38, 58),
        (56, 43, 74),
    )
    OLIVE = (
        'olive',
        ('Olive', 'olive', '808000', '#808000', (128, 128, 0)),
        ('Olive',),
        WebColorGroup.COLORES_AMARILLOS,
        '808000',
        (128, 128, 0),
        (60, 100, 25),
        (60, 100, 50),
    )
    GREEN_YELLOW = (
        'greenyellow',
        ('GreenYellow', 'greenyellow', 'Green Yellow', 'ADFF2F', 'adff2f', '#ADFF2F', '#adff2f', (173, 255, 47)),
        ('GreenYellow',),
        WebColorGroup.COLORES_VERDES_AMARILLOS,
        'ADFF2F',
        (173, 255, 47),
        (84, 100, 59),
        (84, 82, 100),
    )
    CHARTREUSE = (
        'chartreuse',
        ('Chartreuse', 'chartreuse', '7FFF00', '7fff00', '#7FFF00', '#7fff00', (127, 255, 0)),
        ('Chartreuse',),
        WebColorGroup.COLORES_VERDES_AMARILLOS,
        '7FFF00',
        (127, 255, 0),
        (90, 100, 50),
        (90, 100, 100),
    )
    LAWN_GREEN = (
        'lawngreen',
        ('LawnGreen', 'lawngreen', 'Lawn Green', '7CFC00', '7cfc00', '#7CFC00', '#7cfc00', (124, 252, 0)),
        ('LawnGreen',),
        WebColorGroup.COLORES_VERDES_AMARILLOS,
        '7CFC00',
        (124, 252, 0),
        (90, 100, 49),
        (90, 100, 98),
    )
    YELLOW_GREEN = (
        'yellowgreen',
        ('YellowGreen', 'yellowgreen', 'Yellow Green', '9ACD32', '9acd32', '#9ACD32', '#9acd32', (154, 205, 50)),
        ('YellowGreen',),
        WebColorGroup.COLORES_VERDES_AMARILLOS,
        '9ACD32',
        (154, 205, 50),
        (80, 61, 50),
        (80, 76, 81),
    )
    OLIVE_DRAB = (
        'olivedrab',
        ('OliveDrab', 'olivedrab', 'Olive Drab', '6B8E23', '6b8e23', '#6B8E23', '#6b8e23', (107, 142, 35)),
        ('OliveDrab',),
        WebColorGroup.COLORES_VERDES_AMARILLOS,
        '6B8E23',
        (107, 142, 35),
        (80, 60, 35),
        (80, 75, 56),
    )
    DARK_OLIVE_GREEN = (
        'darkolivegreen',
        ('DarkOliveGreen', 'darkolivegreen', 'Dark Olive Green', '556B2F', '556b2f', '#556B2F', '#556b2f', (85, 107, 47)),
        ('DarkOliveGreen',),
        WebColorGroup.COLORES_VERDES_AMARILLOS,
        '556B2F',
        (85, 107, 47),
        (82, 39, 30),
        (82, 56, 42),
    )
    PALE_GREEN = (
        'palegreen',
        ('PaleGreen', 'palegreen', 'Pale Green', '98FB98', '98fb98', '#98FB98', '#98fb98', (152, 251, 152)),
        ('PaleGreen',),
        WebColorGroup.COLORES_VERDES,
        '98FB98',
        (152, 251, 152),
        (120, 93, 79),
        (120, 40, 99),
    )
    LIGHT_GREEN = (
        'lightgreen',
        ('LightGreen', 'lightgreen', 'Light Green', '90EE90', '90ee90', '#90EE90', '#90ee90', (144, 238, 144)),
        ('LightGreen',),
        WebColorGroup.COLORES_VERDES,
        '90EE90',
        (144, 238, 144),
        (120, 73, 75),
        (120, 39, 93),
    )
    MEDIUM_SPRING_GREEN = (
        'mediumspringgreen',
        ('MediumSpringGreen', 'mediumspringgreen', 'Medium Spring Green', '00FA9A', '00fa9a', '#00FA9A', '#00fa9a', (0, 250, 154)),
        ('MediumSpringGreen',),
        WebColorGroup.COLORES_VERDES,
        '00FA9A',
        (0, 250, 154),
        (157, 100, 49),
        (157, 100, 98),
    )
    SPRING_GREEN = (
        'springgreen',
        ('SpringGreen', 'springgreen', 'Spring Green', '00FF7F', '00ff7f', '#00FF7F', '#00ff7f', (0, 255, 127)),
        ('SpringGreen',),
        WebColorGroup.COLORES_VERDES,
        '00FF7F',
        (0, 255, 127),
        (150, 100, 50),
        (150, 100, 100),
    )
    LIME = (
        'lime',
        ('Lime', 'lime', '00FF00', '00ff00', '#00FF00', '#00ff00', (0, 255, 0)),
        ('Lime',),
        WebColorGroup.COLORES_VERDES,
        '00FF00',
        (0, 255, 0),
        (120, 100, 50),
        (120, 100, 100),
    )
    DARK_SEA_GREEN = (
        'darkseagreen',
        ('DarkSeaGreen', 'darkseagreen', 'Dark Sea Green', '8FBC8F', '8fbc8f', '#8FBC8F', '#8fbc8f', (143, 188, 143)),
        ('DarkSeaGreen',),
        WebColorGroup.COLORES_VERDES,
        '8FBC8F',
        (143, 188, 143),
        (120, 25, 65),
        (120, 24, 74),
    )
    LIME_GREEN = (
        'limegreen',
        ('LimeGreen', 'limegreen', 'Lime Green', '32CD32', '32cd32', '#32CD32', '#32cd32', (50, 205, 50)),
        ('LimeGreen',),
        WebColorGroup.COLORES_VERDES,
        '32CD32',
        (50, 205, 50),
        (120, 61, 50),
        (120, 76, 81),
    )
    MEDIUM_SEA_GREEN = (
        'mediumseagreen',
        ('MediumSeaGreen', 'mediumseagreen', 'Medium Sea Green', '3CB371', '3cb371', '#3CB371', '#3cb371', (60, 179, 113)),
        ('MediumSeaGreen',),
        WebColorGroup.COLORES_VERDES,
        '3CB371',
        (60, 179, 113),
        (147, 50, 47),
        (147, 67, 71),
    )
    SEA_GREEN = (
        'seagreen',
        ('SeaGreen', 'seagreen', 'Sea Green', '2E8B57', '2e8b57', '#2E8B57', '#2e8b57', (46, 139, 87)),
        ('SeaGreen',),
        WebColorGroup.COLORES_VERDES,
        '2E8B57',
        (46, 139, 87),
        (146, 50, 36),
        (146, 67, 54),
    )
    FOREST_GREEN = (
        'forestgreen',
        ('ForestGreen', 'forestgreen', 'Forest Green', '228B22', '228b22', '#228B22', '#228b22', (34, 139, 34)),
        ('ForestGreen',),
        WebColorGroup.COLORES_VERDES,
        '228B22',
        (34, 139, 34),
        (120, 61, 34),
        (120, 76, 55),
    )
    GREEN = (
        'green',
        ('Green', 'green', '008000', '#008000', (0, 128, 0)),
        ('Green',),
        WebColorGroup.COLORES_VERDES,
        '008000',
        (0, 128, 0),
        (120, 100, 25),
        (120, 100, 50),
    )
    DARK_GREEN = (
        'darkgreen',
        ('DarkGreen', 'darkgreen', 'Dark Green', '006400', '#006400', (0, 100, 0)),
        ('DarkGreen',),
        WebColorGroup.COLORES_VERDES,
        '006400',
        (0, 100, 0),
        (120, 100, 20),
        (120, 100, 40),
    )
    LIGHT_CYAN = (
        'lightcyan',
        ('LightCyan', 'lightcyan', 'Light Cyan', 'E0FFFF', 'e0ffff', '#E0FFFF', '#e0ffff', (224, 255, 255)),
        ('LightCyan',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        'E0FFFF',
        (224, 255, 255),
        (180, 100, 94),
        (180, 12, 100),
    )
    PALE_TURQUOISE = (
        'paleturquoise',
        ('PaleTurquoise', 'paleturquoise', 'Pale Turquoise', 'AFEEEE', 'afeeee', '#AFEEEE', '#afeeee', (175, 238, 238)),
        ('PaleTurquoise',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        'AFEEEE',
        (175, 238, 238),
        (180, 65, 81),
        (180, 26, 93),
    )
    AQUAMARINE = (
        'aquamarine',
        ('Aquamarine', 'aquamarine', '7FFFD4', '7fffd4', '#7FFFD4', '#7fffd4', (127, 255, 212)),
        ('Aquamarine',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '7FFFD4',
        (127, 255, 212),
        (160, 100, 75),
        (160, 50, 100),
    )
    AQUA = (
        'aqua',
        ('Aqua', 'aqua', 'Cyan', 'cyan', 'Aqua / Cyan', 'aqua / cyan', '00FFFF', '00ffff', '#00FFFF', '#00ffff', (0, 255, 255)),
        ('Aqua', 'Cyan'),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '00FFFF',
        (0, 255, 255),
        (180, 100, 50),
        (180, 100, 100),
    )
    TURQUOISE = (
        'turquoise',
        ('Turquoise', 'turquoise', '40E0D0', '40e0d0', '#40E0D0', '#40e0d0', (64, 224, 208)),
        ('Turquoise',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '40E0D0',
        (64, 224, 208),
        (174, 72, 56),
        (174, 72, 88),
    )
    MEDIUM_TURQUOISE = (
        'mediumturquoise',
        ('MediumTurquoise', 'mediumturquoise', 'Medium Turquoise', '48D1CC', '48d1cc', '#48D1CC', '#48d1cc', (72, 209, 204)),
        ('MediumTurquoise',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '48D1CC',
        (72, 209, 204),
        (178, 60, 55),
        (178, 66, 82),
    )
    DARK_TURQUOISE = (
        'darkturquoise',
        ('DarkTurquoise', 'darkturquoise', 'Dark Turquoise', '00CED1', '00ced1', '#00CED1', '#00ced1', (0, 206, 209)),
        ('DarkTurquoise',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '00CED1',
        (0, 206, 209),
        (181, 100, 82),
        (181, 36, 100),
    )
    MEDIUM_AQUAMARINE = (
        'mediumaquamarine',
        ('MediumAquamarine', 'mediumaquamarine', 'Medium Aquamarine', '66CDAA', '66cdaa', '#66CDAA', '#66cdaa', (102, 205, 170)),
        ('MediumAquamarine',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '66CDAA',
        (102, 205, 170),
        (160, 51, 60),
        (160, 51, 80),
    )
    LIGHT_SEA_GREEN = (
        'lightseagreen',
        ('LightSeaGreen', 'lightseagreen', 'Light Sea Green', '20B2AA', '20b2aa', '#20B2AA', '#20b2aa', (32, 178, 170)),
        ('LightSeaGreen',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '20B2AA',
        (32, 178, 170),
        (177, 70, 41),
        (177, 82, 70),
    )
    CADET_BLUE = (
        'cadetblue',
        ('CadetBlue', 'cadetblue', 'Cadet Blue', '5F9EA0', '5f9ea0', '#5F9EA0', '#5f9ea0', (95, 158, 160)),
        ('CadetBlue',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '5F9EA0',
        (95, 158, 160),
        (182, 41, 63),
        (182, 39, 78),
    )
    DARK_CYAN = (
        'darkcyan',
        ('DarkCyan', 'darkcyan', 'Dark Cyan', '008B8B', '008b8b', '#008B8B', '#008b8b', (0, 139, 139)),
        ('DarkCyan',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '008B8B',
        (0, 139, 139),
        (180, 100, 27),
        (180, 100, 54),
    )
    TEAL = (
        'teal',
        ('Teal', 'teal', '008080', '#008080', (0, 128, 128)),
        ('Teal',),
        WebColorGroup.COLORES_ACIANOS_AZUL_VERDES,
        '008080',
        (0, 128, 128),
        (180, 100, 25),
        (180, 100, 50),
    )
    LAVENDER = (
        'lavender',
        ('Lavender', 'lavender', 'E6E6FA', 'e6e6fa', '#E6E6FA', '#e6e6fa', (230, 230, 250)),
        ('Lavender',),
        WebColorGroup.COLORES_AZULES,
        'E6E6FA',
        (230, 230, 250),
        (240, 67, 94),
        (240, 8, 98),
    )
    BLUE_WEB = (
        'blueweb',
        ('BlueWeb', 'blueweb', 'Blue Web', 'CEE7FF', 'cee7ff', '#CEE7FF', '#cee7ff', (206, 231, 255)),
        ('BlueWeb',),
        WebColorGroup.COLORES_AZULES,
        'CEE7FF',
        (206, 231, 255),
        (209, 100, 90),
        (209, 20, 100),
    )
    POWDER_BLUE = (
        'powderblue',
        ('PowderBlue', 'powderblue', 'Powder Blue', 'B0E0E6', 'b0e0e6', '#B0E0E6', '#b0e0e6', (176, 224, 230)),
        ('PowderBlue',),
        WebColorGroup.COLORES_AZULES,
        'B0E0E6',
        (176, 224, 230),
        (187, 52, 80),
        (187, 23, 90),
    )
    LIGHT_BLUE = (
        'lightblue',
        ('LightBlue', 'lightblue', 'Light Blue', 'ADD8E6', 'add8e6', '#ADD8E6', '#add8e6', (173, 216, 230)),
        ('LightBlue',),
        WebColorGroup.COLORES_AZULES,
        'ADD8E6',
        (173, 216, 230),
        (195, 53, 79),
        (195, 25, 90),
    )
    LIGHT_SKY_BLUE = (
        'lightskyblue',
        ('LightSkyBlue', 'lightskyblue', 'Light Sky Blue', '87CEFA', '87cefa', '#87CEFA', '#87cefa', (135, 206, 250)),
        ('LightSkyBlue',),
        WebColorGroup.COLORES_AZULES,
        '87CEFA',
        (135, 206, 250),
        (203, 92, 75),
        (203, 47, 98),
    )
    SKY_BLUE = (
        'skyblue',
        ('SkyBlue', 'skyblue', 'Sky Blue', '87CEEB', '87ceeb', '#87CEEB', '#87ceeb', (135, 206, 235)),
        ('SkyBlue',),
        WebColorGroup.COLORES_AZULES,
        '87CEEB',
        (135, 206, 235),
        (197, 71, 73),
        (197, 42, 92),
    )
    LIGHT_STEEL_BLUE = (
        'lightsteelblue',
        ('LightSteelBlue', 'lightsteelblue', 'Light Steel Blue', 'B0C4DE', 'b0c4de', '#B0C4DE', '#b0c4de', (176, 196, 222)),
        ('LightSteelBlue',),
        WebColorGroup.COLORES_AZULES,
        'B0C4DE',
        (176, 196, 222),
        (214, 41, 78),
        (214, 21, 87),
    )
    DEEP_SKY_BLUE = (
        'deepskyblue',
        ('DeepSkyBlue', 'deepskyblue', 'Deep Sky Blue', '00BFFF', '00bfff', '#00BFFF', '#00bfff', (0, 191, 255)),
        ('DeepSkyBlue',),
        WebColorGroup.COLORES_AZULES,
        '00BFFF',
        (0, 191, 255),
        (195, 100, 50),
        (195, 100, 100),
    )
    CORNFLOWER_BLUE = (
        'cornflowerblue',
        ('CornflowerBlue', 'cornflowerblue', 'Cornflower Blue', '6495ED', '6495ed', '#6495ED', '#6495ed', (100, 149, 237)),
        ('CornflowerBlue',),
        WebColorGroup.COLORES_AZULES,
        '6495ED',
        (100, 149, 237),
        (219, 79, 66),
        (219, 58, 93),
    )
    DODGER_BLUE = (
        'dodgerblue',
        ('DodgerBlue', 'dodgerblue', 'Dodger Blue', '1E90FF', '1e90ff', '#1E90FF', '#1e90ff', (30, 144, 255)),
        ('DodgerBlue',),
        WebColorGroup.COLORES_AZULES,
        '1E90FF',
        (30, 144, 255),
        (210, 88, 100),
        (210, 0, 100),
    )
    STEEL_BLUE = (
        'steelblue',
        ('SteelBlue', 'steelblue', 'Steel Blue', '4682B4', '4682b4', '#4682B4', '#4682b4', (70, 130, 180)),
        ('SteelBlue',),
        WebColorGroup.COLORES_AZULES,
        '4682B4',
        (70, 130, 180),
        (207, 61, 71),
        (207, 40, 89),
    )
    ROYAL_BLUE = (
        'royalblue',
        ('RoyalBlue', 'royalblue', 'Royal Blue', '4169E1', '4169e1', '#4169E1', '#4169e1', (65, 105, 225)),
        ('RoyalBlue',),
        WebColorGroup.COLORES_AZULES,
        '4169E1',
        (65, 105, 225),
        (225, 73, 57),
        (225, 71, 88),
    )
    BLUE = (
        'blue',
        ('Blue', 'blue', '0000FF', '0000ff', '#0000FF', '#0000ff', (0, 0, 255)),
        ('Blue',),
        WebColorGroup.COLORES_AZULES,
        '0000FF',
        (0, 0, 255),
        (240, 100, 100),
        (240, 0, 100),
    )
    MEDIUM_BLUE = (
        'mediumblue',
        ('MediumBlue', 'mediumblue', 'Medium Blue', '0000CD', '0000cd', '#0000CD', '#0000cd', (0, 0, 205)),
        ('MediumBlue',),
        WebColorGroup.COLORES_AZULES,
        '0000CD',
        (0, 0, 205),
        (240, 100, 80),
        (240, 40, 100),
    )
    DARK_BLUE = (
        'darkblue',
        ('DarkBlue', 'darkblue', 'Dark Blue', '00008B', '00008b', '#00008B', '#00008b', (0, 0, 139)),
        ('DarkBlue',),
        WebColorGroup.COLORES_AZULES,
        '00008B',
        (0, 0, 139),
        (240, 100, 55),
        (240, 90, 100),
    )
    NAVY = (
        'navy',
        ('Navy', 'navy', '000080', '#000080', (0, 0, 128)),
        ('Navy',),
        WebColorGroup.COLORES_AZULES,
        '000080',
        (0, 0, 128),
        (240, 100, 50),
        (240, 100, 100),
    )
    MIDNIGHT_BLUE = (
        'midnightblue',
        ('MidnightBlue', 'midnightblue', 'Midnight Blue', '191970', '#191970', (25, 25, 112)),
        ('MidnightBlue',),
        WebColorGroup.COLORES_AZULES,
        '191970',
        (25, 25, 112),
        (240, 78, 44),
        (240, 88, 78),
    )
    DARK_SLATE_BLUE = (
        'darkslateblue',
        ('DarkSlateBlue', 'darkslateblue', 'Dark Slate Blue', '483D8B', '483d8b', '#483D8B', '#483d8b', (72, 61, 139)),
        ('DarkSlateBlue',),
        WebColorGroup.COLORES_AZULES,
        '483D8B',
        (72, 61, 139),
        (248, 39, 39),
        (248, 56, 54),
    )
    THISTLE = (
        'thistle',
        ('Thistle', 'thistle', 'D8BFD8', 'd8bfd8', '#D8BFD8', '#d8bfd8', (216, 191, 216)),
        ('Thistle',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        'D8BFD8',
        (216, 191, 216),
        (300, 24, 80),
        (300, 11, 85),
    )
    PLUM = (
        'plum',
        ('Plum', 'plum', 'DDA0DD', 'dda0dd', '#DDA0DD', '#dda0dd', (221, 160, 221)),
        ('Plum',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        'DDA0DD',
        (221, 160, 221),
        (300, 47, 75),
        (300, 27, 87),
    )
    VIOLET = (
        'violet',
        ('Violet', 'violet', 'EE82EE', 'ee82ee', '#EE82EE', '#ee82ee', (238, 130, 238)),
        ('Violet',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        'EE82EE',
        (238, 130, 238),
        (300, 76, 72),
        (300, 46, 93),
    )
    ORCHID = (
        'orchid',
        ('Orchid', 'orchid', 'DA70D6', 'da70d6', '#DA70D6', '#da70d6', (218, 112, 214)),
        ('Orchid',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        'DA70D6',
        (218, 112, 214),
        (302, 59, 65),
        (302, 48, 86),
    )
    FUCHSIA = (
        'fuchsia',
        ('Fuchsia', 'fuchsia', 'Magenta', 'magenta', 'Fuchsia / Magenta', 'fuchsia / magenta', 'FF00FF', 'ff00ff', '#FF00FF', '#ff00ff', (255, 0, 255)),
        ('Fuchsia', 'Magenta'),
        WebColorGroup.COLORES_ROSAS,
        'FF00FF',
        (255, 0, 255),
        (300, 100, 50),
        (300, 100, 100),
    )
    MEDIUM_PURPLE = (
        'mediumpurple',
        ('MediumPurple', 'mediumpurple', 'Medium Purple', '9370DB', '9370db', '#9370DB', '#9370db', (147, 112, 219)),
        ('MediumPurple',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '9370DB',
        (147, 112, 219),
        (260, 60, 65),
        (260, 49, 86),
    )
    MEDIUM_ORCHID = (
        'mediumorchid',
        ('MediumOrchid', 'mediumorchid', 'Medium Orchid', 'BA55D3', 'ba55d3', '#BA55D3', '#ba55d3', (186, 85, 211)),
        ('MediumOrchid',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        'BA55D3',
        (186, 85, 211),
        (288, 59, 58),
        (288, 60, 83),
    )
    MEDIUM_SLATE_BLUE = (
        'mediumslateblue',
        ('MediumSlateBlue', 'mediumslateblue', 'Medium Slate Blue', '7B68EE', '7b68ee', '#7B68EE', '#7b68ee', (123, 104, 238)),
        ('MediumSlateBlue',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '7B68EE',
        (123, 104, 238),
        (249, 80, 67),
        (249, 57, 93),
    )
    SLATE_BLUE = (
        'slateblue',
        ('SlateBlue', 'slateblue', 'Slate Blue', '6A5ACD', '6a5acd', '#6A5ACD', '#6a5acd', (106, 90, 205)),
        ('SlateBlue',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '6A5ACD',
        (106, 90, 205),
        (248, 53, 58),
        (248, 55, 80),
    )
    BLUE_VIOLET = (
        'blueviolet',
        ('BlueViolet', 'blueviolet', 'Blue Violet', '8A2BE2', '8a2be2', '#8A2BE2', '#8a2be2', (138, 43, 226)),
        ('BlueViolet',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '8A2BE2',
        (138, 43, 226),
        (271, 76, 53),
        (271, 81, 89),
    )
    DARK_VIOLET = (
        'darkviolet',
        ('DarkViolet', 'darkviolet', 'Dark Violet', '9400D3', '9400d3', '#9400D3', '#9400d3', (148, 0, 211)),
        ('DarkViolet',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '9400D3',
        (148, 0, 211),
        (282, 100, 41),
        (282, 100, 82),
    )
    DARK_ORCHID = (
        'darkorchid',
        ('DarkOrchid', 'darkorchid', 'Dark Orchid', '9932CC', '9932cc', '#9932CC', '#9932cc', (153, 50, 204)),
        ('DarkOrchid',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '9932CC',
        (153, 50, 204),
        (280, 61, 50),
        (280, 76, 81),
    )
    DARK_MAGENTA = (
        'darkmagenta',
        ('DarkMagenta', 'darkmagenta', 'Dark Magenta', '8B008B', '8b008b', '#8B008B', '#8b008b', (139, 0, 139)),
        ('DarkMagenta',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '8B008B',
        (139, 0, 139),
        (300, 100, 27),
        (300, 100, 54),
    )
    PURPLE = (
        'purple',
        ('Purple', 'purple', '800080', '#800080', (128, 0, 128)),
        ('Purple',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '800080',
        (128, 0, 128),
        (300, 100, 25),
        (300, 100, 50),
    )
    INDIGO = (
        'indigo',
        ('Indigo', 'indigo', '4B0082', '4b0082', '#4B0082', '#4b0082', (75, 0, 130)),
        ('Indigo',),
        WebColorGroup.COLORES_VIOLETAS_Y_PURPURAS,
        '4B0082',
        (75, 0, 130),
        (275, 100, 25),
        (275, 100, 50),
    )
    MISTY_ROSE = (
        'mistyrose',
        ('MistyRose', 'mistyrose', 'Misty Rose', 'FFE4E1', 'ffe4e1', '#FFE4E1', '#ffe4e1', (255, 228, 225)),
        ('MistyRose',),
        WebColorGroup.COLORES_ROSAS,
        'FFE4E1',
        (255, 228, 225),
        (6, 100, 94),
        (6, 12, 100),
    )
    PINK = (
        'pink',
        ('Pink', 'pink', 'FFC0CB', 'ffc0cb', '#FFC0CB', '#ffc0cb', (255, 192, 203)),
        ('Pink',),
        WebColorGroup.COLORES_ROSAS,
        'FFC0CB',
        (255, 192, 203),
        (350, 100, 88),
        (350, 24, 100),
    )
    LIGHT_PINK = (
        'lightpink',
        ('LightPink', 'lightpink', 'Light Pink', 'FFB6C1', 'ffb6c1', '#FFB6C1', '#ffb6c1', (255, 182, 193)),
        ('LightPink',),
        WebColorGroup.COLORES_ROSAS,
        'FFB6C1',
        (255, 182, 193),
        (351, 100, 86),
        (351, 28, 100),
    )
    HOT_PINK = (
        'hotpink',
        ('HotPink', 'hotpink', 'Hot Pink', 'FF69B4', 'ff69b4', '#FF69B4', '#ff69b4', (255, 105, 180)),
        ('HotPink',),
        WebColorGroup.COLORES_ROSAS,
        'FF69B4',
        (255, 105, 180),
        (330, 100, 71),
        (330, 58, 100),
    )
    ROSY_BROWN = (
        'rosybrown',
        ('RosyBrown', 'rosybrown', 'Rosy Brown', 'BC8F8F', 'bc8f8f', '#BC8F8F', '#bc8f8f', (188, 143, 143)),
        ('RosyBrown',),
        WebColorGroup.COLORES_ROSAS,
        'BC8F8F',
        (188, 143, 143),
        (0, 25, 65),
        (0, 24, 74),
    )
    PALE_VIOLET_RED = (
        'palevioletred',
        ('PaleVioletRed', 'palevioletred', 'Pale Violet Red', 'DB7093', 'db7093', '#DB7093', '#db7093', (219, 112, 147)),
        ('PaleVioletRed',),
        WebColorGroup.COLORES_ROSAS,
        'DB7093',
        (219, 112, 147),
        (340, 60, 65),
        (340, 49, 86),
    )
    DEEP_PINK = (
        'deeppink',
        ('DeepPink', 'deeppink', 'Deep Pink', 'FF1493', 'ff1493', '#FF1493', '#ff1493', (255, 20, 147)),
        ('DeepPink',),
        WebColorGroup.COLORES_ROSAS,
        'FF1493',
        (255, 20, 147),
        (328, 100, 54),
        (328, 92, 100),
    )
    MEDIUM_VIOLET_RED = (
        'mediumvioletred',
        ('MediumVioletRed', 'mediumvioletred', 'Medium Violet Red', 'C71585', 'c71585', '#C71585', '#c71585', (199, 21, 133)),
        ('MediumVioletRed',),
        WebColorGroup.COLORES_ROSAS,
        'C71585',
        (199, 21, 133),
        (322, 81, 43),
        (322, 90, 78),
    )
    WHITE = (
        'white',
        ('White', 'white', 'FFFFFF', 'ffffff', '#FFFFFF', '#ffffff', (255, 255, 255)),
        ('White',),
        WebColorGroup.COLORES_BLANCOS,
        'FFFFFF',
        (255, 255, 255),
        (None, None, 100),
        (None, 0, 100),
    )
    WHITE_SMOKE = (
        'whitesmoke',
        ('WhiteSmoke', 'whitesmoke', 'White Smoke', 'F5F5F5', 'f5f5f5', '#F5F5F5', '#f5f5f5', (245, 245, 245)),
        ('WhiteSmoke',),
        WebColorGroup.COLORES_BLANCOS,
        'F5F5F5',
        (245, 245, 245),
        (None, 0, 96),
        (None, 0, 96),
    )
    SNOW = (
        'snow',
        ('Snow', 'snow', 'FFFAFA', 'fffafa', '#FFFAFA', '#fffafa', (255, 250, 250)),
        ('Snow',),
        WebColorGroup.COLORES_BLANCOS,
        'FFFAFA',
        (255, 250, 250),
        (0, 2, 100),
        (0, 0, 100),
    )
    SEASHELL = (
        'seashell',
        ('Seashell', 'seashell', 'FFF5EE', 'fff5ee', '#FFF5EE', '#fff5ee', (255, 245, 238)),
        ('Seashell',),
        WebColorGroup.COLORES_BLANCOS,
        'FFF5EE',
        (255, 245, 238),
        (25, 100, 97),
        (25, 6, 100),
    )
    LINEN = (
        'linen',
        ('Linen', 'linen', 'FAF0E6', 'faf0e6', '#FAF0E6', '#faf0e6', (250, 240, 230)),
        ('Linen',),
        WebColorGroup.COLORES_BLANCOS,
        'FAF0E6',
        (250, 240, 230),
        (30, 67, 94),
        (30, 8, 98),
    )
    ANTIQUE_WHITE = (
        'antiquewhite',
        ('AntiqueWhite', 'antiquewhite', 'Antique White', 'FAEBD7', 'faebd7', '#FAEBD7', '#faebd7', (250, 235, 215)),
        ('AntiqueWhite',),
        WebColorGroup.COLORES_BLANCOS,
        'FAEBD7',
        (250, 235, 215),
        (34, 78, 91),
        (34, 14, 98),
    )
    OLD_LACE = (
        'oldlace',
        ('OldLace', 'oldlace', 'Old Lace', 'FDF5E6', 'fdf5e6', '#FDF5E6', '#fdf5e6', (253, 245, 230)),
        ('OldLace',),
        WebColorGroup.COLORES_BLANCOS,
        'FDF5E6',
        (253, 245, 230),
        (39, 85, 95),
        (39, 9, 99),
    )
    FLORAL_WHITE = (
        'floralwhite',
        ('FloralWhite', 'floralwhite', 'Floral White', 'FFFAF0', 'fffaf0', '#FFFAF0', '#fffaf0', (255, 250, 240)),
        ('FloralWhite',),
        WebColorGroup.COLORES_BLANCOS,
        'FFFAF0',
        (255, 250, 240),
        (40, 100, 97),
        (40, 6, 100),
    )
    IVORY = (
        'ivory',
        ('Ivory', 'ivory', 'FFFFF0', 'fffff0', '#FFFFF0', '#fffff0', (255, 255, 240)),
        ('Ivory',),
        WebColorGroup.COLORES_BLANCOS,
        'FFFFF0',
        (255, 255, 240),
        (60, 100, 97),
        (60, 6, 100),
    )
    BEIGE = (
        'beige',
        ('Beige', 'beige', 'F5F5DC', 'f5f5dc', '#F5F5DC', '#f5f5dc', (245, 245, 220)),
        ('Beige',),
        WebColorGroup.COLORES_BLANCOS,
        'F5F5DC',
        (245, 245, 220),
        (60, 56, 91),
        (60, 10, 96),
    )
    HONEYDEW = (
        'honeydew',
        ('Honeydew', 'honeydew', 'F0FFF0', 'f0fff0', '#F0FFF0', '#f0fff0', (240, 255, 240)),
        ('Honeydew',),
        WebColorGroup.COLORES_BLANCOS,
        'F0FFF0',
        (240, 255, 240),
        (120, 6, 100),
        (120, 0, 100),
    )
    MINT_CREAM = (
        'mintcream',
        ('MintCream', 'mintcream', 'Mint Cream', 'F5FFFA', 'f5fffa', '#F5FFFA', '#f5fffa', (245, 255, 250)),
        ('MintCream',),
        WebColorGroup.COLORES_BLANCOS,
        'F5FFFA',
        (245, 255, 250),
        (150, 4, 100),
        (150, 0, 100),
    )
    AZURE = (
        'azure',
        ('Azure', 'azure', 'F0FFFF', 'f0ffff', '#F0FFFF', '#f0ffff', (240, 255, 255)),
        ('Azure',),
        WebColorGroup.COLORES_BLANCOS,
        'F0FFFF',
        (240, 255, 255),
        (180, 6, 100),
        (180, 0, 100),
    )
    ALICE_BLUE = (
        'aliceblue',
        ('AliceBlue', 'aliceblue', 'Alice Blue', 'F0F8FF', 'f0f8ff', '#F0F8FF', '#f0f8ff', (240, 248, 255)),
        ('AliceBlue',),
        WebColorGroup.COLORES_BLANCOS,
        'F0F8FF',
        (240, 248, 255),
        (208, 100, 97),
        (208, 6, 100),
    )
    GHOST_WHITE = (
        'ghostwhite',
        ('GhostWhite', 'ghostwhite', 'Ghost White', 'F8F8FF', 'f8f8ff', '#F8F8FF', '#f8f8ff', (248, 248, 255)),
        ('GhostWhite',),
        WebColorGroup.COLORES_BLANCOS,
        'F8F8FF',
        (248, 248, 255),
        (240, 100, 99),
        (240, 2, 100),
    )
    LAVENDER_BLUSH = (
        'lavenderblush',
        ('LavenderBlush', 'lavenderblush', 'Lavender Blush', 'FFF0F5', 'fff0f5', '#FFF0F5', '#fff0f5', (255, 240, 245)),
        ('LavenderBlush',),
        WebColorGroup.COLORES_BLANCOS,
        'FFF0F5',
        (255, 240, 245),
        (340, 100, 97),
        (340, 6, 100),
    )
    GAINSBORO = (
        'gainsboro',
        ('Gainsboro', 'gainsboro', 'DCDCDC', 'dcdcdc', '#DCDCDC', '#dcdcdc', (220, 220, 220)),
        ('Gainsboro',),
        WebColorGroup.COLORES_GRISES,
        'DCDCDC',
        (220, 220, 220),
        (None, 0, 86),
        (None, 0, 86),
    )
    LIGHT_GREY = (
        'lightgrey',
        ('LightGrey', 'lightgrey', 'Light Grey', 'D3D3D3', 'd3d3d3', '#D3D3D3', '#d3d3d3', (211, 211, 211)),
        ('LightGrey',),
        WebColorGroup.COLORES_GRISES,
        'D3D3D3',
        (211, 211, 211),
        (None, 0, 83),
        (None, 0, 83),
    )
    SILVER = (
        'silver',
        ('Silver', 'silver', 'C0C0C0', 'c0c0c0', '#C0C0C0', '#c0c0c0', (192, 192, 192)),
        ('Silver',),
        WebColorGroup.COLORES_GRISES,
        'C0C0C0',
        (192, 192, 192),
        (None, 0, 75),
        (None, 0, 75),
    )
    DARK_GRAY = (
        'darkgray',
        ('DarkGray', 'darkgray', 'Dark Gray', 'A9A9A9', 'a9a9a9', '#A9A9A9', '#a9a9a9', (169, 169, 169)),
        ('DarkGray',),
        WebColorGroup.COLORES_GRISES,
        'A9A9A9',
        (169, 169, 169),
        (None, 0, 66),
        (None, 0, 66),
    )
    LIGHT_SLATE_GRAY = (
        'lightslategray',
        ('LightSlateGray', 'lightslategray', 'Light Slate Gray', '778899', '#778899', (119, 136, 153)),
        ('LightSlateGray',),
        WebColorGroup.COLORES_GRISES,
        '778899',
        (119, 136, 153),
        (210, 22, 60),
        (210, 26, 69),
    )
    SLATE_GRAY = (
        'slategray',
        ('SlateGray', 'slategray', 'Slate Gray', '708090', '#708090', (112, 128, 144)),
        ('SlateGray',),
        WebColorGroup.COLORES_GRISES,
        '708090',
        (112, 128, 144),
        (210, 22, 56),
        (210, 29, 66),
    )
    GRAY = (
        'gray',
        ('Gray', 'gray', '808080', '#808080', (128, 128, 128)),
        ('Gray',),
        WebColorGroup.COLORES_GRISES,
        '808080',
        (128, 128, 128),
        (None, 0, 50),
        (None, 0, 50),
    )
    DIM_GRAY = (
        'dimgray',
        ('DimGray', 'dimgray', 'Dim Gray', '696969', '#696969', (105, 105, 105)),
        ('DimGray',),
        WebColorGroup.COLORES_GRISES,
        '696969',
        (105, 105, 105),
        (None, 0, 41),
        (None, 0, 41),
    )
    DARK_SLATE_GRAY = (
        'darkslategray',
        ('DarkSlateGray', 'darkslategray', 'Dark Slate Gray', '2F4F4F', '2f4f4f', '#2F4F4F', '#2f4f4f', (47, 79, 79)),
        ('DarkSlateGray',),
        WebColorGroup.COLORES_GRISES,
        '2F4F4F',
        (47, 79, 79),
        (180, 25, 25),
        (180, 40, 31),
    )
    BLACK = (
        'black',
        ('Black', 'black', '000000', '#000000', (0, 0, 0)),
        ('Black',),
        WebColorGroup.COLORES_GRISES,
        '000000',
        (0, 0, 0),
        (None, None, 0),
        (None, None, 0),
    )


def iter_web_colors(group: WebColorGroup | str | None = None) -> Iterable[WebColor]:
    if group is None:
        return tuple(WebColor)
    group_member = group if isinstance(group, WebColorGroup) else WebColorGroup(group)
    return tuple(member for member in WebColor if member.group == group_member)


def get_web_color(value: Any) -> WebColor:
    if isinstance(value, WebColor):
        return value
    return WebColor(value)


def nearest_web_color(value: Any, *, method: str = WEB_COLOR_MATCH_METHOD) -> WebColorMatch:
    target_rgb = color_registry.format_color(value, "rgb")
    best_member = min(
        WebColor,
        key=lambda member: color_registry.delta_e_distance(target_rgb, member.rgb, method=method),
    )
    best_distance = color_registry.delta_e_distance(target_rgb, best_member.rgb, method=method)
    return WebColorMatch(
        color_name=best_member.canonical_name,
        display_name=best_member.display_name,
        group_name=best_member.group.value,
        hex_code=best_member.hex_code,
        rgb=best_member.rgb,
        distance=best_distance,
        method=method,
    )


__all__ = [
    "MultiValueEnum",
    "WEB_COLOR_MATCH_METHOD",
    "WEB_COLOR_SOURCE_TITLE",
    "WebColor",
    "WebColorGroup",
    "WebColorMatch",
    "get_web_color",
    "iter_web_colors",
    "nearest_web_color",
]
