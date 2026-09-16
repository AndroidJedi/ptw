from __future__ import annotations

from io import BytesIO
import unittest

from validation_pipeline.natal_brand import (
    NATAL_LOGO_PATH, NATAL_NAME_COLOR, NATAL_SYMBOL_COLOR,
    natal_logo_bytes, natal_logo_colored_bytes, normalize_natal_logo_colors,
)


@unittest.skipUnless(__import__("importlib").util.find_spec("PIL") is not None, "Pillow is required")
class NatalBrandColorTests(unittest.TestCase):
    def test_canonical_colors_return_the_verified_source_bytes(self) -> None:
        self.assertEqual(NATAL_LOGO_PATH.read_bytes(), natal_logo_bytes())
        self.assertEqual(
            natal_logo_bytes(),
            natal_logo_colored_bytes(NATAL_SYMBOL_COLOR, NATAL_NAME_COLOR),
        )

    def test_custom_colors_preserve_dimensions_and_exact_alpha_mask(self) -> None:
        from PIL import Image

        first = natal_logo_colored_bytes("#123456", "#ABCDEF")
        self.assertEqual(first, natal_logo_colored_bytes("#123456", "#ABCDEF"))
        with Image.open(BytesIO(natal_logo_bytes())) as source, Image.open(BytesIO(first)) as recolored:
            source = source.convert("RGBA")
            recolored = recolored.convert("RGBA")
            self.assertEqual(source.size, recolored.size)
            self.assertEqual(source.getchannel("A").tobytes(), recolored.getchannel("A").tobytes())
            opaque_symbol = [
                recolored.getpixel((x, y))[:3]
                for y in range(recolored.height) for x in range(0, 103)
                if recolored.getpixel((x, y))[3]
            ]
            opaque_name = [
                recolored.getpixel((x, y))[:3]
                for y in range(recolored.height) for x in range(103, recolored.width)
                if recolored.getpixel((x, y))[3]
            ]
            self.assertTrue(opaque_symbol)
            self.assertTrue(opaque_name)
            self.assertEqual({(18, 52, 86)}, set(opaque_symbol))
            self.assertEqual({(171, 205, 239)}, set(opaque_name))

    def test_colors_are_normalized_and_invalid_values_are_rejected(self) -> None:
        self.assertEqual(
            {"symbol_color": "#ABCDEF", "name_color": "#123456"},
            normalize_natal_logo_colors({
                "symbol_color": "#abcdef", "name_color": "#123456",
            }),
        )
        for invalid in (
            {"symbol_color": "red", "name_color": "#123456"},
            {"symbol_color": "#123456", "name_color": "#12345"},
            {"symbol_color": "#123456"},
        ):
            with self.assertRaises(ValueError):
                normalize_natal_logo_colors(invalid)


if __name__ == "__main__":
    unittest.main()
