"""Bounded public inquiry receipts in the existing append-only audit authority.

These are visitor correspondence, never Product Brief feedback, customer proof,
learning examples, or advertising payloads. No outbound message is sent here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
import threading
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends as DependsParameter

from .landing_publication import normalized_slug, canonical_json
from .local_brief_store import utc_now

ACTION = 'landing_inquiry.submitted'
SOURCES = {'apple', 'google', 'telegram', 'instagram', 'threads'}
CHANNELS = {'email', 'telegram', 'instagram'}


def normalize(request: Mapping[str, Any]) -> dict[str, Any]:
    if set(request) != {'request_id', 'source', 'question', 'contact', 'contact_channel', 'website', 'landing_version_sha256'}:
        raise ValueError('Inquiry fields are invalid')
    if any(not isinstance(value, str) for value in request.values()):
        raise ValueError('Inquiry fields must be text')
    value = {key: text.strip() for key, text in request.items()}
    value['request_id'] = str(UUID(value['request_id']))
    if value['source'] not in SOURCES or value['contact_channel'] not in CHANNELS:
        raise ValueError('Inquiry channel is invalid')
    if not re.fullmatch(r'[0-9a-f]{64}', value['landing_version_sha256']):
        raise ValueError('Inquiry version is invalid')
    if len(value['question']) > 2000 or len(value['contact']) > 320 or value['website']:
        raise ValueError('Inquiry content is invalid')
    if not value['question'] and not value['contact']:
        raise ValueError('Write a question or leave a contact')
    contact = value['contact']
    if contact:
        if value['contact_channel'] == 'email':
            valid = re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', contact)
        else:
            channel = value['contact_channel']
            if re.fullmatch(r'@?[A-Za-z0-9_.]{1,64}', contact):
                valid = True
            else:
                parsed = urlsplit(contact if '://' in contact else 'https://' + contact)
                hosts = {'t.me', 'telegram.me'} if channel == 'telegram' else {'instagram.com', 'www.instagram.com'}
                valid = parsed.scheme == 'https' and parsed.netloc.lower() in hosts and re.fullmatch(r'/[A-Za-z0-9_.]{1,64}/?', parsed.path) and not parsed.query and not parsed.fragment
        if not valid:
            raise ValueError('Enter an email or a profile link/nickname for the selected channel')
    return {key: value[key] for key in value if key != 'website'}


class DatabaseInquiryAudit:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def record(self, value: Mapping[str, Any]) -> bool:
        import psycopg
        from psycopg.types.json import Jsonb
        with psycopg.connect(self.database_url, connect_timeout=5) as db:
            # Serializes the rate bound and receipt reconciliation across workers.
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('landing-inquiry-request:' + value['request_id'],))
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('landing-inquiry:' + value['publication_id'],))
            if not db.execute("SELECT p.entity_id FROM landing_publications p JOIN validation_projects project ON project.entity_id=p.project_id WHERE p.entity_id=%s AND p.status='published' AND p.current_event_id=%s AND project.deleted_at IS NULL FOR SHARE OF p,project", (value['publication_id'], value['publication_event_id'])).fetchone():
                raise KeyError('Published page is unavailable')
            previous = db.execute('SELECT action,details FROM commander_audit_events WHERE id=%s', (value['request_id'],)).fetchone()
            if previous:
                if previous[0] != ACTION or previous[1].get('input_sha256') != value['input_sha256']:
                    raise ValueError('request_id was reused with different input')
                return False
            count = db.execute("SELECT count(*) FROM commander_audit_events WHERE action=%s AND details->>'publication_id'=%s AND created_at>clock_timestamp()-interval '1 minute'", (ACTION, value['publication_id'])).fetchone()[0]
            if count >= 30:
                raise RuntimeError('Too many inquiries; please try again shortly')
            db.execute('INSERT INTO commander_audit_events(id,actor,action,target_id,details) VALUES(%s,%s,%s,%s,%s)', (value['request_id'], 'public-landing', ACTION, value['landing_version_id'], Jsonb(dict(value))))
        return True

    def list(self, project_id: str) -> list[dict[str, Any]]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as db:
            rows = db.execute("SELECT id,details,created_at FROM commander_audit_events WHERE action=%s AND details->>'project_id'=%s ORDER BY created_at DESC,id DESC LIMIT 50", (ACTION, project_id)).fetchall()
        return [{**row[1], 'request_id': str(row[0]), 'created_at': row[2].isoformat()} for row in rows]


class LocalInquiryAudit:
    def __init__(self, store: Any):
        self.store, self.lock = store, threading.RLock()

    def record(self, value: Mapping[str, Any]) -> bool:
        with self.lock:
            try:
                previous = self.store.get('landing_inquiry', value['request_id'])
            except KeyError:
                previous = None
            if previous:
                if previous['input_sha256'] != value['input_sha256']:
                    raise ValueError('request_id was reused with different input')
                return False
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
            recent = [item for item in self.store.list('landing_inquiry') if item['publication_id'] == value['publication_id'] and datetime.fromisoformat(item['created_at']) > cutoff]
            if len(recent) >= 30:
                raise RuntimeError('Too many inquiries; please try again shortly')
            self.store.append('landing_inquiry', value['request_id'], {**value, 'created_at': utc_now()})
        return True

    def list(self, project_id: str) -> list[dict[str, Any]]:
        return sorted((item for item in self.store.list('landing_inquiry') if item['project_id'] == project_id), key=lambda item: item['created_at'], reverse=True)[:50]


class LandingInquiries:
    def __init__(self, audit: Any, publications: Any):
        self.audit, self.publications = audit, publications

    def submit(self, slug: str, request: Mapping[str, Any]) -> dict[str, Any]:
        slug = normalized_slug(slug)
        value = normalize(request)
        publication, event, _, _ = self.publications._active(slug)
        if event['landing_version_sha256'] != value['landing_version_sha256']:
            raise ValueError('The page changed; reload before sending your inquiry')
        value.update(project_id=publication['project_id'], publication_id=publication['publication_id'], publication_event_id=event['event_id'], landing_version_id=event['landing_version_id'], slug=slug)
        value['input_sha256'] = hashlib.sha256(canonical_json(value).encode()).hexdigest()
        created = self.audit.record(value)
        return {'accepted': True, 'created': created, 'request_id': value['request_id']}

    def inbox(self, project_id: str) -> dict[str, Any]:
        project_id = str(UUID(project_id))
        # Authentication and the active-project guard are owned by the router.
        return {'items': self.audit.list(project_id)}


def inquiry_router(service: LandingInquiries, *, prefix: str, public: bool, dependencies: Sequence[DependsParameter] = ()) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))
    if public:
        @router.post('/{slug}/inquiries', status_code=202)
        def submit(slug: str, request: Mapping[str, Any]) -> dict[str, Any]:
            try:
                return service.submit(slug, request)
            except (KeyError, ValueError, RuntimeError) as error:
                status = 404 if isinstance(error, KeyError) else 429 if isinstance(error, RuntimeError) else 400
                raise HTTPException(status_code=status, detail=str(error).strip("'")) from error
    else:
        @router.get('/projects/{project_id}/inquiries')
        def inbox(project_id: str, response: Response) -> dict[str, Any]:
            response.headers['Cache-Control'] = 'no-store'
            try:
                return service.inbox(project_id)
            except ValueError as error:
                raise HTTPException(status_code=400, detail='Project ID is invalid') from error
    return router
