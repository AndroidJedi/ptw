import re
from typing import Any

CATEGORIES = ("architecture", "product_rules", "engineering_rules", "design_rules", "business_rules", "research_findings", "decisions", "known_pitfalls", "deployment_rules")


def relevant_categories(request: str) -> list[str]:
    text = request.lower()
    chosen = {"engineering_rules", "known_pitfalls"}
    for category in CATEGORIES:
        if category.replace("_", " ") in text:
            chosen.add(category)
    if any(word in text for word in ("ui", "screen", "layout", "color")): chosen.add("design_rules")
    if any(word in text for word in ("deploy", "firebase", "hosting")): chosen.add("deployment_rules")
    if any(word in text for word in ("architecture", "refactor", "navigation")): chosen.add("architecture")
    return sorted(chosen)


def retrieve(connection: Any, repository_id: str, request: str, *, limit: int = 8, max_chars: int = 6000) -> list[dict]:
    categories = relevant_categories(request)
    query = " ".join(re.findall(r"[A-Za-z0-9_]{3,}", request)[:20])
    rows = connection.execute(
        """SELECT category,title,content,source_reference,
                  ts_rank(to_tsvector('english', title || ' ' || content), plainto_tsquery('english', %s)) score
           FROM project_memory WHERE repository_id=%s AND status='accepted' AND category=ANY(%s)
           ORDER BY score DESC, updated_at DESC LIMIT %s""", (query, repository_id, categories, limit)
    ).fetchall()
    result, used = [], 0
    for category, title, content, source, _score in rows:
        remaining = max_chars - used
        if remaining <= 0: break
        bounded = content[:remaining]
        result.append({"category": category, "title": title, "content": bounded, "source_reference": source})
        used += len(bounded)
    return result
