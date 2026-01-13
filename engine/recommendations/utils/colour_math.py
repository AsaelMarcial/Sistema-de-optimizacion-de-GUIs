def rgb_to_luminance(rgb):
    """
    Calcula la luminancia relativa de un color RGB según WCAG 2.1.
    Entrada: (R, G, B) en rango 0-255.
    Salida: valor entre 0.0 (negro) y 1.0 (blanco).
    """
    def channel_lum(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)

def contrast_ratio(rgb1, rgb2):
    """
    Calcula la relación de contraste entre dos colores RGB.
    (L1 + 0.05) / (L2 + 0.05)
    """
    lum1 = rgb_to_luminance(rgb1)
    lum2 = rgb_to_luminance(rgb2)
    L1, L2 = max(lum1, lum2), min(lum1, lum2)
    return (L1 + 0.05) / (L2 + 0.05)

def adjust_color_brightness(rgb, target_contrast, bg_rgb, step=10):
    """
    Ajusta la claridad/oscuridad de un color RGB hasta alcanzar un contraste deseado con respecto a un fondo.
    """
    new_rgb = list(rgb)
    attempts = 0
    max_attempts = 25

    while contrast_ratio(new_rgb, bg_rgb) < target_contrast and attempts < max_attempts:
        if rgb_to_luminance(new_rgb) > rgb_to_luminance(bg_rgb):
            new_rgb = [max(0, c - step) for c in new_rgb]
        else:
            new_rgb = [min(255, c + step) for c in new_rgb]
        attempts += 1

    return tuple(new_rgb)
