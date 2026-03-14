# Color Palette Reconstruction Notes

## Current state

- `pixels_to_color_frequency` is correct for a raw RGB histogram.
- It is safe to keep using that raw histogram for environmental estimation because that flow intentionally measures the full rendered screenshot.
- It is not sufficient on its own for palette reconstruction of the design language.

## Why the raw histogram is not enough

- It counts every visible pixel, including photos, videos, animated media, gradients and anti-aliasing noise.
- It also counts transient paint like shadows, blur and subpixel edges that do not represent the intended design palette.
- A full screenshot histogram is therefore a good "display energy" input, but a noisy "design palette" input.

## Material Color Utilities fit

The local Material Color Utilities docs recommend this flow:

1. Convert the image to ARGB pixels.
2. Resize to `128x128` for speed.
3. Quantize with `QuantizerCelebi`.
4. Rank prominent colors with `Score`.

In the Java sources:

- `QuantizerCelebi` seeds clusters with `QuantizerWu`.
- `QuantizerWsmeans` then refines those clusters with a weighted K-Means variant.

That flow does apply to this project, but not directly on the raw full screenshot used for energy estimation.

## Recommended split

- Energy estimation:
  Use the full screenshot exactly as today.

- Palette reconstruction:
  Build a filtered input first, then quantize.

## Recommended filtered input for palette reconstruction

- Start from snapshot colors declared directly on elements.
- Keep brand-bearing vector elements like icons, bullets and logos when they are represented by DOM elements and tracked styles.
- Exclude or mask:
  - `img`
  - `picture`
  - `video`
  - animated media
  - decorative shadows when they are not part of the brand palette

## Practical next step

Use two parallel inputs:

- Full screenshot for energy.
- Filtered palette input for design colors.

The new canonical module for this work is `engine/color_processing`.
