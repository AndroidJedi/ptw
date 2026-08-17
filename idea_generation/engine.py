from __future__ import annotations

import hashlib
from typing import Any, Callable

from .provider import StructuredProvider
from .recovery import RecoveryExhausted, recover
from .reporting import generation_report
from .store import PostgresStore
from .validation import evaluations as validate_evaluations
from .validation import idea as validate_idea


def _english(value: dict[str, Any]) -> str:
    return str(value["en"])


class EvolutionEngine:
    def __init__(self, store: PostgresStore, provider: StructuredProvider,
                 notify: Callable[[str], None] | None = None) -> None:
        self.store, self.provider = store, provider
        self.notify = notify or (lambda _message: None)
        self.recovery_count = 0

    def queue_generations(self, count: int = 1) -> tuple[int, bool]:
        """Persist work before returning to Telegram.

        ``run_series_remaining`` includes the generation currently running.  A
        new ``/run`` received during an active series therefore adds to the
        remaining count instead of being silently discarded.
        """
        if count < 1:
            raise ValueError("run count must be positive")
        with self.store.transaction() as connection:
            mission = connection.execute(
                "SELECT id,status,run_series_remaining FROM missions "
                "WHERE is_active=TRUE FOR UPDATE"
            ).fetchone()
            if not mission:
                raise RuntimeError("mission is not seeded")
            if mission[1] != "active":
                raise RuntimeError("mission is paused")
            in_progress = bool(connection.execute(
                "SELECT 1 FROM generations "
                "WHERE status IN ('creating','created','evaluating') LIMIT 1"
            ).fetchone())
            already_active = mission[2] > 0 or in_progress
            remaining = mission[2] + count if already_active else count
            connection.execute(
                "UPDATE missions SET run_series_remaining=%s,"
                "stop_after_current_cycle=FALSE,updated_at=NOW() WHERE id=%s",
                (remaining, mission[0]),
            )
        return remaining, already_active

    def run_series(self, count: int = 1) -> list[int]:
        if count < 1: raise ValueError("run count must be positive")
        mission = self.store.mission()
        if mission["status"] != "active": raise RuntimeError("mission is paused")
        if mission["run_series_remaining"] or self._in_progress():
            raise RuntimeError("a run series is already active")
        start_best = self.store.fetchone("SELECT MAX(s.aggregate_score) best FROM idea_scores s JOIN generations g ON g.id=s.generation_id WHERE g.status='completed'")
        self.store.update_mission(run_series_remaining=count, stop_after_current_cycle=False)
        completed = self.continue_series()
        if count > 1:
            self._series_report(count, completed, start_best["best"] if start_best else None)
        return completed

    def continue_series(self) -> list[int]:
        completed: list[int] = []
        while True:
            mission = self.store.mission()
            if mission["status"] != "active" or mission["run_series_remaining"] <= 0: break
            if mission["stop_after_current_cycle"] and not self._in_progress(): break
            try:
                number = self.run_generation()
            except RecoveryExhausted:
                break
            completed.append(number)
            current = self.store.mission()
            remaining = max(0, current["run_series_remaining"] - 1)
            self.store.update_mission(run_series_remaining=remaining)
            if current["stop_after_current_cycle"]: break
        return completed

    def run_generation(self) -> int:
        import psycopg
        mission_code = str(self.store.mission()["code"])
        with psycopg.connect(self.store.database_url, autocommit=True) as lock_connection:
            locked = lock_connection.execute(
                "SELECT pg_try_advisory_lock(hashtext(%s))", (mission_code,)
            ).fetchone()[0]
            if not locked: raise RuntimeError("mission cycle is already locked")
            try:
                return self._run_generation_locked()
            finally:
                lock_connection.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s))", (mission_code,)
                )

    def _run_generation_locked(self) -> int:
        contexts = self.store.active_contexts()
        if len(contexts) != 10: raise RuntimeError("exactly 10 active contexts are required")
        with self.store.transaction() as connection:
            mission = connection.execute(
                "SELECT * FROM missions WHERE is_active=TRUE FOR UPDATE"
            ).fetchone()
            if not mission:
                raise RuntimeError("mission is not seeded")
            mission_id = mission[0]
            existing = connection.execute("SELECT id,number,status FROM generations WHERE mission_id=%s AND status IN ('creating','created','evaluating') ORDER BY number LIMIT 1", (mission_id,)).fetchone()
            if existing:
                generation_id, number = existing[0], existing[1]
            else:
                number = connection.execute("SELECT COALESCE(MAX(number),0)+1 FROM generations WHERE mission_id=%s", (mission_id,)).fetchone()[0]
                generation_id = connection.execute("INSERT INTO generations(mission_id,number,status) VALUES (%s,%s,'creating') RETURNING id", (mission_id, number)).fetchone()[0]
        try:
            self._create_missing(mission_id, generation_id, number, contexts)
            self._evaluate_missing(mission_id, generation_id, number, contexts)
            self._complete(mission_id, generation_id, number)
            return number
        except RecoveryExhausted as error:
            self.store.execute("UPDATE generations SET status='failed',error_text=%s WHERE id=%s RETURNING id", (str(error), generation_id))
            self.store.update_mission(stop_after_current_cycle=True)
            raise

    def _create_missing(self, mission_id: int, generation_id: int, number: int, contexts: list[dict[str, Any]]) -> None:
        current = self.store.fetchall("SELECT * FROM ideas WHERE generation_id=%s ORDER BY id", (generation_id,))
        submissions = self._reserve_submissions(mission_id, generation_id, number, current)
        if submissions and number > 1:
            self._retain_latest_survivors(mission_id, generation_id, number, submissions)
            current = self.store.fetchall("SELECT * FROM ideas WHERE generation_id=%s ORDER BY id", (generation_id,))
        used_submission_ids = {row["owner_submission_id"] for row in current if row["owner_submission_id"]}
        for submission in submissions:
            if submission["id"] in used_submission_ids: continue
            payload = {
                "task": self.store.mission()["task_text"],
                "context": {"code": "owner", "name": "Owner submission"},
                "raw_text": submission["raw_text"],
                "instruction": "Normalize formatting without changing the business concept.",
            }
            def operation(attempt: int) -> dict[str, Any]:
                execution_id = self._execution(
                    mission_id, generation_id, "normalize_human", None, attempt, payload, "running"
                )
                try:
                    result = self.provider.generate_structured(
                        "normalize_human", "Preserve the owner's concept and return valid JSON only.", payload, {}
                    )
                    validated = validate_idea(result, set(), False)
                    self._finish_execution(execution_id, "succeeded", result)
                    return validated
                except Exception as error:
                    self._finish_execution(execution_id, "failed", error_text=type(error).__name__)
                    raise
            normalized = self._recover(f"G{number} / NORMALIZE_HUMAN / owner", operation)
            idea_id = self.store.execute("""INSERT INTO ideas(
                    mission_id,generation_id,mode,title,one_liner,title_i18n,one_liner_i18n,
                    details,owner_submission_id
                ) VALUES (%s,%s,'human',%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s) RETURNING id""",
                (mission_id, generation_id, _english(normalized["title"]),
                 _english(normalized["one_liner"]), self.store.json(normalized["title"]),
                 self.store.json(normalized["one_liner"]), self.store.json(normalized["details"]),
                 submission["id"]))
            self.store.execute(
                "UPDATE idea_submissions SET inserted_idea_id=%s,updated_at=NOW() WHERE id=%s RETURNING id",
                (idea_id, submission["id"]),
            )
            current.append({"id": idea_id, "mode": "human", "owner_submission_id": submission["id"]})
        remaining = 10 - len(current)
        if remaining < 0: raise RuntimeError("generation exceeds 10 slots")
        generated_modes = self._modes(remaining, number)
        previous = self._working_set(mission_id, number)
        guidance = self.store.fetchall("SELECT id,text,idea_id FROM guidance WHERE mission_id=%s AND active ORDER BY id", (mission_id,))
        for offset, mode in enumerate(generated_modes):
            context = contexts[(len(current) + offset + number - 1) % 10]
            provider_mode = "generate" if number == 1 else "evolve"
            payload = {"task": self.store.mission()["task_text"], "context": {"code": context["code"], "name": context["name"], "prompt": context["prompt_text"]},
                       "owner_guidance": guidance, "mode": mode, **previous}
            valid_parents = {int(row["id"]) for row in previous.get("current_generation", [])}
            def operation(attempt: int) -> dict[str, Any]:
                execution_id = self._execution(mission_id, generation_id, provider_mode, context["id"], attempt, payload, "running")
                try:
                    result = self.provider.generate_structured(provider_mode, "Return valid JSON only.", payload, {})
                    validated = validate_idea(result, valid_parents, number > 1 and mode == "exploit")
                    self._finish_execution(execution_id, "succeeded", result)
                    return validated
                except Exception as error:
                    self._finish_execution(execution_id, "failed", error_text=type(error).__name__)
                    raise
            result = self._recover(f"G{number} / {provider_mode.upper()} / {context['code']}", operation)
            self.store.execute("""INSERT INTO ideas(
                    mission_id,generation_id,creator_context_id,mode,title,one_liner,
                    title_i18n,one_liner_i18n,details,parent_ids,lineage_note
                ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s) RETURNING id""",
                (mission_id, generation_id, context["id"], mode,
                 _english(result["title"]), _english(result["one_liner"]),
                 self.store.json(result["title"]), self.store.json(result["one_liner"]),
                 self.store.json(result["details"]), result.get("parent_ids", []),
                 result.get("lineage_note")))
            current.append({"mode": mode})
        if len(current) != 10: raise RuntimeError("generation must contain exactly 10 ideas")
        self.store.execute("UPDATE generations SET status='created' WHERE id=%s RETURNING id", (generation_id,))

    def _reserve_submissions(
        self, mission_id: int, generation_id: int, number: int, current: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        scheduled = self.store.fetchall(
            "SELECT * FROM idea_submissions WHERE mission_id=%s AND status='scheduled' "
            "AND target_generation_number=%s ORDER BY id",
            (mission_id, number),
        )
        # Once candidate creation has begun, newly arriving submissions belong
        # to the next generation.  This keeps partial/restart reconciliation
        # deterministic.
        if not current:
            slots = max(0, 10 - len(scheduled))
            pending = self.store.fetchall(
                "SELECT * FROM idea_submissions WHERE mission_id=%s AND status='pending' "
                "ORDER BY created_at,id LIMIT %s",
                (mission_id, slots),
            )
            for submission in pending:
                self.store.execute(
                    "UPDATE idea_submissions SET status='scheduled',target_generation_number=%s,"
                    "updated_at=NOW() WHERE id=%s AND status='pending' RETURNING id",
                    (number, submission["id"]),
                )
            scheduled.extend(pending)
        if not scheduled or number == 1:
            return scheduled

        lowest = self.store.fetchall(
            """SELECT i.id FROM ideas i
               JOIN generations g ON g.id=i.generation_id
               JOIN idea_scores s ON s.idea_id=i.id
               WHERE i.mission_id=%s AND g.status='completed' AND g.number<%s
               AND g.number=(SELECT MAX(number) FROM generations
                             WHERE mission_id=%s AND status='completed' AND number<%s)
               ORDER BY s.aggregate_score ASC,i.id ASC LIMIT %s""",
            (mission_id, number, mission_id, number, len(scheduled)),
        )
        if len(lowest) != len(scheduled):
            raise RuntimeError("latest completed generation is not a full replacement source")
        for submission, dropped in zip(scheduled, lowest):
            if submission.get("replaces_idea_id") is None:
                self.store.execute(
                    "UPDATE idea_submissions SET replaces_idea_id=%s,updated_at=NOW() "
                    "WHERE id=%s RETURNING id",
                    (dropped["id"], submission["id"]),
                )
                submission["replaces_idea_id"] = dropped["id"]
        return scheduled

    def _retain_latest_survivors(
        self, mission_id: int, generation_id: int, number: int, submissions: list[dict[str, Any]]
    ) -> None:
        dropped = {int(row["replaces_idea_id"]) for row in submissions}
        sources = self.store.fetchall(
            """SELECT i.*,g.number source_generation FROM ideas i
               JOIN generations g ON g.id=i.generation_id
               JOIN idea_scores s ON s.idea_id=i.id
               WHERE i.mission_id=%s AND g.status='completed' AND g.number<%s
               AND g.number=(SELECT MAX(number) FROM generations
                             WHERE mission_id=%s AND status='completed' AND number<%s)
               ORDER BY s.aggregate_score DESC,i.id ASC""",
            (mission_id, number, mission_id, number),
        )
        survivors = [row for row in sources if int(row["id"]) not in dropped]
        if len(survivors) != 10 - len(submissions):
            raise RuntimeError("owner replacement must retain the latest batch minus its lowest scores")
        existing = {
            int(row["parent_ids"][0])
            for row in self.store.fetchall(
                "SELECT parent_ids FROM ideas WHERE generation_id=%s AND mode='retained'",
                (generation_id,),
            )
            if row["parent_ids"]
        }
        for source in survivors:
            if int(source["id"]) in existing:
                continue
            self.store.execute(
                """INSERT INTO ideas(
                       mission_id,generation_id,creator_context_id,mode,title,one_liner,
                       title_i18n,one_liner_i18n,details,parent_ids,lineage_note
                   ) VALUES (%s,%s,%s,'retained',%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s) RETURNING id""",
                (mission_id, generation_id, source["creator_context_id"], source["title"],
                 source["one_liner"], self.store.json(source["title_i18n"]),
                 self.store.json(source["one_liner_i18n"]), self.store.json(source["details"]), [source["id"]],
                 f"Retained from G{source['source_generation']}; owner submission replaced a lower-scored candidate."),
            )

    @staticmethod
    def _modes(slots: int, number: int) -> list[str]:
        if number == 1: return ["initial"] * slots
        explore = round(slots * .3)
        modes = ["exploit"] * (slots - explore) + ["explore"] * explore
        shift = (number - 2) % max(1, slots)
        return modes[shift:] + modes[:shift]

    def _working_set(self, mission_id: int, number: int) -> dict[str, Any]:
        if number == 1: return {}
        current = self.store.fetchall("""SELECT i.id,i.title,i.one_liner,i.details,s.aggregate_score,
            (SELECT e.critique FROM idea_evaluations e WHERE e.idea_id=i.id ORDER BY ABS(e.score-s.aggregate_score),e.id LIMIT 1) median_critique,
            (SELECT e.critique FROM idea_evaluations e WHERE e.idea_id=i.id ORDER BY e.score,e.id LIMIT 1) critical_critique
            FROM ideas i JOIN generations g ON g.id=i.generation_id JOIN idea_scores s ON s.idea_id=i.id
            WHERE i.mission_id=%s AND g.number=%s ORDER BY i.id""", (mission_id, number - 1))
        hall = self.store.fetchall("""SELECT i.id,i.title,s.aggregate_score FROM ideas i JOIN generations g ON g.id=i.generation_id JOIN idea_scores s ON s.idea_id=i.id
            WHERE i.mission_id=%s AND g.status='completed' AND g.number<%s ORDER BY s.aggregate_score DESC,i.id LIMIT 3""", (mission_id, number))
        failures = sorted(current, key=lambda row: row["aggregate_score"])[:2]
        return {"current_generation": current, "hall_of_fame": hall, "failures": failures}

    def _evaluate_missing(self, mission_id: int, generation_id: int, number: int, contexts: list[dict[str, Any]]) -> None:
        self.store.execute("UPDATE generations SET status='evaluating' WHERE id=%s RETURNING id", (generation_id,))
        ideas = self.store.fetchall(
            "SELECT id,title,one_liner,title_i18n,one_liner_i18n,details,mode,parent_ids "
            "FROM ideas WHERE generation_id=%s ORDER BY id", (generation_id,)
        )
        if len(ideas) != 10: raise RuntimeError("cannot evaluate incomplete generation")
        ids = [row["id"] for row in ideas]
        existing = {row["evaluator_context_id"] for row in self.store.fetchall("SELECT DISTINCT evaluator_context_id FROM idea_evaluations WHERE idea_id=ANY(%s)", (ids,))}
        for context in contexts:
            if context["id"] in existing: continue
            payload = {"task": self.store.mission()["task_text"], "context": {"code": context["code"], "name": context["name"], "prompt": context["prompt_text"]}, "ideas": ideas}
            def operation(attempt: int) -> list[dict[str, Any]]:
                execution_id = self._execution(mission_id, generation_id, "evaluate", context["id"], attempt, payload, "running")
                try:
                    result = self.provider.generate_structured("evaluate", "Apply the fixed 100-point rubric.", payload, {})
                    validated = validate_evaluations(result, ids)
                    self._finish_execution(execution_id, "succeeded", result)
                    return validated
                except Exception as error:
                    self._finish_execution(execution_id, "failed", error_text=type(error).__name__)
                    raise
            rows = self._recover(f"G{number} / EVALUATE / {context['code']}", operation)
            with self.store.transaction() as connection:
                for row in rows:
                    connection.execute("""INSERT INTO idea_evaluations(idea_id,evaluator_context_id,score,criteria,strengths,critique,fatal_flaw)
                        VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s) ON CONFLICT (idea_id,evaluator_context_id) DO NOTHING""",
                        (row["idea_id"], context["id"], row["score"], self.store.json(row["criteria"]), row["strengths"], row["critique"], row.get("fatal_flaw")))

    def _complete(self, mission_id: int, generation_id: int, number: int) -> None:
        count = self.store.fetchone("SELECT COUNT(*) AS count FROM idea_evaluations e JOIN ideas i ON i.id=e.idea_id WHERE i.generation_id=%s", (generation_id,))["count"]
        if count != 100: raise RuntimeError("completed generation requires 100 evaluations")
        ranking = self.store.fetchall("""SELECT i.id AS idea_id,i.title,i.mode,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id
            WHERE i.generation_id=%s ORDER BY s.aggregate_score DESC,i.id""", (generation_id,))
        previous = self.store.fetchone("""SELECT MAX(s.aggregate_score) AS best FROM idea_scores s JOIN generations g ON g.id=s.generation_id
            WHERE g.mission_id=%s AND g.status='completed'""", (mission_id,))
        historical = self.store.fetchone("""SELECT i.id,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id JOIN generations g ON g.id=i.generation_id
            WHERE i.mission_id=%s AND g.status='completed' ORDER BY s.aggregate_score DESC LIMIT 1""", (mission_id,))
        owner_count = sum(1 for row in ranking if row["mode"] == "human")
        calls = self.store.fetchone("SELECT COUNT(*) AS count,COALESCE(SUM(input_tokens+output_tokens),0) AS tokens FROM executions WHERE generation_id=%s", (generation_id,))
        body, payload = generation_report(number, ranking, float(previous["best"]) if previous and previous["best"] else None,
                                           historical, owner_count, self.recovery_count, calls["count"], calls["tokens"])
        failures = self.store.fetchall("""SELECT i.id,i.title,s.aggregate_score,
            (SELECT e.critique FROM idea_evaluations e WHERE e.idea_id=i.id ORDER BY e.score,e.id LIMIT 1) reason
            FROM ideas i JOIN idea_scores s ON s.idea_id=i.id WHERE i.generation_id=%s ORDER BY s.aggregate_score,i.id LIMIT 2""", (generation_id,))
        disagreement = self.store.fetchall("""SELECT i.id,MAX(e.score)-MIN(e.score) spread FROM ideas i JOIN idea_evaluations e ON e.idea_id=i.id
            WHERE i.generation_id=%s GROUP BY i.id ORDER BY spread DESC,i.id LIMIT 3""", (generation_id,))
        guidance = self.store.fetchall("SELECT id,idea_id,text FROM guidance WHERE mission_id=%s AND active ORDER BY id", (mission_id,))
        top_lineage = self.store.fetchone("SELECT parent_ids,lineage_note FROM ideas WHERE id=%s", (ranking[0]["idea_id"],))
        recoveries = self.store.fetchall("SELECT id,phase,context_id,attempt,error_text FROM executions WHERE generation_id=%s AND status='failed' ORDER BY id", (generation_id,))
        replacements = self.store.fetchall(
            "SELECT id submission_id,inserted_idea_id,replaces_idea_id FROM idea_submissions "
            "WHERE mission_id=%s AND target_generation_number=%s ORDER BY id",
            (mission_id, number),
        )
        payload.update({"failures": failures, "evaluator_disagreement": disagreement, "active_guidance": guidance,
                        "top_lineage": top_lineage, "recovery_incidents": recoveries,
                        "owner_replacements": replacements})
        body += ("\n\nFailures:\n" + "\n".join(f"#{row['id']} {row['aggregate_score']} — {row['reason']}" for row in failures)
                 + "\n\nEvaluator disagreement:\n" + "\n".join(f"#{row['id']} spread {row['spread']}" for row in disagreement)
                 + f"\n\nOwner replacements: {replacements}"
                 + f"\nActive guidance: {len(guidance)}; recovery incidents: {len(recoveries)}; top lineage: {top_lineage}")
        with self.store.transaction() as connection:
            connection.execute("UPDATE generations SET status='completed',completed_at=NOW(),error_text=NULL WHERE id=%s", (generation_id,))
            connection.execute("UPDATE idea_submissions SET status='inserted',updated_at=NOW() WHERE target_generation_number=%s AND mission_id=%s AND status='scheduled'", (number, mission_id))
            connection.execute("INSERT INTO reports(mission_id,generation_id,report_type,title,body_text,payload) VALUES (%s,%s,'generation',%s,%s,%s::jsonb)",
                               (mission_id, generation_id, f"G{number} report", body, self.store.json(payload)))
        self.notify(f"✅ G{number} complete\n\nBest: #{ranking[0]['idea_id']} — {ranking[0]['aggregate_score']}\n/report G{number}")

    def _series_report(self, requested: int, completed: list[int], start_best: Any) -> None:
        mission = self.store.mission()
        end = self.store.fetchone("""SELECT i.id,i.title,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id
            JOIN generations g ON g.id=i.generation_id WHERE g.status='completed' ORDER BY s.aggregate_score DESC,i.id LIMIT 1""")
        reason = "completed" if len(completed) == requested else ("owner stop" if mission["stop_after_current_cycle"] else "recovery failure or pause")
        payload = {"requested_generations": requested, "completed_generations": completed, "ended_because": reason,
                   "start_best_score": start_best, "end_best_score": end["aggregate_score"] if end else None, "best_discovered_idea": end}
        body = (f"Run series: requested {requested}; completed {len(completed)}; reason: {reason}.\n"
                f"Start best: {start_best}; end best: {payload['end_best_score']}; best: {end}.")
        self.store.execute("INSERT INTO reports(mission_id,report_type,title,body_text,payload) VALUES (%s,'run_series',%s,%s,%s::jsonb) RETURNING id",
                           (mission["id"], "Run series report", body, self.store.json(payload)))

    def _execution(self, mission_id: int, generation_id: int, phase: str, context_id: int | None, attempt: int,
                   payload: dict[str, Any], status: str) -> int:
        digest = hashlib.sha256(self.store.json(payload).encode()).hexdigest()
        result = self.store.execute("""INSERT INTO executions(mission_id,generation_id,phase,status,context_id,attempt,model_name,prompt_hash,request_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING id""", (mission_id, generation_id, phase, status,
            context_id, attempt, getattr(self.provider, "model_name", None), digest, self.store.json(payload)))
        assert result is not None
        return result

    def _finish_execution(self, execution_id: int, status: str, response: Any = None, error_text: str | None = None) -> None:
        self.store.execute("UPDATE executions SET status=%s,response_json=%s::jsonb,error_text=%s,completed_at=NOW() WHERE id=%s RETURNING id",
                           (status, self.store.json(response) if response is not None else None, error_text, execution_id))

    def _recover(self, step: str, operation: Callable[[int], Any]) -> Any:
        before = len(getattr(self.provider, "calls", []))
        result = recover(step, operation, self.notify)
        attempts = len(getattr(self.provider, "calls", [])) - before
        self.recovery_count += max(0, attempts - 1)
        return result

    def _in_progress(self) -> bool:
        row = self.store.fetchone("SELECT 1 AS yes FROM generations WHERE status IN ('creating','created','evaluating') LIMIT 1")
        return bool(row)
