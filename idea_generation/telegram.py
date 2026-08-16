from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any

from .engine import EvolutionEngine
from .store import PostgresStore

HELP = """Idea Evolution v1
/status /run [N] /stop /continue /pause /resume /autopilot on|off|24h
/ranking /generation N /idea ID /top [N] /history [N] /lineage ID
/report [G7] /reports [N]
/idea_add TEXT /idea_queue /idea_cancel ID
/guidance TEXT /guidance_list /guidance_clear ID /feedback IDEA_ID TEXT /keep IDEA_ID [TEXT] /reject IDEA_ID [REASON]
/contexts /context C03 /context_set C03 TEXT /context_name C03 NAME /context_history C03 /context_restore C03 VERSION /context_enable C03 /context_disable C03
/executions [N] /errors [N] /cost /task /help"""


class TelegramController:
    def __init__(self, store: PostgresStore, engine: EvolutionEngine, allowed_chat_ids: frozenset[int]) -> None:
        self.store, self.engine, self.allowed = store, engine, allowed_chat_ids
        self.notifications: list[str] = []
        self.engine.notify = self.notifications.append

    def handle(self, chat_id: int, text: str) -> str:
        if chat_id not in self.allowed: return "Unauthorized."
        text = self._freeform(text.strip())
        self.notifications.clear()
        self._event(chat_id, "in", "command", text)
        command, _, tail = text.partition(" ")
        try:
            result = self._dispatch(command.lower(), tail.strip())
        except Exception as error:
            result = f"Error: {error}"
        if self.notifications:
            result = "\n\n".join([*self.notifications, result])
        self._event(chat_id, "out", "response", result)
        return result

    def _dispatch(self, command: str, arg: str) -> str:
        mission = self.store.mission()
        if command == "/help": return HELP
        if command == "/task": return mission["task_text"]
        if command == "/status":
            active = self.store.fetchone("SELECT number,status FROM generations WHERE status IN ('creating','created','evaluating') ORDER BY number LIMIT 1")
            latest = self.store.fetchone("SELECT number FROM generations WHERE status='completed' ORDER BY number DESC LIMIT 1")
            progress = ""
            if active:
                done = self.store.fetchone("SELECT COUNT(DISTINCT evaluator_context_id) n FROM idea_evaluations e JOIN ideas i ON i.id=e.idea_id JOIN generations g ON g.id=i.generation_id WHERE g.number=%s", (active["number"],))["n"]
                progress = f"\nRunning: YES\nGeneration: G{active['number']}\nPhase: {active['status'].upper()}\nProgress: {done}/10 evaluator contexts"
            return (f"Mission: {mission['status'].upper()}\nAutopilot: {'ON' if mission['auto_enabled'] else 'OFF'}{progress}\n"
                    f"Latest completed: {'none' if not latest else 'G'+str(latest['number'])}\nRun-series remaining: {mission['run_series_remaining']}")
        if command == "/run":
            count = int(arg or "1"); done = self.engine.run_series(count)
            return f"Completed: {', '.join('G'+str(n) for n in done) or 'none'}"
        if command == "/continue": return f"Completed: {self.engine.continue_series()}"
        if command == "/stop": self.store.update_mission(stop_after_current_cycle=True); return "Will stop at the next safe generation boundary."
        if command in {"/pause", "/resume"}:
            self.store.update_mission(status="paused" if command == "/pause" else "active", **({"auto_enabled": False} if command == "/pause" else {}))
            return "Mission paused; autopilot OFF." if command == "/pause" else "Mission resumed; autopilot remains unchanged."
        if command == "/autopilot":
            if arg not in {"on", "off", "24h"}: raise ValueError("use /autopilot on|off|24h")
            self.store.update_mission(auto_enabled=arg != "off", cadence_hours=24)
            return f"Autopilot: {'OFF' if arg == 'off' else 'ON (24h)'}"
        if command in {"/ranking", "/generation"}:
            number = int(arg) if command == "/generation" else None
            if number is None:
                row = self.store.fetchone("SELECT number FROM generations WHERE status='completed' ORDER BY number DESC LIMIT 1")
                if not row: return "No completed generations."
                number = row["number"]
            rows = self._ranking(number)
            return f"G{number}\n" + "\n".join(f"{i}. #{r['idea_id']} {r['aggregate_score']} ({r['mode']}) {r['title']}" for i,r in enumerate(rows,1))
        if command == "/top":
            limit = min(100, max(1, int(arg or "10")))
            rows = self.store.fetchall("""SELECT i.id idea_id,i.title,g.number,s.aggregate_score FROM ideas i JOIN generations g ON g.id=i.generation_id JOIN idea_scores s ON s.idea_id=i.id
                WHERE g.status='completed' ORDER BY s.aggregate_score DESC,i.id LIMIT %s""", (limit,))
            return "\n".join(f"#{r['idea_id']} G{r['number']} {r['aggregate_score']} {r['title']}" for r in rows) or "No completed ideas."
        if command == "/history":
            limit = min(100, max(1, int(arg or "20")))
            rows = self.store.fetchall("""SELECT g.number,MAX(s.aggregate_score) best,AVG(s.aggregate_score)::numeric(5,2) average,MIN(s.aggregate_score) worst
                FROM generations g JOIN idea_scores s ON s.generation_id=g.id WHERE g.status='completed' GROUP BY g.number ORDER BY g.number DESC LIMIT %s""", (limit,))
            return "\n".join(f"G{r['number']} {r['best']} / {r['average']} / {r['worst']}" for r in reversed(rows)) or "No history."
        if command == "/idea": return self._idea(int(arg))
        if command == "/lineage": return self._lineage(int(arg))
        if command in {"/report", "/reports"}:
            if command == "/reports":
                rows = self.store.fetchall("SELECT title,created_at FROM reports ORDER BY id DESC LIMIT %s", (min(50,int(arg or "10")),))
                return "\n".join(f"{r['title']} — {r['created_at']}" for r in rows) or "No reports."
            number = int(arg.upper().removeprefix("G")) if arg else None
            sql = "SELECT body_text FROM reports WHERE report_type='generation'" + (" AND generation_id=(SELECT id FROM generations WHERE number=%s)" if number else "") + " ORDER BY id DESC LIMIT 1"
            row = self.store.fetchone(sql, (number,) if number else ()); return row["body_text"] if row else "No report."
        if command == "/idea_add":
            if not arg: raise ValueError("idea text is required")
            submission = self.store.execute("INSERT INTO idea_submissions(mission_id,raw_text) VALUES (%s,%s) RETURNING id", (mission["id"],arg))
            return f"Owner idea queued as submission #{submission}."
        if command == "/idea_queue":
            rows = self.store.fetchall("SELECT id,status,raw_text FROM idea_submissions WHERE status IN ('pending','scheduled') ORDER BY id")
            return "\n".join(f"#{r['id']} [{r['status']}] {r['raw_text']}" for r in rows) or "Queue empty."
        if command == "/idea_cancel":
            changed = self.store.execute("UPDATE idea_submissions SET status='cancelled',updated_at=NOW() WHERE id=%s AND status='pending' RETURNING id", (int(arg),))
            return "Cancelled." if changed else "Submission is not pending."
        if command in {"/guidance", "/feedback", "/keep", "/reject"}:
            idea_id = None; content = arg
            if command != "/guidance":
                first, _, content = arg.partition(" "); idea_id = int(first)
                if command == "/keep": content = content or "Owner marked this idea to keep."
                if command == "/reject": content = content or "Owner rejected this idea."
            if not content: raise ValueError("text is required")
            row_id = self.store.execute("INSERT INTO guidance(mission_id,idea_id,text) VALUES (%s,%s,%s) RETURNING id", (mission["id"],idea_id,content))
            return f"Guidance #{row_id} saved for future generations."
        if command == "/guidance_list":
            rows = self.store.fetchall("SELECT id,idea_id,text FROM guidance WHERE active ORDER BY id")
            return "\n".join(f"#{r['id']} idea={r['idea_id'] or '-'} {r['text']}" for r in rows) or "No active guidance."
        if command == "/guidance_clear": self.store.execute("UPDATE guidance SET active=FALSE WHERE id=%s RETURNING id",(int(arg),)); return "Guidance cleared."
        if command == "/contexts":
            rows=self.store.fetchall("SELECT code,name,version,active FROM contexts ORDER BY sort_order")
            return "\n".join(f"{r['code']} v{r['version']} {'ON' if r['active'] else 'OFF'} — {r['name']}" for r in rows)
        if command.startswith("/context"):
            return self._context_command(command,arg)
        if command in {"/executions", "/errors"}:
            limit=min(50,int(arg or "10")); where="WHERE status='failed'" if command=="/errors" else ""
            rows=self.store.fetchall(f"SELECT id,phase,status,attempt,error_text,started_at FROM executions {where} ORDER BY id DESC LIMIT %s",(limit,))
            return "\n".join(str(r) for r in rows) or "None."
        if command == "/cost":
            row=self.store.fetchone("SELECT COUNT(*) calls,COALESCE(SUM(input_tokens),0) input,COALESCE(SUM(output_tokens),0) output FROM executions")
            return f"Calls: {row['calls']}; input tokens: {row['input']}; output tokens: {row['output']}"
        raise ValueError("unsupported command; use /help")

    def _context_command(self, command: str, arg: str) -> str:
        code, _, value = arg.partition(" "); code=code.upper()
        row=self.store.fetchone("SELECT * FROM contexts WHERE code=%s",(code,))
        if not row: raise ValueError("unknown context")
        if command == "/context": return f"{code} v{row['version']} {row['name']}\n\n{row['prompt_text']}"
        if command == "/context_history":
            rows=self.store.fetchall("SELECT version,name,changed_by,change_note,created_at FROM context_revisions WHERE context_id=%s ORDER BY version",(row['id'],))
            return "\n".join(f"v{r['version']} {r['name']} — {r['changed_by']} {r['change_note'] or ''}" for r in rows)
        if command in {"/context_enable","/context_disable"}:
            self.store.execute("UPDATE contexts SET active=%s,updated_at=NOW() WHERE id=%s RETURNING id",(command.endswith("enable"),row['id'])); return f"{code} updated. A run still requires 10 active contexts."
        if command == "/context_restore":
            revision=self.store.fetchone("SELECT name,prompt_text FROM context_revisions WHERE context_id=%s AND version=%s",(row['id'],int(value)))
            if not revision: raise ValueError("unknown version")
            return self._revise(row,revision['name'],revision['prompt_text'],f"restored from v{value}")
        if command == "/context_set" and value: return self._revise(row,row['name'],value,"prompt edited")
        if command == "/context_name" and value: return self._revise(row,value,row['prompt_text'],"name edited")
        raise ValueError("invalid context command")

    def _revise(self,row:dict[str,Any],name:str,prompt:str,note:str)->str:
        version=row['version']+1
        with self.store.transaction() as connection:
            connection.execute("UPDATE contexts SET name=%s,prompt_text=%s,version=%s,updated_at=NOW() WHERE id=%s",(name,prompt,version,row['id']))
            connection.execute("INSERT INTO context_revisions(context_id,version,name,prompt_text,changed_by,change_note) VALUES (%s,%s,%s,%s,'owner',%s)",(row['id'],version,name,prompt,note))
        return f"{row['code']} saved as v{version}; future calls only."

    def _ranking(self,number:int)->list[dict[str,Any]]:
        return self.store.fetchall("""SELECT i.id idea_id,i.title,i.mode,s.aggregate_score FROM ideas i JOIN generations g ON g.id=i.generation_id JOIN idea_scores s ON s.idea_id=i.id
            WHERE g.number=%s AND g.status='completed' ORDER BY s.aggregate_score DESC,i.id""",(number,))
    def _idea(self,idea_id:int)->str:
        row=self.store.fetchone("""SELECT i.*,g.number,s.aggregate_score FROM ideas i JOIN generations g ON g.id=i.generation_id LEFT JOIN idea_scores s ON s.idea_id=i.id WHERE i.id=%s""",(idea_id,))
        if not row:return "Idea not found."
        evaluations=self.store.fetchall("SELECT score,strengths,critique,fatal_flaw FROM idea_evaluations WHERE idea_id=%s ORDER BY score",(idea_id,))
        scores=[float(r['score']) for r in evaluations]
        return f"#{idea_id} G{row['number']} {row['title']}\n{row['one_liner']}\nMode: {row['mode']}; score: {row['aggregate_score']}; range: {min(scores) if scores else '-'}..{max(scores) if scores else '-'}\nParents: {row['parent_ids']}\n{json.dumps(row['details'],ensure_ascii=False,default=str)}"
    def _lineage(self,idea_id:int)->str:
        lines=[];seen=set()
        def visit(current:int,depth:int)->None:
            if current in seen:return
            seen.add(current); row=self.store.fetchone("SELECT id,title,parent_ids FROM ideas WHERE id=%s",(current,))
            if not row:return
            lines.append(f"{'  '*depth}#{row['id']} {row['title']}")
            for parent in row['parent_ids']:visit(parent,depth+1)
        visit(idea_id,0);return "\n".join(lines) or "Idea not found."
    def _event(self,chat_id:int,direction:str,event_type:str,text:str)->None:
        self.store.execute("INSERT INTO telegram_events(chat_id,direction,event_type,text) VALUES (%s,%s,%s,%s) RETURNING id",(chat_id,direction,event_type,text[:10000]))
    @staticmethod
    def _freeform(text:str)->str:
        lower=text.lower()
        if text.startswith("/"):return text
        if "рейтинг" in lower:return "/ranking"
        if "всю историю" in lower or "всю історію" in lower:return "/history 100"
        if "что сейчас" in lower or "виконується" in lower:return "/status"
        match=re.match(r"(?:добавь мою идею|додай мою ідею):\s*(.+)",text,re.I)
        if match:return "/idea_add "+match.group(1)
        match=re.match(r"(?:покажи контекст|покажи контекст)\s+(C\d{2})",text,re.I)
        if match:return "/context "+match.group(1).upper()
        match=re.match(r"(?:измени контекст|измени|зміни контекст|зміни)\s+(C\d{2}):\s*(.+)",text,re.I)
        if match:return f"/context_set {match.group(1).upper()} {match.group(2)}"
        if "остановись после текущего поколения" in lower or "зупинись після поточного покоління" in lower:return "/stop"
        return text


class TelegramPoller:
    def __init__(self,token:str,controller:TelegramController,store:PostgresStore,timeout:int=30)->None:
        self.base=f"https://api.telegram.org/bot{token}";self.controller=controller;self.store=store;self.timeout=timeout
    def _api(self,method:str,values:dict[str,Any])->Any:
        request=urllib.request.Request(f"{self.base}/{method}",data=urllib.parse.urlencode(values).encode())
        with urllib.request.urlopen(request,timeout=self.timeout+10) as response:payload=json.loads(response.read())
        if not payload.get("ok"):raise RuntimeError("Telegram API rejected request")
        return payload["result"]
    def run_forever(self)->None:
        while True:
            offset=self.store.fetchone("SELECT update_id FROM telegram_offsets WHERE bot_key='primary'")
            updates=self._api("getUpdates",{"offset":(offset['update_id']+1 if offset else 0),"timeout":self.timeout,"allowed_updates":json.dumps(["message"])})
            for update in updates:
                message=update.get("message",{});chat=message.get("chat",{});text=message.get("text")
                if text:self._api("sendMessage",{"chat_id":chat["id"],"text":self.controller.handle(int(chat["id"]),text)[:4096]})
                self.store.execute("INSERT INTO telegram_offsets(bot_key,update_id) VALUES ('primary',%s) ON CONFLICT(bot_key) DO UPDATE SET update_id=EXCLUDED.update_id,updated_at=NOW() RETURNING update_id",(update["update_id"],))
            if not updates:time.sleep(.1)
