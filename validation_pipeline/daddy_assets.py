"""Independent digest-addressed Daddy assets with request reconciliation."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from functools import lru_cache
from uuid import UUID

from .studio_daddy import EDITOR, SLOTS, required_slots
from .image_reference import decode_reference, generate_image
from .image_generation_policy import compile_image_prompt, image_provenance
from .template_components import sha, bounded_text


def check_slot(workspace, slot):
    if workspace._definition().editor_key != EDITOR or slot not in SLOTS:
        raise ValueError("Select a declared Daddy asset slot")


def history(workspace, slot):
    check_slot(workspace, slot)
    path = workspace.assets / f"{slot}_history.json"
    if not path.exists():
        current = workspace._asset_record(slot)
        return [] if current is None else [{k:v for k,v in current.items() if k!="bytes"}]
    value = json.loads(path.read_text())
    if value.get("schema") != "ptw.studio.asset-history.v1" or not isinstance(value.get("items"), list) or len(value["items"]) > 3:
        raise ValueError("Asset history is invalid")
    return value["items"]


def read_history(workspace, slot, digest):
    from pathlib import Path
    item = next((v for v in history(workspace, slot) if v.get("sha256") == digest), None)
    if not item or Path(item["filename"]).name != item["filename"]:
        raise KeyError("Asset is not retained in this slot")
    data = (workspace.assets / item["filename"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Asset digest mismatch")
    return {**item, "bytes":data}


def summaries(workspace, slot):
    current = workspace._asset_record(slot)
    return [{"sha256":v["sha256"], "mime_type":v["mime_type"], "width":v["width"], "height":v["height"],
             "source":v["source"], "selected":bool(current and current["sha256"]==v["sha256"])} for v in history(workspace,slot)]


def store(workspace, slot, data, mime_type, source):
    check_slot(workspace, slot)
    previous = history(workspace,slot)
    for item in previous:
        if not item["filename"].startswith(f"{slot}_history_"):
            original = (workspace.assets / item["filename"]).read_bytes()
            item["filename"] = f"{slot}_history_{item['sha256']}.png"
            workspace._atomic_bytes(workspace.assets/item["filename"], original)
    workspace._store_asset(slot,mime_type=mime_type,data=data,source=source)
    item = {k:v for k,v in workspace._asset_record(slot).items() if k!="bytes"}
    extension = {"image/png":"png","image/jpeg":"jpg","image/webp":"webp"}[mime_type]
    item["filename"] = f"{slot}_history_{item['sha256']}.{extension}"
    workspace._atomic_bytes(workspace.assets/item["filename"],data)
    items = [item, *[v for v in previous if v["sha256"]!=item["sha256"]]][:3]
    workspace._atomic_json(workspace.assets/f"{slot}_history.json",{"schema":"ptw.studio.asset-history.v1","slot":slot,"items":items})
    keep = {v["filename"] for v in items}
    for path in workspace.assets.glob(f"{slot}_history_*.*"):
        if path.name not in keep:
            path.unlink()


def operate(workspace, *, slot, base_sha256, request_id, action, options, image_context=None, progress=None):
    check_slot(workspace,slot)
    request_id = str(UUID(str(request_id)))
    if action not in {"generate","upload","select","stock","registered"} or not isinstance(options,dict):
        raise ValueError("Asset action is invalid")
    receipt_path = workspace.root / "asset-requests.json"
    receipts = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    fingerprint = sha([slot,base_sha256,action,options])
    if request_id in receipts:
        if receipts[request_id]!=fingerprint:
            raise RuntimeError("Asset request ID was reused with different input")
        return workspace.detail()
    workspace._assert_state(base_sha256)
    current = workspace._asset_record(slot)
    original = None
    if action == "generate":
        if set(options)-{"visual_direction","enhance_current","reference_image"} or not image_context:
            raise ValueError("Asset generation fields are invalid")
        bounded_text(options.get("visual_direction"),600,"Visual direction")
        enhance = options.get("enhance_current",False)
        if not isinstance(enhance,bool) or (enhance and (not current or options.get("reference_image"))):
            raise ValueError("Enhance requires a current image and no uploaded reference")
        reference = decode_reference(options["reference_image"]) if options.get("reference_image") else current["bytes"] if enhance else None
        result = generate_image(workspace.image_provider,compile_image_prompt(image_context),reference_image=reference,
            uploaded_reference=bool(options.get("reference_image")),output_spec=image_context.get("output_spec"),operation_key=f"daddy:{workspace.root.name}:{request_id}",progress=progress)
        data,mime = result["bytes"],result["mime_type"]
        source = {**result.get("source",{}),**image_provenance(image_context),"visual_direction":options["visual_direction"],
                  "request_id":request_id,
                  **({"reference_asset_sha256":current["sha256"]} if enhance else {})}
    elif action == "upload":
        if set(options)!={"image"}:
            raise ValueError("Upload requires one image")
        data,mime = decode_reference(options["image"]),"image/png"
        original = base64.b64decode(options["image"]["bytes_base64"],validate=True)
        original_digest = hashlib.sha256(original).hexdigest()
        source = {"origin":"owner_upload","original_sha256":original_digest,"original_filename":f"{slot}_original_{original_digest}.bin"}
    elif action == "select":
        if set(options)!={"sha256"}:
            raise ValueError("Select requires an exact retained digest")
        selected = read_history(workspace,slot,options["sha256"])
        data,mime,source = selected["bytes"],selected["mime_type"],selected["source"]
    elif action == "stock":
        if set(options)!={"photo_id"} or slot=="screen":
            raise ValueError("Stock requires a photo ID and a photographic slot")
        import os
        from .images import PexelsClient
        client = PexelsClient(os.environ.get("PEXELS_API_KEY", ""))
        photo = client.get(options["photo_id"])
        data,mime,source = client.download(photo),"image/jpeg",photo.source_metadata()
    else:
        from .template_assets import IMAGE_ASSET_IDS,asset_bytes,asset_metadata,is_reference_identity
        if set(options)!={"asset_id"} or options["asset_id"] not in IMAGE_ASSET_IDS or is_reference_identity(options["asset_id"]):
            raise ValueError("Choose a registered image asset")
        data,mime = asset_bytes(options["asset_id"])
        source = {"origin":"registered_asset","asset_id":options["asset_id"],"registration":asset_metadata(options["asset_id"])}
    workspace._assert_state(base_sha256)
    before = {path.name:path.read_bytes() for path in workspace.assets.iterdir() if path.is_file()}
    try:
        if original is not None:
            workspace._atomic_bytes(workspace.assets/source["original_filename"],original)
        if action=="select":
            workspace._store_asset(slot,mime_type=mime,data=data,source=source)
        else:
            store(workspace,slot,data,mime,source)
        # Validate all new source bytes and their deterministic rendering before commit.
        workspace.render_preview(state_sha256=workspace.state_sha256())
        workspace._atomic_json(receipt_path,{**receipts,request_id:fingerprint})
        return workspace.detail()
    except Exception:
        for path in workspace.assets.iterdir():
            if path.is_file() and path.name not in before:
                path.unlink()
        for name,data in before.items():
            workspace._atomic_bytes(workspace.assets/name,data)
        raise


def sources(query):
    import os
    from .template_assets import image_asset_catalog
    from .images import PexelsClient
    bounded_text(query, 160, "Stock search", empty=True)
    photos = PexelsClient(os.environ.get("PEXELS_API_KEY", "")).search(query, per_page=8) if query.strip() and os.environ.get("PEXELS_API_KEY") else []
    return {"registered": image_asset_catalog(), "stock_available": bool(os.environ.get("PEXELS_API_KEY")),
            "photos": [{"photo_id":v.photo_id,"description":v.alt,"image_url":v.image_url,"source":v.source_metadata()} for v in photos]}


def preset_preview(preset):
    """Neutral native template thumbnails; never production Project artwork."""
    return _preset_preview(preset)


@lru_cache(maxsize=12)
def _preset_preview(preset):
    from .studio_daddy import default_configuration
    return neutral_render(default_configuration(preset))["bytes"]


def neutral_render(config):
    from io import BytesIO
    from PIL import Image, ImageDraw
    from .studio_daddy import default_configuration, COPY, render_assets, build_template
    from .studio import StudioRenderer
    from .template_demo_assets import app_screen
    art = Image.new("RGBA", (700,700))
    draw = ImageDraw.Draw(art)
    draw.rounded_rectangle((100,70,610,610),radius=95,fill="#72B7AF")
    draw.ellipse((240,230,470,460),fill="#E8FA85")
    stream = BytesIO(); art.save(stream,format="PNG")
    records = {s:{"bytes":(_landscape_fixture() if config["device"]["pose"] == "landscape" else app_screen(0)) if s in {"screen","feature"} else stream.getvalue(),"mime_type":"image/png"} for s in required_slots(config)}
    copy = {**COPY,"feature_title":"One useful detail","feature_text":"A closer look at the product.","left_label":"The everyday task","right_label":"With your product"}
    return StudioRenderer().render_preview(build_template(config, copy), semantic_data={}, assets=render_assets(config, records))


@lru_cache(maxsize=1)
def _landscape_fixture():
    """Neutral gallery UI in its native aperture; never crop a portrait interface."""
    from io import BytesIO
    from PIL import Image, ImageDraw
    from .studio_phone_metrics import _screen_font
    canvas = Image.new("RGB", (1872,864), "#F5F8FC")
    draw = ImageDraw.Draw(canvas)
    draw.text((180,90),"Choose a task",font=_screen_font(92,700),fill="#17263C")
    for x,label,color_value in ((180,"Explore","#E7EFFA"),(990,"Create","#E9F2CB")):
        draw.rounded_rectangle((x,280,x+680,620),radius=42,fill=color_value)
        draw.text((x+52,405),label,font=_screen_font(80,600),fill="#17263C")
    draw.text((180,716),"Interface preview",font=_screen_font(50,500),fill="#52637A")
    output=BytesIO();canvas.save(output,format="PNG");return output.getvalue()
