import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    task_class: str
    risk: str
    decompose: bool


HIGH = ("architecture", "migration", "security", "infrastructure", "database schema", "auth")
MEDIUM = ("new screen", "navigation", "state", "api", "integration", "feature")


def classify(request: str) -> Classification:
    text = request.lower()
    if any(term in text for term in HIGH):
        task_class, risk = ("architecture_change" if "architecture" in text else "feature"), "HIGH"
    elif any(term in text for term in MEDIUM):
        task_class, risk = "feature", "MEDIUM"
    elif any(term in text for term in ("investigate", "diagnose", "why ")):
        task_class, risk = "investigation", "LOW"
    elif any(term in text for term in ("refactor", "cleanup", "restructure")):
        task_class, risk = "refactor", "MEDIUM"
    elif any(term in text for term in ("bug", "fix", "broken", "crash")):
        task_class, risk = "bug", "LOW"
    elif any(term in text for term in ("ui", "spacing", "color", "copy", "text", "layout")):
        task_class, risk = "ui_change", "LOW"
    else:
        task_class, risk = "small_fix", "LOW"
    return Classification(task_class, risk, risk == "HIGH" or len(request) > 800)


def acceptance_criteria(request: str) -> list[str]:
    sentences = [part.strip(" -") for part in re.split(r"[\n;]+", request) if part.strip()]
    return [f"Requested behavior is implemented: {sentence}" for sentence in sentences[:5]] or ["Requested behavior is implemented"]


def render_spec(*, request: str, repository_id: str, classification: Classification,
                memory: list[dict], attachments: list[str] | None = None,
                component_catalog: str = "- No component manifest available") -> str:
    criteria = acceptance_criteria(request)
    context = "\n".join(f"- [{item['category']}] {item['content']} (source: {item['source_reference']})" for item in memory) or "- No matching accepted project rules."
    images = "\n".join(f"- {path}" for path in attachments or []) or "- None"
    sections = {
        "Goal": request.strip(), "User request": request.strip(), "Repository": repository_id,
        "Execution mode": "Specification-driven, isolated workspace, agent branch and PR only",
        "Relevant project context": context,
        "Acceptance criteria": "\n".join(f"- {item}" for item in criteria),
        "Constraints": "- Never push main\n- Never merge or deploy production\n- Keep changes scoped",
        "Likely affected areas": "- Determine with targeted rg/git inspection before editing",
        "Component catalog": component_catalog,
        "Required validation": "- Determine affected components from the final diff.\n- Run each affected component's manifest validation.\n- Run global manifest validation.\n- Do not substitute checks from another language or subsystem.",
        "Risk level": classification.risk, "Screenshots/attachments": images,
        "Out of scope": "- Production merge/deploy and unrelated refactors", "Open questions": "- None",
    }
    return "# Engineering Specification\n\n" + "\n\n".join(f"## {name}\n\n{value}" for name, value in sections.items()) + "\n"


def decompose(request: str, classification: Classification) -> list[str]:
    if not classification.decompose:
        return []
    return ["Inspect domain and architecture impact", "Implement bounded code changes", "Add or update tests", "Run staged validation"]
