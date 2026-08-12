from engineering.brain import Classification, classify, decompose, render_spec


def test_small_task_classification() -> None:
    result = classify("Fix spacing in the share card")
    assert result.task_class == "bug" and result.risk == "LOW"


def test_high_risk_classification_and_decomposition() -> None:
    result = classify("Change authentication architecture and database schema")
    assert result.risk == "HIGH" and len(decompose("task", result)) >= 3


def test_spec_has_acceptance_criteria_and_bounded_context() -> None:
    spec = render_spec(request="Update button copy", repository_id="ptw",
                       classification=Classification("ui_change", "LOW", False),
                       memory=[{"category":"design_rules", "content":"Use theme tokens", "source_reference":"docs/design.md"}])
    for heading in ("Goal", "User request", "Repository", "Acceptance criteria", "Required validation", "Risk level", "Out of scope"):
        assert f"## {heading}" in spec
    assert "Use theme tokens" in spec

