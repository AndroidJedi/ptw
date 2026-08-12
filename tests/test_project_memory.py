from unittest.mock import MagicMock

from engineering.memory import relevant_categories, retrieve


def test_category_retrieval() -> None:
    assert "design_rules" in relevant_categories("Change UI screen layout")
    assert "deployment_rules" in relevant_categories("Deploy Firebase preview")


def test_source_references_and_bounded_size() -> None:
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = [
        ("engineering_rules", "Rule", "x" * 200, "docs/rules.md", 1.0),
        ("known_pitfalls", "Pitfall", "y" * 200, "job:12", 0.5),
    ]
    result = retrieve(connection, "ptw", "fix widget", limit=2, max_chars=250)
    assert result[0]["source_reference"] == "docs/rules.md"
    assert sum(len(item["content"]) for item in result) <= 250
    sql = connection.execute.call_args.args[0]
    assert "status='accepted'" in sql and "LIMIT" in sql


def test_superseded_rules_are_excluded_by_query() -> None:
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = []
    retrieve(connection, "ptw", "task")
    assert "status='accepted'" in connection.execute.call_args.args[0]
