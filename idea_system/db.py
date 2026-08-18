from __future__ import annotations

import json
import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, url: str): self.url = url
    def connect(self): return psycopg.connect(self.url, row_factory=dict_row)
    def query(self, sql: str, params=()):
        with self.connect() as c: return c.execute(sql, params).fetchall()
    def one(self, sql: str, params=()):
        rows = self.query(sql, params); return rows[0] if rows else None
    def execute(self, sql: str, params=()):
        with self.connect() as c: return c.execute(sql, params).rowcount

    def mission(self): return self.one("SELECT * FROM missions WHERE code='MISSION_450M_5Y'")
    def active_contexts(self): return self.query("SELECT * FROM contexts WHERE active ORDER BY sort_order")
    def latest_completed(self):
        return self.one("SELECT * FROM generations WHERE mission_id=(SELECT id FROM missions WHERE code='MISSION_450M_5Y') AND status='completed' ORDER BY number DESC LIMIT 1")
    def ranking(self, number=None, limit=100):
        condition = "g.number=%s" if number is not None else "g.number=(SELECT max(number) FROM generations WHERE status='completed')"
        params = (number, limit) if number is not None else (limit,)
        return self.query(f"SELECT i.*,s.aggregate_score,s.evaluation_count,g.number generation_number FROM ideas i JOIN generations g ON g.id=i.generation_id JOIN idea_scores s ON s.idea_id=i.id WHERE g.status='completed' AND {condition} ORDER BY s.aggregate_score DESC,i.id LIMIT %s", params)
    def event(self, chat_id, direction, event_type, text, payload=None):
        self.execute("INSERT INTO telegram_events(chat_id,direction,event_type,text,payload) VALUES(%s,%s,%s,%s,%s::jsonb)", (chat_id,direction,event_type,text,json.dumps(payload or {})))
