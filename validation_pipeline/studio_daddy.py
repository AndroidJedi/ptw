"""Versioned molecular Post compositions. Copy, design and source art stay separate."""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import hashlib
import json
from typing import Mapping

from .natal_brand import NATAL_NAME_COLOR, NATAL_SYMBOL_COLOR, natal_logo_colored_bytes
from .studio import STUDIO_FONT_FAMILIES, StudioRenderer
from .studio_primitives import PrimitiveTemplate, PRIMITIVE_TEMPLATE_SCHEMA, PrimitivePreviewRenderer, TEXT_PROPERTIES
from .template_components import color, number, bounded_text, sha

SCHEMA = "ptw.studio.daddy.v1"
EDITOR = "post.daddy.react"
STYLES = ("photography", "editorial_illustration", "line_drawing", "paper_collage", "contemporary_3d")
SLOTS = {name: {"role": role, "description": description, "allowed_mime_types": ["image/png", "image/jpeg", "image/webp"]}
         for name, role, description in (
             ("scene", "background", "Contextual background with space for copy; no ad text."),
             ("subject", "hero", "Complete product, person, interaction or original illustration."),
             ("screen", "app_screen", "Generated app-screen interior; no hardware or outer ad copy."),
             ("feature", "secondary_media", "A close-up product feature or UI detail; no invented proof."),
             ("prop_one", "secondary_media", "First separate thematic object or second comparison scene."),
             ("prop_two", "secondary_media", "Second separate thematic object supporting the message."),
         )}

BASE = {
    "schema": SCHEMA, "preset": "bold_poster", "style": "photography",
    "logo": {"symbol_color": NATAL_SYMBOL_COLOR, "name_color": NATAL_NAME_COLOR},
    "background": {"enabled": True, "color": "#E9FF61", "end_color": "#B8E75B", "blur": 0, "overlay": 0, "overlay_color": "#091C2E", "shape": "plain"},
    "message": {"enabled": True, "x": 7, "y": 22, "width": 86, "title_size": 112, "body_size": 36, "gap": 24, "font": "Manrope", "color": "#101B25", "align": "left", "flow": True},
    "device": {"enabled": False, "x": 39, "y": 43, "width": 55, "height": 48, "rotation": -8, "pose": "portrait", "shadow": 24},
    "subject": {"enabled": False, "x": 15, "y": 42, "width": 70, "height": 45, "rotation": 0, "fit": "contain", "focal_x": .5, "focal_y": .5, "cutout": False},
    "collage": {"enabled": False, "x": 8, "y": 46, "width": 84, "height": 39, "rotation": 0, "gap": 24},
    "offer": {"enabled": True, "x": 7, "y": 72, "width": 78, "size": 36, "color": "#101B25", "fill": "#FFFFFF", "radius": 30},
    "brand": {"enabled": True, "x": 7, "y": 6, "width": 25},
    "action": {"enabled": True, "x": 7, "y": 88, "width": 70, "size": 32, "color": "#FFFFFF", "fill": "#101B25", "radius": 38, "badges": False},
}
COPY = {"hero_title": "Make room for what matters", "supporting_text": "One clear idea. Your next step.",
        "offer": "", "cta": "Discover more", "feature_title": "", "feature_text": "", "left_label": "", "right_label": "", "previous_price": ""}


def _preset(name, uk, description, slots=(), **overrides):
    config = deepcopy(BASE)
    for block, values in overrides.items():
        if isinstance(values, dict):
            config[block].update(values)
        else:
            config[block] = values
    return {"name": name, "name_uk": uk, "description": description, "slots": list(slots), "configuration": config}


PRESETS = {
    "phone_feature": _preset("Phone and feature", "Телефон і функція", "Show a useful app task and one enlarged detail.", ("screen", "feature"),
        background={"color": "#FCFAF7", "end_color": "#EDE9F3"}, message={"y": 16, "title_size": 78, "width": 87},
        device={"enabled": True, "x": 36, "y": 43, "height": 46, "pose": "angled"}, offer={"enabled": False}, action={"badges": True}),
    "offer_collage": _preset("Offer and collage", "Пропозиція та колаж", "An established offer with concrete thematic objects.", ("scene", "subject", "prop_one", "prop_two"),
        background={"color": "#0570B9", "end_color": "#16456A", "overlay": .3}, message={"y": 15, "title_size": 78, "color": "#FFFFFF"},
        subject={"enabled": True, "x": 55, "y": 45, "width": 45}, collage={"enabled": True, "y": 51}, offer={"y": 37, "fill": "#FF164A", "color": "#FFFFFF", "size": 58}, action={"fill": "#FF164A"}),
    "lifestyle": _preset("Emotional lifestyle", "Емоційна фотографія", "A recognizable human moment expressing the brand belief.", ("scene",),
        background={"color": "#514F43", "end_color": "#292F28", "overlay": .42}, message={"y": 17, "title_size": 84, "color": "#FFFFFF"},
        offer={"enabled": False}, action={"badges": True}),
    "still_life": _preset("Phone in a still life", "Телефон у тематичній сцені", "A domain-specific setting beside a readable app demonstration.", ("scene", "screen"),
        background={"color": "#EDE5D6", "end_color": "#D7CBBD", "shape": "split"}, message={"y": 17, "width": 45, "title_size": 70, "color": "#FFFFFF", "body_size": 30},
        device={"enabled": True, "x": 48, "y": 29, "width": 48, "height": 62, "rotation": 10}, offer={"x": 7, "y": 69, "width": 39, "size": 28}, action={"width": 39, "size": 26}),
    "blurred_phone": _preset("Phone on a blurred scene", "Телефон на розмитому фоні", "A standalone phone against a soft thematic background; no hands.", ("scene", "screen"),
        background={"color": "#F4EEE8", "end_color": "#DDD4CB", "blur": 18}, message={"y": 14, "title_size": 83},
        device={"enabled": True, "pose": "portrait", "x": 36, "y": 40, "height": 51, "width": 62, "rotation": 7}, offer={"y": 57, "width": 37, "size": 27}, action={"width": 40, "size": 26}),
    "playful_demo": _preset("Playful app demonstration", "Грайлива демонстрація", "Landscape app screen, curved color fields and small accents.", ("screen",),
        background={"color": "#FFF5E9", "end_color": "#EEE2FC", "shape": "wave"}, message={"y": 14, "title_size": 74, "align": "center"},
        device={"enabled": True, "pose": "landscape", "x": 7, "y": 40, "width": 86, "height": 30, "rotation": 0}, offer={"y": 75, "width": 86, "size": 30}, action={"badges": True}),
    "bold_poster": _preset("Bold text poster", "Яскравий текстовий постер", "One short hook on a vivid brand-colored field; no generated art."),
    "product_spotlight": _preset("Product spotlight", "Продукт у центрі", "One complete product or meaningful object with generous breathing room.", ("subject",),
        background={"color": "#FFF1DA", "end_color": "#EACEA8"}, message={"y": 15, "title_size": 82},
        subject={"enabled": True, "cutout": True}, offer={"y": 80, "size": 28}),
    "editorial_collage": _preset("Editorial collage", "Редакційний колаж", "Cut-paper layering and a coordinated set of separate subjects.", ("subject", "prop_one", "prop_two"),
        style="paper_collage", background={"color": "#FAF5E9", "end_color": "#E8DDC5", "shape": "paper"}, message={"y": 15, "title_size": 80},
        subject={"enabled": True, "x": 23, "width": 58, "cutout": True, "rotation": -5}, collage={"enabled": True}, offer={"enabled": False}),
    "illustrated_metaphor": _preset("Illustrated metaphor", "Ілюстрована метафора", "An original illustration makes the product meaning immediately recognizable.", ("subject",),
        style="editorial_illustration", background={"color": "#F4DBFB", "end_color": "#D8C4F5"}, message={"y": 15, "title_size": 82}, subject={"enabled": True}, offer={"enabled": False}),
    "drawing": _preset("Drawing and annotation", "Малюнок і пояснення", "A purposeful drawing with crisp, editable explanatory labels.", ("subject",),
        style="line_drawing", background={"color": "#FFFBEF", "end_color": "#EEE8D2", "shape": "drawing"}, message={"y": 15, "title_size": 82}, subject={"enabled": True}, offer={"y": 80, "size": 28}),
    "two_panel": _preset("Two-panel explanation", "Пояснення у двох панелях", "Contrast a problem with the product-assisted task; never invent outcomes.", ("subject", "prop_one"),
        background={"color": "#F6F4EF", "end_color": "#E2EAF2"}, message={"y": 15, "title_size": 76},
        subject={"enabled": True, "x": 7, "y": 47, "width": 40, "height": 32, "fit": "cover"}, collage={"enabled": True, "x": 53, "y": 47, "width": 40, "height": 32}, offer={"enabled": False}),
}
for _key, _value in PRESETS.items():
    _value["configuration"]["preset"] = _key

ENUMS = {"preset": tuple(PRESETS), "style": STYLES, "shape": ("plain", "split", "wave", "paper", "drawing"),
         "font": STUDIO_FONT_FAMILIES, "align": ("left", "center", "right"), "pose": ("portrait", "landscape", "angled"), "fit": ("contain", "cover")}
BOUNDS = {"x": (0, 95), "y": (0, 95), "width": (10, 100), "height": (10, 100), "title_size": (32, 150), "body_size": (24, 64),
          "size": (24, 100), "gap": (8, 80), "blur": (0, 40), "overlay": (0, .85), "rotation": (-30, 30), "shadow": (0, 60),
          "focal_x": (0, 1), "focal_y": (0, 1), "radius": (0, 100)}

# Additive appearance controls preserve the original preset geometry and digest.
# Old snapshots omit these controls and render with the same values below.
EXTRA = {
    "background": {"focal_x": .5, "focal_y": .5, "shape_color": "#C8BBFF",
        "annotation_kind": "circle", "annotation_x": 74/10.8, "annotation_y": 720/13.5,
        "annotation_width": 230/10.8, "annotation_height": 180/13.5, "annotation_rotation": 0},
    "device": {"feature_enabled": True, "feature_x": 120/10.8, "feature_y": 950/13.5,
        "feature_width": 75, "feature_height": 180/13.5, "feature_size": 30, "detail_size": 26,
        "feature_fill": "#FFFFFF", "feature_color": "#152030", "detail_color": "#354453"},
    "collage": {"second_x": 0, "second_y": 0, "second_rotation": 0},
    "brand": {"surface": False, "fill": "#FFFFFF", "padding": 16, "radius": 18},
}
BOUNDS.update(feature_x=BOUNDS["x"], feature_y=BOUNDS["y"], feature_width=BOUNDS["width"],
              feature_height=BOUNDS["height"], feature_size=(24,64), detail_size=(24,64),
              second_x=(-40,40), second_y=(-40,40), second_rotation=(-30,30))
ENUMS["annotation_kind"] = ("circle", "arrow")
BOUNDS.update(annotation_x=BOUNDS["x"], annotation_y=BOUNDS["y"], annotation_width=BOUNDS["width"],
              annotation_height=BOUNDS["height"], annotation_rotation=(-180,180))
BOUNDS["padding"] = (0,60)


def appearance_defaults(configuration):
    config = deepcopy(configuration)
    for block, values in EXTRA.items():
        defaults = deepcopy(values)
        if block == "background":
            defaults["shape_color"] = {"split":"#164775","paper":"#FFFFFF","drawing":"#E27845"}.get(config[block]["shape"],"#C8BBFF")
        config[block] = {**defaults, **config[block]}
    return config


def default_configuration(preset="bold_poster"):
    if preset not in PRESETS:
        raise ValueError("Unknown Daddy composition")
    config = appearance_defaults(PRESETS[preset]["configuration"])
    if preset in {"offer_collage", "lifestyle", "still_life"}:
        config["brand"]["surface"] = True
    return config


def normalize_configuration(value):
    if not isinstance(value, Mapping) or set(value) != set(BASE) or value.get("schema") != SCHEMA:
        raise ValueError("Daddy configuration fields are invalid")
    result = deepcopy(dict(value))
    for key, default in BASE.items():
        if isinstance(default, dict):
            extra = EXTRA.get(key, {})
            if not isinstance(value[key], Mapping) or not set(default).issubset(value[key]) or set(value[key]) - set(default) - set(extra):
                raise ValueError(f"Daddy {key} controls are invalid")
            for field, sample in {**extra, **default}.items():
                if field not in value[key]:
                    continue
                current = value[key][field]
                if isinstance(sample, bool):
                    if not isinstance(current, bool):
                        raise ValueError(f"Daddy {key}.{field} must be boolean")
                elif field in ENUMS:
                    if current not in ENUMS[field]:
                        raise ValueError(f"Daddy {key}.{field} option is invalid")
                elif isinstance(sample, str):
                    result[key][field] = color(current)
                else:
                    number(current, *BOUNDS[field])
        elif key != "schema" and value[key] not in ENUMS[key]:
            raise ValueError(f"Daddy {key} option is invalid")
    return result


def normalize_content(value):
    if not isinstance(value, Mapping) or set(value) not in (set(COPY), set(COPY)-{"previous_price"}):
        raise ValueError("Daddy content fields are invalid")
    limits = {"hero_title": 160, "supporting_text": 320, "offer": 120, "cta": 60, "feature_title": 100, "feature_text": 200, "left_label": 100, "right_label": 100, "previous_price": 40}
    return {k: bounded_text(v, limits[k], f"Daddy {k}", empty=True) for k, v in value.items()}


def required_slots(config):
    c = normalize_configuration(config)
    slots = list(PRESETS[c["preset"]]["slots"])
    enabled = {"scene": c["background"]["enabled"], "screen": c["device"]["enabled"], "feature": c["device"]["enabled"] and c["device"].get("feature_enabled",True),
               "subject": c["subject"]["enabled"], "prop_one": c["collage"]["enabled"], "prop_two": c["collage"]["enabled"]}
    for slot, block in (("screen", "device"), ("subject", "subject"), ("prop_one", "collage"), ("prop_two", "collage")):
        if slot == "prop_two" and c["preset"] == "two_panel":
            continue
        if c[block]["enabled"] and slot not in slots:
            slots.append(slot)
    return [slot for slot in slots if enabled[slot]]


def _png(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return {"bytes": output.getvalue(), "mime_type": "image/png"}


def device_asset(data, pose):
    """Hardware and aperture transform together; source screen pixels stay untouched."""
    from PIL import Image, ImageDraw, ImageOps, ImageFilter
    from .studio_phone_metrics import iphone_frame_record, IPHONE_SCREEN_BOX, IPHONE_SCREEN_RADIUS
    frame = Image.open(BytesIO(iphone_frame_record()["bytes"])).convert("RGBA")
    # Canonical frame aperture, proportional to its checked-in artwork.
    width, height = frame.size
    left, top, right, bottom = IPHONE_SCREEN_BOX
    margin = left
    screen = Image.new("RGBA", (right-left, bottom-top), "#F4F4F7")
    if data:
        source = Image.open(BytesIO(data)).convert("RGBA")
        screen = ImageOps.fit(source, screen.size, method=Image.Resampling.LANCZOS)
    mask = Image.new("L", screen.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, screen.width - 1, screen.height - 1), radius=IPHONE_SCREEN_RADIUS, fill=255)
    screen.putalpha(mask)
    result = Image.new("RGBA", frame.size)
    result.alpha_composite(screen, (left, top))
    result.alpha_composite(frame)
    if pose == "landscape":
        # Rotate hardware, then bind the landscape interior in its own orientation.
        result = result.rotate(90, expand=True)
        if data:
            area = (bottom-top, right-left)
            interior = ImageOps.fit(Image.open(BytesIO(data)).convert("RGBA"), area, method=Image.Resampling.LANCZOS)
            mask = Image.new("L", area, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, area[0]-1, area[1]-1), radius=IPHONE_SCREEN_RADIUS, fill=255)
            interior.putalpha(mask)
            base = Image.new("RGBA", result.size)
            base.alpha_composite(interior, (top, width-right))
            base.alpha_composite(frame.rotate(90, expand=True))
            result = base
    elif pose == "angled":
        # Solve the inverse homography into a padded canvas, preserving all corners.
        target = ((180,170), (width+80,60), (width+210,height+110), (230,height+300))
        source = ((0,0), (width,0), (width,height), (0,height))
        matrix = []
        for (x,y),(u,v) in zip(target,source):
            matrix.extend(([x,y,1,0,0,0,-u*x,-u*y,u], [0,0,0,x,y,1,-v*x,-v*y,v]))
        for col in range(8):
            pivot = max(range(col,8), key=lambda row:abs(matrix[row][col]))
            matrix[col],matrix[pivot] = matrix[pivot],matrix[col]
            factor = matrix[col][col]
            matrix[col] = [v/factor for v in matrix[col]]
            for row in range(8):
                if row != col:
                    factor = matrix[row][col]
                    matrix[row] = [a-factor*b for a,b in zip(matrix[row],matrix[col])]
        result = result.transform((width+400,height+400),Image.Transform.PERSPECTIVE,tuple(row[-1] for row in matrix),Image.Resampling.BICUBIC)
    return _png(result)


def render_assets(config, records):
    from PIL import Image, ImageFilter, ImageDraw
    c = appearance_defaults(normalize_configuration(config))
    result = {k: v for k, v in records.items() if v}
    # Missing art is explicit in the editor; keep a usable preview during asset preparation.
    for slot in required_slots(c):
        result.setdefault(slot, _png(Image.new("RGBA", (8, 8))))
    if "scene" in result and c["background"]["blur"]:
        image = Image.open(BytesIO(result["scene"]["bytes"])).convert("RGBA")
        image.thumbnail((1080, 1350))
        result["scene"] = _png(image.filter(ImageFilter.GaussianBlur(c["background"]["blur"])))
    for slot in ("subject", "prop_one", "prop_two"):
        if slot in result and (c["subject"]["cutout"] if slot == "subject" else c["preset"] in {"editorial_collage", "offer_collage"}):
            from .template_cutout import cutout_png
            result[slot] = {"bytes": cutout_png(result[slot]["bytes"]), "mime_type": "image/png"}
    result["device"] = device_asset(result.get("screen", {}).get("bytes"), c["device"]["pose"]) if c["device"]["enabled"] else None
    result["brand"] = {"bytes": natal_logo_colored_bytes(**{"symbol_color": c["logo"]["symbol_color"], "name_color": c["logo"]["name_color"]}), "mime_type": "image/png"}
    if c["action"]["badges"]:
        from .template_assets import asset_bytes
        for key, asset in (("apple_badge", "owner_app_store_badge_v1"), ("google_badge", "owner_google_play_badge_v1")):
            data, mime = asset_bytes(asset)
            result[key] = {"bytes": data, "mime_type": mime}
    if c["background"]["shape"] == "drawing" and c["background"]["annotation_kind"] == "arrow":
        arrow = Image.new("RGBA", (1000,500))
        draw = ImageDraw.Draw(arrow)
        draw.line([(60,250),(880,250)], fill=c["background"]["shape_color"], width=22)
        draw.line([(690,60),(880,250),(690,440)], fill=c["background"]["shape_color"], width=22, joint="curve")
        result["annotation"] = _png(arrow)
    return {k: v for k, v in result.items() if v}


def build_template(configuration, content):
    c, text = appearance_defaults(normalize_configuration(configuration)), normalize_content(content)
    nodes, roles, assets = [], {}, {}
    def node(identifier, kind, role, x, y, width, height, **props):
        nodes.append({"id": identifier, "type": kind, "props": {"position": "absolute", "x": x, "y": y, "width": width, "height": height, **props}})
        if role:
            roles.setdefault(role, []).append(identifier)
    def card(identifier, x, y, width, height, fill, **props):
        node(identifier, "card", None, x, y, width, height, background_color=fill, **props)
    def image(identifier, role, x, y, width, height, slot=None, **props):
        slot = slot or identifier
        assets[slot] = {"kind": "image", "allowed_mime_types": ["image/png", "image/jpeg", "image/webp"], "required": False, "provenance": "Digest-bound independent Daddy asset"}
        node(identifier, "image", role, x, y, width, height, asset=slot, fit="contain", **props)
    measure = PrimitivePreviewRenderer(StudioRenderer()._font)
    def copy(identifier, value, role, x, y, width, size, color_value, *, align="left", weight=600):
        if not value:
            return 0
        props = {k: deepcopy(v["default"]) for k, v in TEXT_PROPERTIES.items()}
        props.update(text=value, font_family=c["message"]["font"], font_size=size, font_weight=weight, color=color_value, line_height=1.12, text_align=align, text_fit="fixed")
        measured = measure.measure_text(props, width)
        height = max(size * 1.2, measured.get("line_box_height", size * 1.2) + size * .3)
        # measure_text exposes the same line metrics used for paint.
        if "lines" in measured:
            height = max(height, len(measured["lines"]) * size * 1.12 + size * .25)
        node(identifier, "text", role, x, y, width, height, **{k: props[k] for k in ("text", "font_family", "font_size", "font_weight", "color", "line_height", "text_align", "text_fit")})
        return height
    m = c["message"]
    # Measure with the exact selected font. Move dependent blocks, never silently shrink it.
    start = len(nodes)
    title_h = copy("measure_title",text["hero_title"],None,0,0,m["width"]*10.8,m["title_size"],m["color"],weight=800)
    body_h = copy("measure_body",text["supporting_text"],None,0,0,m["width"]*10.8,m["body_size"],m["color"],weight=400)
    del nodes[start:]
    message_bottom = m["y"]*13.5+title_h+(m["gap"]+body_h if body_h else 0)
    def flow_y(block):
        proposed = block["y"]*13.5
        if m["flow"] and m["enabled"] and m["width"] > 60:
            return max(proposed,message_bottom+28)
        return proposed
    b = c["background"]
    card("backdrop", 0, 0, 1080, 1350, b["color"], background_gradient=[b["color"], b["end_color"]])
    if "scene" in required_slots(c):
        image("scene", "secondary_media", 0, 0, 1080, 1350, focal_x=b["focal_x"], focal_y=b["focal_y"])
        nodes[-1]["props"]["fit"] = "cover"
    if b["overlay"]:
        card("scrim", 0, 0, 1080, 1350, b["overlay_color"], opacity=b["overlay"])
    if b["shape"] == "split":
        card("copy_panel", 0, 0, min(1080,(m["x"]+m["width"])*10.8+28), 1350, b["shape_color"])
    elif b["shape"] == "wave":
        card("wave_base", 0, 900, 1080, 450, b["shape_color"])
        node("wave", "shape", None, -180, 760, 1440, 300, shape="ellipse", fill=b["shape_color"])
    elif b["shape"] == "paper":
        card("paper", 40, 540, 1000, 630, b["shape_color"], rotation=-3, shadow_color="#302C23", shadow_blur=12)
    elif b["shape"] == "drawing":
        ax,ay,aw,ah = b["annotation_x"]*10.8,b["annotation_y"]*13.5,b["annotation_width"]*10.8,b["annotation_height"]*13.5
        if b["annotation_kind"] == "circle":
            node("annotation_ring", "shape", None, ax, ay, aw, ah, shape="ellipse", fill=b["color"], stroke_color=b["shape_color"], stroke_width=5, rotation=b["annotation_rotation"])
        else:
            image("annotation",None,ax,ay,aw,ah,rotation=b["annotation_rotation"])
    s = c["subject"]
    if s["enabled"]:
        image("subject", "hero", s["x"]*10.8, flow_y(s), s["width"]*10.8, s["height"]*13.5, rotation=s["rotation"], focal_x=s["focal_x"], focal_y=s["focal_y"])
        nodes[-1]["props"]["fit"] = "contain" if s["cutout"] else s["fit"]
    g = c["collage"]
    if g["enabled"]:
        if c["preset"] == "two_panel":
            image("prop_one", "secondary_media", g["x"]*10.8, flow_y(g), g["width"]*10.8, g["height"]*13.5)
        else:
            for index, slot in enumerate(("prop_one", "prop_two")):
                image(slot, "secondary_media", g["x"]*10.8 + index*(g["width"]*6.2+g["second_x"]*10.8), flow_y(g) + index*(g["gap"]+g["second_y"]*13.5), g["width"]*4.2, g["height"]*13.5, rotation=g["rotation"]+(-8+g["second_rotation"] if index else 8))
    d = c["device"]
    if d["enabled"]:
        image("device", "hero", d["x"]*10.8, flow_y(d), d["width"]*10.8, d["height"]*13.5, rotation=d["rotation"], alpha_outline_shadow_color="#152030", alpha_outline_shadow_blur=min(40, d["shadow"]), alpha_outline_shadow_y=12)
        if c["preset"] == "phone_feature" and d["feature_enabled"]:
            fx,fy,fw,fh = d["feature_x"]*10.8,d["feature_y"]*13.5,d["feature_width"]*10.8,d["feature_height"]*13.5
            card("feature_card", fx, fy, fw, fh, d["feature_fill"], radius=24, shadow_color="#182732", shadow_blur=12)
            image("feature", "secondary_media", fx+25, fy+18, min(140,fw*.2), max(30,fh-40))
            tx,tw = fx+min(188,fw*.24), max(30,fw-min(188,fw*.24)-32)
            h = copy("feature_title", text["feature_title"], "description", tx, fy+25, tw, d["feature_size"], d["feature_color"])
            copy("feature_text", text["feature_text"], "description", tx, fy+35+h, tw, d["detail_size"], d["detail_color"], weight=400)
    m = c["message"]
    if m["enabled"]:
        x, y, w = m["x"]*10.8, m["y"]*13.5, m["width"]*10.8
        h = copy("hero_title", text["hero_title"], "headline", x, y, w, m["title_size"], m["color"], align=m["align"], weight=800)
        copy("supporting_text", text["supporting_text"], "description", x, y+h+m["gap"], w, m["body_size"], m["color"], align=m["align"], weight=400)
    o = c["offer"]
    if o["enabled"] and text["offer"]:
        x,y,w = o["x"]*10.8, flow_y(o), o["width"]*10.8
        h = copy("offer", text["offer"], "meta", x+22, y+18, w-44, o["size"], o["color"])
        text_node = nodes.pop()
        card("offer_surface", x,y,w,h+36,o["fill"],radius=o["radius"])
        nodes.append(text_node)
        if text.get("previous_price"):
            ph = copy("previous_price", text["previous_price"], "meta", x+22, y+h+52, w-44, min(o["size"],36), m["color"], weight=400)
            node("previous_price_strike", "shape", None, x+20, y+h+52+ph*.46, min(w-40,len(text["previous_price"])*min(o["size"],36)*.6), 3, shape="line", fill=m["color"])
    if c["preset"] == "two_panel":
        for field,x in (("left_label",76),("right_label",572)):
            copy(field,text[field],"description",x,1080,420,28,m["color"])
    brand = c["brand"]
    if brand["enabled"]:
        if brand["surface"]:
            pad = brand["padding"]
            card("brand_surface",brand["x"]*10.8-pad,brand["y"]*13.5-pad,brand["width"]*10.8+2*pad,brand["width"]*10.8/4.6+2*pad,brand["fill"],radius=brand["radius"])
        image("brand", "brand", brand["x"]*10.8,brand["y"]*13.5,brand["width"]*10.8,brand["width"]*10.8/4.6)
    a = c["action"]
    if a["enabled"]:
        x,y,w = a["x"]*10.8,a["y"]*13.5,a["width"]*10.8
        if a["badges"]:
            image("apple_badge","cta",x,y,w*.47, w*.47/3)
            image("google_badge","cta",x+w*.51,y,w*.47,w*.47/3)
        elif text["cta"]:
            node("cta", "button", "cta", x,y,w,max(80,a["size"]*2.4),label=text["cta"],font_family=m["font"],font_size=a["size"],font_weight=600,label_color=a["color"],background_color=a["fill"],radius=a["radius"],text_align="center",vertical_align="center",padding=16)
    return PrimitiveTemplate.from_dict({"schema": PRIMITIVE_TEMPLATE_SCHEMA,"template_id":"daddy","template_type":"post","version":1,"status":"draft",
        "root":{"id":"canvas","type":"frame","props":{"width":1080,"height":1350},"children":nodes},"semantic_roles":roles,"assets":assets,"rules":[],"provenance":{"base_template_id":None,"base_version":None,"base_sha256":None,"reference_ids":[],"change_note":"Daddy modular composition"}})


def catalog():
    return {"schema":"ptw.studio.daddy-catalog.v1","template_id":"daddy","template_version":1,"name":"Daddy","canvas":{"width":1080,"height":1350},
        "presets":[{"id":key,**{k:deepcopy(v[k]) for k in ("name","name_uk","description","slots")},"configuration":default_configuration(key)} for key,v in PRESETS.items()],
        "styles":list(STYLES),"enums":{k:list(v) for k,v in ENUMS.items()},"bounds":deepcopy(BOUNDS),"asset_slots":deepcopy(SLOTS),
        "components":[{"component_id":key,"role":key,"setting_ids":[f"configuration.{key}"]} for key in BASE if key!="schema"]+[{"component_id":"copy","role":"copy","setting_ids":["content"]}],"sha256":sha(PRESETS)}


def agent_catalog():
    value = catalog()
    value["presets"] = [{k:v for k,v in p.items() if k!="configuration"} for p in value["presets"]]
    return value


def definition():
    from .post_templates import PostTemplateDefinition
    from .template_registry import TemplateCapabilities, TemplateIdentity
    return PostTemplateDefinition(identity=TemplateIdentity("post","daddy",1,sha({"presets":PRESETS,"schema":SCHEMA,"slots":SLOTS})),
        name="Daddy",description="Twelve modular compositions with independent assets, brand-aware generation and grouped tuning.",canvas={"width":1080,"height":1350},
        catalog=catalog,agent_catalog=agent_catalog,default_configuration=default_configuration,default_content=lambda:deepcopy(COPY),
        normalize_configuration=normalize_configuration,normalize_content=normalize_content,
        component_settings=lambda c,t:{"template_id":"daddy","configuration":normalize_configuration(c),"content":normalize_content(t),"sha256":sha([c,t])},
        capabilities=TemplateCapabilities(image_slots=tuple(SLOTS)),renderer_key="post.daddy.pillow.v1",editor_key=EDITOR,
        build_template=build_template,semantic_data=lambda c,t:{},asset_slots=lambda:deepcopy(SLOTS))


def neutral_document(configuration):
    from .template_components import new_component
    config = normalize_configuration(configuration)
    return {"name": f"Daddy · {PRESETS[config['preset']]['name']}", "description":"Reusable owner-tuned composition. Project copy and private assets are excluded.",
        "canvas":{"width":1080,"height":1350,"mobile_height":1350},"background":config["background"]["color"],
        "components":[new_component("identity","brand","brand",[70,60,250,50])],"daddy_configuration":config}


def saved_definition(record):
    from dataclasses import replace
    from .template_registry import TemplateIdentity
    config = normalize_configuration(record["document"]["daddy_configuration"])
    identity = TemplateIdentity("post",record["template_id"],record["template_version"],record["template_sha256"])
    def selected_catalog(compact=False):
        value = agent_catalog() if compact else catalog()
        value.update(template_id=identity.template_id,template_version=identity.template_version,sha256=identity.template_sha256)
        return value
    return replace(definition(),identity=identity,name=record["document"]["name"],description=record["document"]["description"],
        default_configuration=lambda:deepcopy(config),catalog=selected_catalog,agent_catalog=lambda:selected_catalog(True))
