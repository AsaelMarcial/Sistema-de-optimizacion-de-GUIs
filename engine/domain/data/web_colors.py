from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar

from coloraide.everything import ColorAll as Color


@dataclass(frozen=True)
class ColorDictionary:
    __slots__ = ("group", "hex", "rgb_value")

    group: str
    hex: str
    rgb_value: str

DICTIONARY = MappingProxyType(
    {
        "lightcoral": ColorDictionary(
            group="Rojo",
            hex="F08080",
            rgb_value="rgb(240, 128, 128)",
        ),
        "salmon": ColorDictionary(
            group="Rojo",
            hex="FA8072",
            rgb_value="rgb(250, 128, 114)",
        ),
        "indianred": ColorDictionary(
            group="Rojo",
            hex="CD5C5C",
            rgb_value="rgb(205, 92, 92)",
        ),
        "red": ColorDictionary(
            group="Rojo",
            hex="FF0000",
            rgb_value="rgb(255, 0, 0)",
        ),
        "crimson": ColorDictionary(
            group="Rojo",
            hex="DC143C",
            rgb_value="rgb(220, 20, 60)",
        ),
        "firebrick": ColorDictionary(
            group="Rojo",
            hex="B22222",
            rgb_value="rgb(178, 34, 34)",
        ),
        "brown": ColorDictionary(
            group="Rojo",
            hex="A52A2A",
            rgb_value="rgb(165, 42, 42)",
        ),
        "darkred": ColorDictionary(
            group="Rojo",
            hex="8B0000",
            rgb_value="rgb(139, 0, 0)",
        ),
        "maroon": ColorDictionary(
            group="Rojo",
            hex="800000",
            rgb_value="rgb(128, 0, 0)",
        ),
        "papayawhip": ColorDictionary(
            group="Naranja",
            hex="FFEFD5",
            rgb_value="rgb(255, 239, 213)",
        ),
        "blanchedalmond": ColorDictionary(
            group="Naranja",
            hex="FFEBCD",
            rgb_value="rgb(255, 235, 205)",
        ),
        "bisque": ColorDictionary(
            group="Naranja",
            hex="FFE4C4",
            rgb_value="rgb(255, 228, 196)",
        ),
        "moccasin": ColorDictionary(
            group="Naranja",
            hex="FFE4B5",
            rgb_value="rgb(255, 228, 181)",
        ),
        "peachpuff": ColorDictionary(
            group="Naranja",
            hex="FFDAB9",
            rgb_value="rgb(255, 218, 185)",
        ),
        "navajowhite": ColorDictionary(
            group="Naranja",
            hex="FFDEAD",
            rgb_value="rgb(255, 222, 173)",
        ),
        "lightsalmon": ColorDictionary(
            group="Naranja",
            hex="FFA07A",
            rgb_value="rgb(255, 160, 122)",
        ),
        "darksalmon": ColorDictionary(
            group="Naranja",
            hex="E9967A",
            rgb_value="rgb(233, 150, 122)",
        ),
        "orange": ColorDictionary(
            group="Naranja",
            hex="FFA500",
            rgb_value="rgb(255, 165, 0)",
        ),
        "darkorange": ColorDictionary(
            group="Naranja",
            hex="FF8C00",
            rgb_value="rgb(255, 140, 0)",
        ),
        "coral": ColorDictionary(
            group="Naranja",
            hex="FF7F50",
            rgb_value="rgb(255, 127, 80)",
        ),
        "tomato": ColorDictionary(
            group="Naranja",
            hex="FF6347",
            rgb_value="rgb(255, 99, 71)",
        ),
        "orangered": ColorDictionary(
            group="Naranja",
            hex="FF4500",
            rgb_value="rgb(255, 69, 0)",
        ),
        "wheat": ColorDictionary(
            group="Marrón",
            hex="F5DEB3",
            rgb_value="rgb(245, 222, 179)",
        ),
        "burlywood": ColorDictionary(
            group="Marrón",
            hex="DEB887",
            rgb_value="rgb(222, 184, 135)",
        ),
        "tan": ColorDictionary(
            group="Marrón",
            hex="D2B48C",
            rgb_value="rgb(210, 180, 140)",
        ),
        "sandybrown": ColorDictionary(
            group="Marrón",
            hex="F4A460",
            rgb_value="rgb(244, 164, 96)",
        ),
        "goldenrod": ColorDictionary(
            group="Marrón",
            hex="DAA520",
            rgb_value="rgb(218, 165, 32)",
        ),
        "peru": ColorDictionary(
            group="Marrón",
            hex="CD853F",
            rgb_value="rgb(205, 133, 63)",
        ),
        "darkgoldenrod": ColorDictionary(
            group="Marrón",
            hex="B8860B",
            rgb_value="rgb(184, 134, 11)",
        ),
        "chocolate": ColorDictionary(
            group="Marrón",
            hex="D2691E",
            rgb_value="rgb(210, 105, 30)",
        ),
        "sienna": ColorDictionary(
            group="Marrón",
            hex="A0522D",
            rgb_value="rgb(160, 82, 45)",
        ),
        "saddlebrown": ColorDictionary(
            group="Marrón",
            hex="8B4513",
            rgb_value="rgb(139, 69, 19)",
        ),
        "lightyellow": ColorDictionary(
            group="Amarillo",
            hex="FFFFE0",
            rgb_value="rgb(255, 255, 224)",
        ),
        "cornsilk": ColorDictionary(
            group="Amarillo",
            hex="FFF8DC",
            rgb_value="rgb(255, 248, 220)",
        ),
        "lemonchiffon": ColorDictionary(
            group="Amarillo",
            hex="FFFACD",
            rgb_value="rgb(255, 250, 205)",
        ),
        "lightgoldenrodyellow": ColorDictionary(
            group="Amarillo",
            hex="FAFAD2",
            rgb_value="rgb(250, 250, 210)",
        ),
        "palegoldenrod": ColorDictionary(
            group="Amarillo",
            hex="EEE8AA",
            rgb_value="rgb(238, 232, 170)",
        ),
        "khaki": ColorDictionary(
            group="Amarillo",
            hex="F0E68C",
            rgb_value="rgb(240, 230, 140)",
        ),
        "yellow": ColorDictionary(
            group="Amarillo",
            hex="FFFF00",
            rgb_value="rgb(255, 255, 0)",
        ),
        "gold": ColorDictionary(
            group="Amarillo",
            hex="FFD700",
            rgb_value="rgb(255, 215, 0)",
        ),
        "darkkhaki": ColorDictionary(
            group="Amarillo",
            hex="BDB76B",
            rgb_value="rgb(189, 183, 107)",
        ),
        "olive": ColorDictionary(
            group="Amarillo",
            hex="808000",
            rgb_value="rgb(128, 128, 0)",
        ),
        "greenyellow": ColorDictionary(
            group="Verde amarillo",
            hex="ADFF2F",
            rgb_value="rgb(173, 255, 47)",
        ),
        "chartreuse": ColorDictionary(
            group="Verde amarillo",
            hex="7FFF00",
            rgb_value="rgb(127, 255, 0)",
        ),
        "lawngreen": ColorDictionary(
            group="Verde amarillo",
            hex="7CFC00",
            rgb_value="rgb(124, 252, 0)",
        ),
        "yellowgreen": ColorDictionary(
            group="Verde amarillo",
            hex="9ACD32",
            rgb_value="rgb(154, 205, 50)",
        ),
        "olivedrab": ColorDictionary(
            group="Verde amarillo",
            hex="6B8E23",
            rgb_value="rgb(107, 142, 35)",
        ),
        "darkolivegreen": ColorDictionary(
            group="Verde amarillo",
            hex="556B2F",
            rgb_value="rgb(85, 107, 47)",
        ),
        "palegreen": ColorDictionary(
            group="Verde",
            hex="98FB98",
            rgb_value="rgb(152, 251, 152)",
        ),
        "lightgreen": ColorDictionary(
            group="Verde",
            hex="90EE90",
            rgb_value="rgb(144, 238, 144)",
        ),
        "mediumspringgreen": ColorDictionary(
            group="Verde",
            hex="00FA9A",
            rgb_value="rgb(0, 250, 154)",
        ),
        "springgreen": ColorDictionary(
            group="Verde",
            hex="00FF7F",
            rgb_value="rgb(0, 255, 127)",
        ),
        "lime": ColorDictionary(
            group="Verde",
            hex="00FF00",
            rgb_value="rgb(0, 255, 0)",
        ),
        "darkseagreen": ColorDictionary(
            group="Verde",
            hex="8FBC8F",
            rgb_value="rgb(143, 188, 143)",
        ),
        "limegreen": ColorDictionary(
            group="Verde",
            hex="32CD32",
            rgb_value="rgb(50, 205, 50)",
        ),
        "mediumseagreen": ColorDictionary(
            group="Verde",
            hex="3CB371",
            rgb_value="rgb(60, 179, 113)",
        ),
        "seagreen": ColorDictionary(
            group="Verde",
            hex="2E8B57",
            rgb_value="rgb(46, 139, 87)",
        ),
        "forestgreen": ColorDictionary(
            group="Verde",
            hex="228B22",
            rgb_value="rgb(34, 139, 34)",
        ),
        "green": ColorDictionary(
            group="Verde",
            hex="008000",
            rgb_value="rgb(0, 128, 0)",
        ),
        "darkgreen": ColorDictionary(
            group="Verde",
            hex="006400",
            rgb_value="rgb(0, 100, 0)",
        ),
        "lightcyan": ColorDictionary(
            group="Aciano azul verde",
            hex="E0FFFF",
            rgb_value="rgb(224, 255, 255)",
        ),
        "paleturquoise": ColorDictionary(
            group="Aciano azul verde",
            hex="AFEEEE",
            rgb_value="rgb(175, 238, 238)",
        ),
        "aquamarine": ColorDictionary(
            group="Aciano azul verde",
            hex="7FFFD4",
            rgb_value="rgb(127, 255, 212)",
        ),
        "aqua": ColorDictionary(
            group="Aciano azul verde",
            hex="00FFFF",
            rgb_value="rgb(0, 255, 255)",
        ),
        "turquoise": ColorDictionary(
            group="Aciano azul verde",
            hex="40E0D0",
            rgb_value="rgb(64, 224, 208)",
        ),
        "mediumturquoise": ColorDictionary(
            group="Aciano azul verde",
            hex="48D1CC",
            rgb_value="rgb(72, 209, 204)",
        ),
        "darkturquoise": ColorDictionary(
            group="Aciano azul verde",
            hex="00CED1",
            rgb_value="rgb(0, 206, 209)",
        ),
        "mediumaquamarine": ColorDictionary(
            group="Aciano azul verde",
            hex="66CDAA",
            rgb_value="rgb(102, 205, 170)",
        ),
        "lightseagreen": ColorDictionary(
            group="Aciano azul verde",
            hex="20B2AA",
            rgb_value="rgb(32, 178, 170)",
        ),
        "cadetblue": ColorDictionary(
            group="Aciano azul verde",
            hex="5F9EA0",
            rgb_value="rgb(95, 158, 160)",
        ),
        "darkcyan": ColorDictionary(
            group="Aciano azul verde",
            hex="008B8B",
            rgb_value="rgb(0, 139, 139)",
        ),
        "teal": ColorDictionary(
            group="Aciano azul verde",
            hex="008080",
            rgb_value="rgb(0, 128, 128)",
        ),
        "lavender": ColorDictionary(
            group="Azul",
            hex="E6E6FA",
            rgb_value="rgb(230, 230, 250)",
        ),
        "blueweb": ColorDictionary(
            group="Azul",
            hex="CEE7FF",
            rgb_value="rgb(206, 231, 255)",
        ),
        "powderblue": ColorDictionary(
            group="Azul",
            hex="B0E0E6",
            rgb_value="rgb(176, 224, 230)",
        ),
        "lightblue": ColorDictionary(
            group="Azul",
            hex="ADD8E6",
            rgb_value="rgb(173, 216, 230)",
        ),
        "lightskyblue": ColorDictionary(
            group="Azul",
            hex="87CEFA",
            rgb_value="rgb(135, 206, 250)",
        ),
        "skyblue": ColorDictionary(
            group="Azul",
            hex="87CEEB",
            rgb_value="rgb(135, 206, 235)",
        ),
        "lightsteelblue": ColorDictionary(
            group="Azul",
            hex="B0C4DE",
            rgb_value="rgb(176, 196, 222)",
        ),
        "deepskyblue": ColorDictionary(
            group="Azul",
            hex="00BFFF",
            rgb_value="rgb(0, 191, 255)",
        ),
        "cornflowerblue": ColorDictionary(
            group="Azul",
            hex="6495ED",
            rgb_value="rgb(100, 149, 237)",
        ),
        "dodgerblue": ColorDictionary(
            group="Azul",
            hex="1E90FF",
            rgb_value="rgb(30, 144, 255)",
        ),
        "steelblue": ColorDictionary(
            group="Azul",
            hex="4682B4",
            rgb_value="rgb(70, 130, 180)",
        ),
        "royalblue": ColorDictionary(
            group="Azul",
            hex="4169E1",
            rgb_value="rgb(65, 105, 225)",
        ),
        "blue": ColorDictionary(
            group="Azul",
            hex="0000FF",
            rgb_value="rgb(0, 0, 255)",
        ),
        "mediumblue": ColorDictionary(
            group="Azul",
            hex="0000CD",
            rgb_value="rgb(0, 0, 205)",
        ),
        "darkblue": ColorDictionary(
            group="Azul",
            hex="00008B",
            rgb_value="rgb(0, 0, 139)",
        ),
        "navy": ColorDictionary(
            group="Azul",
            hex="000080",
            rgb_value="rgb(0, 0, 128)",
        ),
        "midnightblue": ColorDictionary(
            group="Azul",
            hex="191970",
            rgb_value="rgb(25, 25, 112)",
        ),
        "darkslateblue": ColorDictionary(
            group="Azul",
            hex="483D8B",
            rgb_value="rgb(72, 61, 139)",
        ),
        "thistle": ColorDictionary(
            group="Violeta",
            hex="D8BFD8",
            rgb_value="rgb(216, 191, 216)",
        ),
        "plum": ColorDictionary(
            group="Violeta",
            hex="DDA0DD",
            rgb_value="rgb(221, 160, 221)",
        ),
        "violet": ColorDictionary(
            group="Violeta",
            hex="EE82EE",
            rgb_value="rgb(238, 130, 238)",
        ),
        "orchid": ColorDictionary(
            group="Violeta",
            hex="DA70D6",
            rgb_value="rgb(218, 112, 214)",
        ),
        "fuchsia": ColorDictionary(
            group="Rosa",
            hex="FF00FF",
            rgb_value="rgb(255, 0, 255)",
        ),
        "mediumpurple": ColorDictionary(
            group="Violeta",
            hex="9370DB",
            rgb_value="rgb(147, 112, 219)",
        ),
        "mediumorchid": ColorDictionary(
            group="Violeta",
            hex="BA55D3",
            rgb_value="rgb(186, 85, 211)",
        ),
        "mediumslateblue": ColorDictionary(
            group="Violeta",
            hex="7B68EE",
            rgb_value="rgb(123, 104, 238)",
        ),
        "slateblue": ColorDictionary(
            group="Violeta",
            hex="6A5ACD",
            rgb_value="rgb(106, 90, 205)",
        ),
        "blueviolet": ColorDictionary(
            group="Violeta",
            hex="8A2BE2",
            rgb_value="rgb(138, 43, 226)",
        ),
        "darkviolet": ColorDictionary(
            group="Violeta",
            hex="9400D3",
            rgb_value="rgb(148, 0, 211)",
        ),
        "darkorchid": ColorDictionary(
            group="Violeta",
            hex="9932CC",
            rgb_value="rgb(153, 50, 204)",
        ),
        "darkmagenta": ColorDictionary(
            group="Violeta",
            hex="8B008B",
            rgb_value="rgb(139, 0, 139)",
        ),
        "purple": ColorDictionary(
            group="Violeta",
            hex="800080",
            rgb_value="rgb(128, 0, 128)",
        ),
        "indigo": ColorDictionary(
            group="Violeta",
            hex="4B0082",
            rgb_value="rgb(75, 0, 130)",
        ),
        "mistyrose": ColorDictionary(
            group="Rosa",
            hex="FFE4E1",
            rgb_value="rgb(255, 228, 225)",
        ),
        "pink": ColorDictionary(
            group="Rosa",
            hex="FFC0CB",
            rgb_value="rgb(255, 192, 203)",
        ),
        "lightpink": ColorDictionary(
            group="Rosa",
            hex="FFB6C1",
            rgb_value="rgb(255, 182, 193)",
        ),
        "hotpink": ColorDictionary(
            group="Rosa",
            hex="FF69B4",
            rgb_value="rgb(255, 105, 180)",
        ),
        "rosybrown": ColorDictionary(
            group="Rosa",
            hex="BC8F8F",
            rgb_value="rgb(188, 143, 143)",
        ),
        "palevioletred": ColorDictionary(
            group="Rosa",
            hex="DB7093",
            rgb_value="rgb(219, 112, 147)",
        ),
        "deeppink": ColorDictionary(
            group="Rosa",
            hex="FF1493",
            rgb_value="rgb(255, 20, 147)",
        ),
        "mediumvioletred": ColorDictionary(
            group="Rosa",
            hex="C71585",
            rgb_value="rgb(199, 21, 133)",
        ),
        "white": ColorDictionary(
            group="Blanco",
            hex="FFFFFF",
            rgb_value="rgb(255, 255, 255)",
        ),
        "whitesmoke": ColorDictionary(
            group="Blanco",
            hex="F5F5F5",
            rgb_value="rgb(245, 245, 245)",
        ),
        "snow": ColorDictionary(
            group="Blanco",
            hex="FFFAFA",
            rgb_value="rgb(255, 250, 250)",
        ),
        "seashell": ColorDictionary(
            group="Blanco",
            hex="FFF5EE",
            rgb_value="rgb(255, 245, 238)",
        ),
        "linen": ColorDictionary(
            group="Blanco",
            hex="FAF0E6",
            rgb_value="rgb(250, 240, 230)",
        ),
        "antiquewhite": ColorDictionary(
            group="Blanco",
            hex="FAEBD7",
            rgb_value="rgb(250, 235, 215)",
        ),
        "oldlace": ColorDictionary(
            group="Blanco",
            hex="FDF5E6",
            rgb_value="rgb(253, 245, 230)",
        ),
        "floralwhite": ColorDictionary(
            group="Blanco",
            hex="FFFAF0",
            rgb_value="rgb(255, 250, 240)",
        ),
        "ivory": ColorDictionary(
            group="Blanco",
            hex="FFFFF0",
            rgb_value="rgb(255, 255, 240)",
        ),
        "beige": ColorDictionary(
            group="Blanco",
            hex="F5F5DC",
            rgb_value="rgb(245, 245, 220)",
        ),
        "honeydew": ColorDictionary(
            group="Blanco",
            hex="F0FFF0",
            rgb_value="rgb(240, 255, 240)",
        ),
        "mintcream": ColorDictionary(
            group="Blanco",
            hex="F5FFFA",
            rgb_value="rgb(245, 255, 250)",
        ),
        "azure": ColorDictionary(
            group="Blanco",
            hex="F0FFFF",
            rgb_value="rgb(240, 255, 255)",
        ),
        "aliceblue": ColorDictionary(
            group="Blanco",
            hex="F0F8FF",
            rgb_value="rgb(240, 248, 255)",
        ),
        "ghostwhite": ColorDictionary(
            group="Blanco",
            hex="F8F8FF",
            rgb_value="rgb(248, 248, 255)",
        ),
        "lavenderblush": ColorDictionary(
            group="Blanco",
            hex="FFF0F5",
            rgb_value="rgb(255, 240, 245)",
        ),
        "gainsboro": ColorDictionary(
            group="Grises",
            hex="DCDCDC",
            rgb_value="rgb(220, 220, 220)",
        ),
        "lightgrey": ColorDictionary(
            group="Grises",
            hex="D3D3D3",
            rgb_value="rgb(211, 211, 211)",
        ),
        "silver": ColorDictionary(
            group="Grises",
            hex="C0C0C0",
            rgb_value="rgb(192, 192, 192)",
        ),
        "darkgray": ColorDictionary(
            group="Grises",
            hex="A9A9A9",
            rgb_value="rgb(169, 169, 169)",
        ),
        "lightslategray": ColorDictionary(
            group="Grises",
            hex="778899",
            rgb_value="rgb(119, 136, 153)",
        ),
        "slategray": ColorDictionary(
            group="Grises",
            hex="708090",
            rgb_value="rgb(112, 128, 144)",
        ),
        "gray": ColorDictionary(
            group="Grises",
            hex="808080",
            rgb_value="rgb(128, 128, 128)",
        ),
        "dimgray": ColorDictionary(
            group="Grises",
            hex="696969",
            rgb_value="rgb(105, 105, 105)",
        ),
        "darkslategray": ColorDictionary(
            group="Grises",
            hex="2F4F4F",
            rgb_value="rgb(47, 79, 79)",
        ),
        "black": ColorDictionary(
            group="Grises",
            hex="000000",
            rgb_value="rgb(0, 0, 0)",
        ),
    }
)

def all_rgb_values() -> list[str]:
    rgb_values = []
    for key in DICTIONARY.keys():
        rgb_values.append(DICTIONARY[key].rgb_value)
    return rgb_values


def nearest_web_color(value: Color) -> str:
    name = Color(value).closest(all_rgb_values()).to_string(names=True)
    
    return name
