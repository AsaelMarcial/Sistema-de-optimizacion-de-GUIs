from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional
from coloraide.everything import ColorAll

TONAL_STEPS: tuple[int, ...] = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95)
NEUTRAL_TONAL_STEPS: tuple[int, ...] = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100)

class Color(ColorAll):
    """
    Project Color class.

    This class extends ColorAide's ColorAll and centralizes the default color
    behavior required by the project.

    Project defaults:
        DELTA_E = "2000"
            Default color-difference algorithm used when delta_e() or closest()
            are called without an explicit method.

        CONTRAST = "wcag21"
            Default contrast algorithm used when contrast() is called without
            an explicit method.

        INTERPOLATE = "hct"
            Default interpolation space used by interpolation-related methods.

        FIT = "lch-chroma"
            Default gamut mapping method.

        PRECISION = 5
            Default output precision.

        DECIMAL = True
            Enables decimal-place rounding behavior according to ColorAide's
            precision settings.

    ColorAide methods commonly used by this project:

    - convert(space: str, *, in_place: bool = False, norm: bool = True) -> Color
        Converts the color to another color space.

        Parameters:
            space:
                Target color space name. Example: "srgb", "hct", "oklch".
            in_place:
                If False, returns a new Color object.
                If True, mutates the current object and returns itself.
            norm:
                Controls achromatic hue normalization during conversion.

        Returns:
            Color object in the requested color space.

        Example:
            color = Color("rgb(255, 0, 0)")
            hct_color = color.convert("hct")


    - to_string(**kwargs) -> str
        Serializes the color to a string format supported by its color space.

        Common parameters:
            alpha:
                If True, always includes alpha.
                If False, omits alpha.
                If None, alpha appears only when needed.
            precision:
                Controls output precision.
            fit:
                If True, applies gamut mapping during string output.
            color:
                If True, outputs color(space ...).
            percent:
                If True, outputs channels as percentages when supported.

        sRGB-specific parameters:
            hex:
                If True, outputs HEX format.
            names:
                If True, outputs CSS color names when available.
            comma:
                If True, outputs legacy comma-separated rgb()/rgba().
            compress:
                If True with hex=True, compresses HEX when possible.

        Returns:
            str.

        Example, HEX:
            color = Color("rgb(255, 0, 0)")
            color.to_string(hex=True)
            # "#ff0000"

        Example, sRGB 0-255 with commas:
            color = Color("color(srgb 1 0 0 / 1)")
            color.to_string(comma=True, alpha=True)
            # "rgb(255, 0, 0, 1)"


    - delta_e(color: ColorInput, *, method: str | None = None, **kwargs) -> float
        Calculates the perceptual color difference between self and another color.

        Parameters:
            color:
                Color string, Color object, or dictionary representing a color.
            method:
                Delta E method. If None, uses Color.DELTA_E.
                In this project, default is "2000".
            **kwargs:
                Extra parameters for the selected Delta E method.

        Returns:
            float.

        Example:
            red = Color("red")
            blue = Color("blue")
            difference = red.delta_e(blue)
            # Uses DELTA_E = "2000"


    - contrast(color: ColorInput, method: str | None = None) -> float
        Calculates the contrast ratio between self and another color.

        Parameters:
            color:
                Color string, Color object, or dictionary representing a color.
            method:
                Contrast method. If None, uses Color.CONTRAST.
                In this project, default is "wcag21".

        Returns:
            float.

        Example:
            foreground = Color("white")
            background = Color("black")
            ratio = foreground.contrast(background)


    - closest(
        colors: Sequence[ColorInput],
        *,
        method: str | None = None,
        **kwargs
      ) -> Color | None
        Finds the closest color to self from a list of candidate colors.

        Parameters:
            colors:
                Sequence of color strings, Color objects, or dictionaries.
            method:
                Delta E method used for comparison.
                If None, uses Color.DELTA_E.
            **kwargs:
                Extra parameters for the selected Delta E method.

        Returns:
            Closest Color object, or None if the candidate list is empty.

        Example:
            target = Color("red")
            candidates = [Color("pink"), Color("yellow"), Color("maroon")]
            closest_color = target.closest(candidates)
            # color(srgb 0.50196 0 0 / 1), approximately "maroon"


    - mix(
        color: ColorInput,
        percent: float = 0.5,
        *,
        in_place: bool = False,
        **interpolate_args
      ) -> Color
        Mixes self with another color.

        Parameters:
            color:
                Color string, Color object, or dictionary to mix with.
            percent:
                How much the provided color contributes to the result.
                0.5 means 50/50.
            in_place:
                If False, returns a new Color.
                If True, mutates self.
            **interpolate_args:
                Interpolation options such as space, out_space, hue, etc.

        Returns:
            New Color object, or self when in_place=True.

        Example:
            red = Color("red")
            blue = Color("blue")
            purple = red.mix(blue, percent=0.5, space="hct")


    - steps(
        colors: Sequence[ColorInput],
        *,
        steps: int = 2,
        max_steps: int = 1000,
        max_delta_e: float = 0,
        delta_e: str | None = None,
        delta_e_args: dict | None = None,
        **interpolate_args
      ) -> list[Color]
        Generates discrete color steps from an interpolation.

        Parameters:
            colors:
                Sequence of color strings, Color objects, dictionaries,
                stops, or easing functions.
            steps:
                Minimum number of generated steps.
            max_steps:
                Maximum allowed number of steps.
            max_delta_e:
                If greater than 0, subdivides until no step exceeds this
                Delta E distance.
            delta_e:
                Delta E method used for distance checking.
                If None, uses Color.DELTA_E.
            delta_e_args:
                Extra Delta E parameters.
            **interpolate_args:
                Interpolation options such as space and out_space.

        Returns:
            list[Color].

        Example:
            gradient_steps = Color.steps(
                ["red", "blue"],
                steps=5,
                space="hct",
                out_space="srgb"
            )


    - get(
        name: str | list[str] | tuple[str, ...],
        *,
        nans: bool = True,
        precision: int | Sequence[int] | None = None,
        decimal: int | bool | Sequence[int | bool] | None = None
      ) -> float | list[float]
        Reads one or more channel values.

        Parameters:
            name:
                Channel name, channel index as string, or cross-space channel
                using "space.channel". Examples: "red", "alpha", "hct.tone".
            nans:
                If False, resolves undefined NaN values before returning.
            precision:
                Optional rounding precision.
            decimal:
                Optional decimal-place rounding control.

        Returns:
            float when name is a string.
            list[float] when name is a list or tuple.

        Example:
            color = Color("gray")
            tone = color.get("hct.tone", nans=False)


    - set(
        name: str | dict[str, float | Callable],
        value: float | Callable | None = None,
        *,
        nans: bool = True
      ) -> Color
        Sets one or more channel values.

        Parameters:
            name:
                Channel name, cross-space channel, or dictionary of channels.
                Examples: "red", "alpha", "hct.tone".
            value:
                New channel value or callback.
            nans:
                If False, callback inputs receive resolved values instead of NaN.

        Returns:
            Self, after mutation.

        Example:
            color = Color("blue").convert("hct")
            color.set("tone", 80)


    - coords(
        *,
        nans: bool = True,
        precision: int | Sequence[int] | None = None,
        decimal: int | bool | Sequence[int | bool] | None = None
      ) -> list[float]
        Returns the color channels, excluding alpha.

        Parameters:
            nans:
                If False, resolves undefined NaN values before returning.
            precision:
                Optional rounding precision.
            decimal:
                Optional decimal-place rounding control.

        Returns:
            list[float].

        Example:
            color = Color("rgb(255, 0, 0)")
            rgb_channels = color.coords(nans=False)
            # [1.0, 0.0, 0.0]


    - alpha(
        *,
        nans: bool = True,
        precision: int | None = None,
        decimal: int | bool | None = None
      ) -> float
        Returns the alpha channel.

        Parameters:
            nans:
                If False, resolves undefined NaN alpha values.
            precision:
                Optional rounding precision.
            decimal:
                Optional decimal-place rounding control.

        Returns:
            float.

        Example:
            color = Color("rgb(255 0 0 / 0.5)")
            opacity = color.alpha()
            # 0.5


    - is_achromatic() -> bool
        Checks whether the color is achromatic, meaning it has no meaningful hue
        and is effectively grayscale.

        Parameters:
            None.

        Returns:
            bool.

        Example:
            gray = Color("gray")
            gray.is_achromatic()
            # True


    - match(
        string: str,
        start: int = 0,
        fullmatch: bool = False
      ) -> ColorMatch | None
        Class method that attempts to match a color string at the given start
        position. It does not scan the entire string automatically.

        Parameters:
            string:
                CSS value or string buffer that may contain a color.
            start:
                Position where ColorAide should attempt to match a color.
            fullmatch:
                If True, the match must consume the rest of the string.

        Returns:
            ColorMatch object with:
                color: matched Color object.
                start: match start index.
                end: match end index.
            Returns None if no color is matched at start.

        Example, color inside a gradient value:
            gradient = "linear-gradient(90deg, rgb(255, 0, 0), #0000ff)"
            start = gradient.index("rgb")
            match = Color.match(gradient, start=start)

            if match is not None:
                matched_color = match.color
                # color(srgb 1 0 0 / 1)
    """

    DELTA_E = "2000"
    CONTRAST = "wcag21"
    INTERPOLATE = "hct"
    FIT = "lch-chroma"
    PRECISION = 5
    DECIMAL = True

    def __hash__(self) -> int:
        return hash(
            self
            .convert("srgb")
            .normalize(nans=False)
            .to_string(comma=True, alpha=True)
        )


@dataclass(frozen=True, slots=True)
class Tone:
    name: str
    value: int
    color: Color

    @property
    def to_var(self) -> str:
        return f"var({self.name})"
    
@dataclass(frozen=True, slots=True)
class Palette:
    name: str
    source_color: Color
    tones: tuple[Tone, ...] = field(default_factory=tuple)

    @property
    def steps(self) -> tuple[int, ...]:
        return (
            NEUTRAL_TONAL_STEPS
            if self.name == "Neutral"
            else TONAL_STEPS
        )

    def tone(self, value: int) -> Tone | None:
        return next((tone for tone in self.tones if int(tone.value) == int(value)), None)

    def get_highest_tone(self) -> Tone | None:
        """Returns the Tone object with the largest .value from the tuple."""
        return max(self.tones, key=lambda tone: tone.value)

    def get_lowest_tone(self) -> Tone | None:
        """Returns the Tone object with the smallest .value from the tuple."""
        return min(self.tones, key=lambda tone: tone.value)

    def shift_tone_by_steps(self, base_tone: Tone, steps: int) -> Tone:
        """
        Finds the base_tone in the tuple and shifts its position by the given steps.
        Caps the result at the boundaries if steps go out of bounds.
        """
        try:
            current_index = self.tones.index(base_tone)
        except ValueError:
            current_index = 0

        target_index = current_index + steps
        last_allowed_index = len(self.tones) - 1
        safe_index = min(max(0, target_index), last_allowed_index)

        return self.tones[safe_index]


@dataclass(slots=True)
class ColorScheme:
    """
    Color catalogue.

    colors:
        Stores unique Color objects.
        Key = standardized sRGB string.
        Value = ColorAide Color object.

    The stored value is always the object reference used by other domain entities.
    """

    colors: dict[str, Color] = field(default_factory=dict)
    palettes: dict[str, Palette] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Creates the default achromatic tonal palette.

        Neutral is always available when ColorScheme is instantiated.
        It includes tones 0 and 100.
        """

        self.add_palette(
            palette_name="Neutral",
            source_color_input="rgb(0, 0, 0)",
            steps=NEUTRAL_TONAL_STEPS
        )

    def add_color(self, color: str | Color) -> Color | None:
        """
        Parses a color and stores it if it is not duplicated.

        Returns the stored Color object so other entities can reference it.
        Returns None if the input is not a valid color.
        """
        new_color = color if isinstance(color, Color) else Color(color)
        unique_key = self.serialize_color(new_color)

        if unique_key not in self.colors:
            self.colors[unique_key] = new_color

        return self.colors[unique_key]

    def get_color(self, color_string: str) -> Optional[Color]:
        """
        Retrieves a Color object from the catalogue.

        It does not register anything.
        It only creates a temporary Color to calculate the same search key.
        """

        search_key = self.serialize_color(Color(color_string))

        return self.colors[search_key] if search_key in self.colors else None

    @staticmethod
    def serialize_color(color: Color) -> str:
        """
        Creates a standardized sRGB key.

        ColorAide's sRGB output already supports rgb(), comma syntax,
        names, hex, percent, and color(srgb ...) forms. For the catalogue,
        comma=True gives a stable readable key.
        """

        return (
            color
            .convert("srgb")
            .to_string(comma=True, alpha=True, rounding="decimal", precision=0)
        ) 

    def get_colors(self) -> dict[str, Color]:
        """Devuelve la instancia directa del catálogo de colores."""
        return self.colors

    def get_palette(self, palette_name: str) -> Optional[Palette]:
        """
        Retrieves a Palette object from the catalogue.

        It does not register anything.
        """

        return self.palettes[palette_name] if palette_name in self.palettes else None

    def get_palettes(self) -> dict[str, Palette]:
        """Devuelve la instancia directa del catálogo de paletas."""
        return self.palettes

    def get_all_palette_colors(self) -> list[Color]:
        """
        Extrae en una sola lista plana todas las referencias a los objetos Color
        almacenados exclusivamente en los tonos de todas las paletas registradas.
        Evita duplicados y operaciones redundantes.
        """
        unique_colors: list[Color] = []
        for palette in self.palettes.values():
            for tone in palette.tones:
                if tone.color not in unique_colors:
                    unique_colors.append(tone.color)
        return unique_colors

    def get_palette_colors(self, palette_name: str) -> list[Color]:
        """
        Extrae en una sola lista plana todas las referencias a los objetos Color
        almacenados en una paleta específica.
        Evita duplicados y operaciones redundantes.
        """
        unique_colors: list[Color] = []
        palette = self.get_palette(palette_name)
        if palette is None:
            return unique_colors

        for tone in palette.tones:
            if tone.color not in unique_colors:
                unique_colors.append(tone.color)
        return unique_colors

    def resolve_color_location(self, color: Color) -> tuple[Palette, Tone] | tuple[None, None]:
        """
        Identifica a qué Palette y a qué Tone pertenece exactamente una instancia de Color dada,
        mediante comparación directa de referencias de memoria (operador 'is').
        """
        for palette in self.palettes.values():
            for tone in palette.tones:
                if tone.color is color:
                    return palette, tone
        return None, None


    def find_closest(self, target_color: str | Color, color_pool: str = "colors") -> Any:
        """
        Calcula mediante ColorAide el objeto de color más cercano al string provisto,
        buscando estrictamente dentro del pool inyectado como parámetro.
        """
        try:
            target = Color(target_color)
            palette_name = color_pool.strip()

            match palette_name.lower():
                case "colors":
                    if not self.colors:
                        return None
                    return target.closest(list(self.get_colors().values()), method="2000")
                
                case "palettes":
                    if not self.palettes:
                        return None, None, None
                    closest_color = target.closest(self.get_all_palette_colors())
                    if closest_color is None:
                        return None, None, None
                        
                    # Extraemos palette, tone y el atributo steps directamente de la paleta encontrada
                    return next(
                        ((palette, tone, palette.steps) 
                         for palette in self.palettes.values() 
                         for tone in palette.tones 
                         if tone.color is closest_color),
                        (None, None, None)
                    )
                
                case _:
                    closest_color = target.closest(self.get_palette_colors(palette_name)) if self.get_palette(palette_name) is not None else None
                    if closest_color is None:
                        return None, None, None
                        
                    # Reemplazamos la variable genérica 'steps' por el atributo real 'palette.steps'
                    return next(
                        ((palette, tone, palette.steps) 
                         for palette in self.palettes.values() 
                         for tone in palette.tones 
                         if closest_color is not None and tone.color is closest_color),
                        (None, None, None)
                    )
                    
        except Exception as exc:
            # Tu bloque except flexible que captura y reporta de forma clara cualquier anomalía
            raise RuntimeError(
                f"Failed to find closest color due to an unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    def add_palette(
        self,
        palette_name: str,
        source_color_input: str | Color,
        steps: Iterable[int] = TONAL_STEPS
    ) -> Palette | None:
        """
        Generates and registers a tonal cam02-jmh palette.

        Uses ColorAide's cam02-jmh tonal palette strategy:
        """

        source_color = Color(source_color_input).convert("hct")
        source_color_key = self.serialize_color(source_color)
        existing_palette = next(
            (
                palette
                for palette in self.palettes.values()
                if self.serialize_color(palette.source_color) == source_color_key
            ),
            None,
        )

        if existing_palette is None:
            step_values = tuple(int(step) for step in steps)
            generated_colors = [source_color.clone().set('tone', step).fit('srgb', method='raytrace', pspace='hct') for step in step_values]
            tones = tuple(
                Tone(
                    name=f"--{palette_name}-{step}",
                    value=int(step),
                    color=color,
                )
                for color, step in zip(generated_colors, step_values)
            )

            palette = Palette(
                name=palette_name,
                source_color=source_color,
                tones=tones
            )

            self.palettes[palette_name] = palette

            return self.palettes[palette_name]
        else:
            return existing_palette      


