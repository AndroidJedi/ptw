import json

import pytest

from engineering.components import describe_manifest, load_manifest
from engineering.runner import StageFailure


def test_manifest_matches_overlapping_components_and_deduplicates_later(tmp_path) -> None:
    (tmp_path / "project.components.json").write_text(json.dumps({
        "version": 1,
        "global_validation": [["git", "diff", "--check"]],
        "components": [
            {"name": "app", "description": "all Dart", "paths": ["lib/**"],
             "validation": [["flutter", "test"]], "extended_validation": []},
            {"name": "templates", "description": "template package", "paths": ["lib/template_generator/**"],
             "validation": [["flutter", "test"]], "extended_validation": []},
        ],
    }))
    manifest = load_manifest(tmp_path)
    assert [item.name for item in manifest.matching(["lib/template_generator/a.dart"])] == ["app", "templates"]
    assert "templates: template package" in describe_manifest(manifest)


def test_invalid_manifest_fails_closed(tmp_path) -> None:
    (tmp_path / "project.components.json").write_text("{}")
    with pytest.raises(StageFailure) as failure:
        load_manifest(tmp_path)
    assert failure.value.stage == "VALIDATION_CONFIG"
