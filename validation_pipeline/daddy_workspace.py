"""Content-preserving conversion at the registered Daddy template boundary."""
from copy import deepcopy
from .studio_daddy import EDITOR, COPY


def switch_values(current, target, configuration, content, saved):
    fields = {"headline":"hero_title","description":"supporting_text","meta":"offer","cta":"cta"}
    copy = {key:content.get(key,"") for key in COPY}
    if current.editor_key != EDITOR:
        for key in ("hero_title", "supporting_text", "offer", "cta"):
            if isinstance(configuration.get(key), dict) and not configuration[key].get("enabled", True):
                copy[key] = ""
    if current.editor_key == "post.declarative.react":
        from .post_template_runtime import text_fields
        seen = set()
        for field in text_fields(current.document):
            role = field["role"]
            if role in fields and role not in seen:
                copy[fields[role]] = content["template_text"][field["id"]]
                seen.add(role)
    config = deepcopy((saved or {}).get("configuration") or target.default_configuration())
    for key in ("symbol_color", "name_color"):
        config["logo"][key] = configuration["logo"][key]
    if target.editor_key == EDITOR:
        result = deepcopy((saved or {}).get("content") or target.default_content())
        result.update({key:copy[key] for key in (COPY if current.editor_key == EDITOR else ("hero_title","supporting_text","offer","cta"))})
        return config,result
    result = target.default_content()
    result.update({key:copy[key] for key in ("hero_title","supporting_text","offer","cta")})
    if target.identity.template_id == "phone_metrics":
        for key in ("hero_title", "supporting_text", "offer"):
            if not result[key]:
                result[key] = target.default_content()[key]
                config[key]["enabled"] = False
    if target.editor_key == "post.declarative.react":
        from .post_template_runtime import text_fields
        for field in text_fields(target.document):
            if field["role"] in fields:
                result["template_text"][field["id"]] = copy[fields[field["role"]]]
    return config,result
