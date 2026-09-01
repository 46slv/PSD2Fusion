"""Build the smallest PSD fixture that exercises this clipping failure class."""

import argparse
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import BlendMode


def _banded_base(width, height):
    image = Image.new("RGBA", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            alpha = 64 if x < width // 3 else (144 if x < 2 * width // 3 else 255)
            red = 60 + (x * 96 // max(1, width - 1))
            green = 90 + (y * 96 // max(1, height - 1))
            pixels[x, y] = (red, green, 180, alpha)
    return image


def _normal_member(width, height):
    image = Image.new("RGBA", (width, height), (230, 70, 45, 0))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            if (x // max(1, width // 6) + y // max(1, height // 4)) % 2 == 0:
                pixels[x, y] = (230, 70, 45, 180)
    return image


def _multiply_member(width, height):
    image = Image.new("RGBA", (width, height), (70, 210, 100, 0))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            if x >= width // 4 and y >= height // 4:
                pixels[x, y] = (70, 210, 100, 220)
    return image


def build(output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    width, height = 480, 320
    psd = PSDImage.new("RGBA", (width, height), color=(36, 42, 52, 255))
    PixelLayer.frompil(
        Image.new("RGBA", (width, height), (36, 42, 52, 255)),
        psd,
        name="outer backdrop",
    )
    base = PixelLayer.frompil(
        _banded_base(width, height), psd, name="partial alpha base"
    )
    normal = PixelLayer.frompil(
        _normal_member(width, height), psd, name="normal clipped member"
    )
    normal.clipping = True
    multiply = PixelLayer.frompil(
        _multiply_member(width, height), psd, name="multiply opacity clipped member"
    )
    multiply.clipping = True
    multiply.blend_mode = BlendMode.MULTIPLY
    multiply.opacity = 128

    fixture = output / "clipping-micro-oracle.psd"
    psd.save(fixture)
    print(fixture)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
