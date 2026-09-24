"""Deterministic, neutral UI fixtures for template inspection, never Project media.

These are code-drawn examples, not generated product screenshots or evidence.
Screen interiors share one family and leave camera/home-indicator safe areas.
"""
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageOps

from .studio_phone_metrics import (
    IPHONE_SCREEN_BOX, IPHONE_SCREEN_RADIUS, _screen_font, iphone_frame_record,
)


def _png(image):
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


@lru_cache(maxsize=3)
def app_screen(index: int) -> bytes:
    if index not in range(3):
        raise ValueError("Demo screen must be 0, 1 or 2")
    canvas = Image.new("RGB", (864, 1872), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    ink, muted, blue = "#17263C", "#52637A", "#2369DB"

    def text(x, y, value, size=32, weight=500, fill=ink):
        draw.text((x, y), value, font=_screen_font(size, weight), fill=fill, anchor="lt")

    def panel(y, height, fill="#FFFFFF"):
        draw.rounded_rectangle((48, y, 816, y + height), radius=24, fill=fill,
                               outline="#DCE5F0", width=2)

    def action(label):
        panel(1510, 104, blue)
        text(84, 1543, label, 32, 700, "#FFFFFF")
        text(60, 1680, "Overview", 27, fill=blue)
        text(335, 1680, "Requests", 27, fill=muted)
        text(660, 1680, "Profile", 27, fill=muted)

    text(52, 155, "INTERFACE PREVIEW", 26, 700, muted)
    text(52, 225, ["Your workspace", "New request", "Request details"][index], 52, 800)
    text(52, 310, "Example content for this template", 29, fill=muted)
    if index == 0:
        panel(408, 132)
        text(80, 454, "Search available options", 31, fill=muted)
        text(52, 610, "Choose a task", 36, 700)
        for y, title, subtitle in [(704, "Browse services", "Explore available options"),
                                   (900, "Create a request", "Choose a category and add details"),
                                   (1096, "View your requests", "Keep related details together")]:
            panel(y, 160)
            text(80, y + 32, title, 34, 700)
            text(80, y + 91, subtitle, 27, fill=muted)
            text(762, y + 49, "›", 42, fill=blue)
        action("Explore options")
    elif index == 1:
        text(52, 418, "Category", 30, 700)
        panel(480, 116)
        text(80, 522, "Select an option", 32, fill=muted)
        draw.line(((747, 526), (759, 538), (771, 526)), fill=blue, width=4)
        text(52, 684, "Details", 30, 700)
        panel(748, 360)
        text(80, 788, "Describe what you need…", 31, fill=muted)
        text(52, 1195, "Add a note", 30, 700)
        panel(1260, 116)
        text(80, 1300, "Optional", 31, fill=muted)
        action("Review request")
    else:
        text(52, 420, "Review before sending", 36, 700)
        for y, label, value in [(510, "CATEGORY", "Your selected option"),
                                (708, "DETAILS", "Your request description"),
                                (906, "NOTE", "Your optional note")]:
            panel(y, 162)
            text(80, y + 30, label, 25, 700, muted)
            text(80, y + 91, value, 32)
        panel(1178, 160, "#EAF1FC")
        text(80, 1226, "You can edit these details", 30)
        text(80, 1274, "before continuing.", 30)
        action("Continue")
    draw.rounded_rectangle((332, 1814, 532, 1824), radius=5, fill=ink)
    return _png(canvas)


@lru_cache(maxsize=1)
def walkthrough() -> bytes:
    """Complete canonical phones on native alpha, with opaque white interiors."""
    frame = Image.open(BytesIO(iphone_frame_record()["bytes"])).convert("RGBA")
    left, top, right, bottom = IPHONE_SCREEN_BOX
    size = (right - left, bottom - top)
    mask = Image.new("L", size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=IPHONE_SCREEN_RADIUS, fill=255)
    canvas = Image.new("RGBA", (1536, 1152))
    for index, (x, y, height) in enumerate(((32, 112, 960), (514, 56, 1040), (1037, 112, 960))):
        phone = Image.new("RGBA", frame.size)
        screen = ImageOps.contain(Image.open(BytesIO(app_screen(index))), size, Image.Resampling.LANCZOS)
        surface = Image.new("RGBA", size, "#F5F8FC")
        surface.paste(screen, ((size[0] - screen.width) // 2, (size[1] - screen.height) // 2))
        phone.paste(surface, (left, top), mask)
        phone.alpha_composite(frame)
        phone = phone.resize((round(height * frame.width / frame.height), height), Image.Resampling.LANCZOS)
        canvas.alpha_composite(phone, (x, y))
    return _png(canvas)
