import base64
import hashlib
import json
import time
from unittest.mock import Mock

import pytest

from common.image_references import EphemeralImageReferences, persistable_image_request
from worker.main import _materialize_input_images
from tests.test_worker import png_header


def image():
    content = png_header(640, 320)
    return {'mime_type': 'image/png', 'width': 640, 'height': 320,
            'digest': hashlib.sha256(content).hexdigest(), 'bytes_base64': base64.b64encode(content).decode()}


def visual_artifact():
    content = png_header(640, 320)
    return {
        'name': 'approved_png', 'mime_type': 'image/png',
        'sha256': hashlib.sha256(content).hexdigest(),
        'bytes_base64': base64.b64encode(content).decode(),
    }


def test_job_parameters_never_contain_image_bytes():
    references = EphemeralImageReferences()
    request = {'mode': 'content_non_human_graphic_generation', 'input_images': [image()]}
    persisted, key = persistable_image_request(request, references)
    serialized = json.dumps(persisted)
    assert 'bytes_base64' not in serialized
    assert image()['bytes_base64'] not in serialized
    assert references.consume(key) == image()
    with pytest.raises(KeyError):
        references.consume(key)


def test_visual_artifact_bytes_are_ephemeral_and_never_persisted():
    references = EphemeralImageReferences()
    persisted, key = persistable_image_request({
        'mode': 'creative_visual_analysis', 'input_artifacts': [visual_artifact()],
    }, references)
    assert 'input_artifacts' not in persisted
    assert 'bytes_base64' not in json.dumps(persisted)
    assert persisted['input_reference']['name'] == 'approved_png'
    assert references.consume(key) == visual_artifact()


def test_ttl_capacity_explicit_cleanup_and_restart():
    references = EphemeralImageReferences(ttl_seconds=0.03, capacity=1)
    key = references.put(image())
    with pytest.raises(RuntimeError):
        references.put(image())
    time.sleep(0.06)
    with pytest.raises(KeyError):
        references.consume(key)
    key = references.put(image())
    references.discard(key)
    with pytest.raises(KeyError):
        references.consume(key)
    with pytest.raises(KeyError):
        EphemeralImageReferences().consume(key)


def test_worker_consumes_non_square_reference_and_checks_digest(tmp_path, monkeypatch):
    references = EphemeralImageReferences()
    persisted, key = persistable_image_request({'mode': 'content_non_human_graphic_generation', 'input_images': [image()]}, references)
    monkeypatch.setattr('worker.main.secrets.get', lambda _name: 'test-token')
    def consume(url, **kwargs):
        assert url.endswith(f'/{key}/consume')
        assert kwargs['headers'] == {'X-PTW-Bridge-Token': 'test-token'}
        return Mock(status_code=200, content=base64.b64decode(references.consume(key)['bytes_base64']))
    monkeypatch.setattr('worker.main.httpx.post', consume)
    paths, mapping = _materialize_input_images(persisted, tmp_path)
    assert paths[0].read_bytes() == png_header(640, 320)
    assert mapping[0]['sha256'] == image()['digest']
    assert paths[0].stat().st_mode & 0o777 == 0o600
    with pytest.raises(KeyError):
        references.consume(key)
    monkeypatch.setattr('worker.main.httpx.post', lambda *_a, **_kw: Mock(status_code=200, content=png_header(320, 640)))
    with pytest.raises(RuntimeError, match='exact PNG'):
        _materialize_input_images(persisted, tmp_path)
    monkeypatch.setattr('worker.main.httpx.post', lambda *_a, **_kw: Mock(status_code=410))
    with pytest.raises(RuntimeError, match='upload it again'):
        _materialize_input_images(persisted, tmp_path)


def test_enqueue_writes_only_reference_metadata_and_authenticated_consume_is_single_use(monkeypatch):
    from fastapi.testclient import TestClient
    from commander.main import app
    import commander.main as bridge
    references = EphemeralImageReferences()
    monkeypatch.setattr(bridge, 'image_references', references)
    monkeypatch.setattr(bridge.secrets, 'get', lambda _name: 'test-token')
    monkeypatch.setattr(bridge, 'allowed_user_ids', lambda: {1})
    monkeypatch.setattr(bridge, 'database_url', lambda _secrets: 'disposable-test')
    persisted = {}
    def execute(sql, args):
        if 'SELECT id,status FROM jobs' in sql:
            return Mock(fetchone=lambda: None)
        if 'INSERT INTO jobs' in sql:
            persisted.update(args[2].obj)
        return Mock(fetchone=lambda: (123,))
    connection = Mock(execute=execute)
    context = __import__('unittest').mock.MagicMock()
    context.__enter__.return_value = connection
    monkeypatch.setattr(bridge.psycopg, 'connect', lambda _url: context)
    request = {'mode': 'content_non_human_graphic_generation', 'system_prompt': 'Use reference with direction',
               'input_payload': {'visual_direction': 'Change background'}, 'output_schema': {'type': 'object'},
               'idempotency_key': 'reference-test', 'input_images': [image()]}
    client = TestClient(app)
    headers = {'X-PTW-Bridge-Token': 'test-token'}
    assert client.post('/internal/llm/structured', json=request).status_code == 403
    response = client.post('/internal/llm/structured', json=request, headers=headers)
    assert response.status_code == 200
    assert 'input_images' not in persisted
    assert 'bytes_base64' not in json.dumps(persisted)
    key = persisted['input_reference']['id']
    path = f'/internal/llm/input-reference/{key}/consume'
    assert client.post(path).status_code == 403
    result = client.post(path, headers=headers)
    assert result.content == png_header(640, 320)
    assert result.headers['cache-control'] == 'private, no-store'
    assert client.post(path, headers=headers).status_code == 410
