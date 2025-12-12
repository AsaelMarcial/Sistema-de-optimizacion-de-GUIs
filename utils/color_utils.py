from utils.colour_math import rgb_to_luminance, contrast_ratio, adjust_color_brightness


def parse_rgb(css_value):
    """
    Convierte 'rgb(255, 255, 255)' a (255, 255, 255).
    """
    if css_value.startswith('rgb'):
        nums = css_value.strip('rgb()').split(',')
        return tuple(int(n.strip()) for n in nums[:3])
    return (255, 255, 255)

def rgb_to_css(rgb):
    """
    Convierte (255, 255, 255) a 'rgb(255, 255, 255)'.
    """
    return f'rgb({rgb[0]}, {rgb[1]}, {rgb[2]})'

def invert_rgb(rgb):
    """
    Invierte un color RGB: (255, 255, 255) -> (0, 0, 0).
    """
    return tuple(255 - x for x in rgb)

def is_light_color(rgb):
    r, g, b = rgb
    brightness = (r*299 + g*587 + b*114) / 1000  # Fórmula perceptual
    return brightness > 180


def parse_inline_styles(style_str):
    """
    Convierte 'color: red; background-color: blue;' a un diccionario.
    """
    styles = {}
    for item in style_str.split(';'):
        if ':' in item:
            key, value = item.split(':', 1)
            styles[key.strip()] = value.strip()
    return styles

def reconstruct_inline_style(styles_dict):
    """
    Convierte un diccionario de estilos a string CSS.
    """
    return '; '.join(f'{k}: {v}' for k, v in styles_dict.items())

def brighten_color(rgb, target_contrast, bg_color):
    """
    Wrapper para ajustar el brillo de un color hasta alcanzar contraste deseado.
    """
    return adjust_color_brightness(rgb, target_contrast, bg_color)