import logging
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg

from common.database import database_url
from common.events import append_event
from common.repositories import Repository, RepositoryRegistry
from common.secrets import EnvironmentSecretStore
from common.telegram import send_telegram

logger = logging.getLogger("ptw.git-watcher")
logging.basicConfig(level=os.getenv("PTW_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
running = True
secrets = EnvironmentSecretStore()


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    author: str
    timestamp: str


def stop(_signum: int, _frame: object) -> None:
    global running
    running = False


def git(*args: str, cwd: str | None = None) -> str:
    environment = os.environ.copy()
    environment.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": "ssh -F /etc/ptw-git/ssh_config",
    })
    result = subprocess.run(["git", *args], cwd=cwd, env=environment, text=True,
                            capture_output=True, timeout=90, check=True)
    return result.stdout


def remote_sha(repository: Repository, branch: str) -> str:
    output = git("ls-remote", "--heads", repository.clone_url, f"refs/heads/{branch}").strip()
    if not output:
        raise RuntimeError(f"Remote branch not found: {repository.id}/{branch}")
    sha, ref = output.split()
    if ref != f"refs/heads/{branch}" or len(sha) != 40:
        raise RuntimeError("Unexpected ls-remote response")
    return sha


def commit_metadata(repository: Repository, previous: str, current: str) -> tuple[list[Commit], int | None]:
    with tempfile.TemporaryDirectory(prefix="ptw-watch-") as directory:
        git("init", "--quiet", cwd=directory)
        git("remote", "add", "origin", repository.clone_url, cwd=directory)
        git("fetch", "--quiet", "--no-tags", "origin", current, cwd=directory)
        try:
            git("fetch", "--quiet", "--no-tags", "origin", previous, cwd=directory)
            raw = git("log", "--format=%H%x1f%s%x1f%an%x1f%aI%x1e", f"{previous}..{current}", cwd=directory)
        except subprocess.CalledProcessError:
            raw = git("log", "-1", "--format=%H%x1f%s%x1f%an%x1f%aI%x1e", current, cwd=directory)
        commits = []
        for record in raw.strip("\x1e\n").split("\x1e") if raw else []:
            fields = record.strip().split("\x1f")
            if len(fields) == 4:
                commits.append(Commit(*fields))
        try:
            changed_files = int(git("diff", "--name-only", previous, current, cwd=directory).count("\n"))
        except subprocess.CalledProcessError:
            changed_files = None
        return commits, changed_files


def format_notification(repository: Repository, branch: str, previous: str, current: str,
                        commits: list[Commit], changed_files: int | None, maximum: int = 5) -> str:
    detected = datetime.now(timezone.utc).strftime("%H:%M UTC")
    if len(commits) == 1:
        commit = commits[0]
        lines = [f"🚀 {repository.id.upper()} {branch} updated",
                 f"{commit.sha[:7]} — {commit.subject}", f"Author: {commit.author}"]
        if changed_files is not None:
            lines.append(f"Files changed: {changed_files}")
        return "\n".join(lines)
    lines = [f"🚀 {repository.id.upper()} {branch} updated", f"Repository: {repository.id}",
             f"Branch: {branch}", f"Before: {previous[:7]}", f"Now: {current[:7]}",
             f"{len(commits)} new commits:"]
    lines.extend(f"• {commit.sha[:7]} {commit.subject}" for commit in commits[:maximum])
    if len(commits) > maximum:
        lines.append(f"+ {len(commits) - maximum} more commits")
    if commits:
        lines.append(f"Latest author: {commits[0].author}")
    lines.extend((f"Detected: {detected}", "No action required."))
    return "\n".join(lines)


def observe(connection: psycopg.Connection, repository_id: str = "ptw", branch: str = "main") -> str:
    repository = RepositoryRegistry(connection).get(repository_id)
    current = remote_sha(repository, branch)
    row = connection.execute(
        "SELECT last_sha FROM watched_branches WHERE repository_id=%s AND branch=%s FOR UPDATE",
        (repository.id, branch),
    ).fetchone()
    if row is None or row[0] is None:
        connection.execute(
            """INSERT INTO watched_branches(repository_id, branch, last_sha)
               VALUES (%s,%s,%s) ON CONFLICT(repository_id,branch)
               DO UPDATE SET last_sha=excluded.last_sha, detected_at=now()""",
            (repository.id, branch, current),
        )
        logger.info("Initialized %s/%s at %s", repository.id, branch, current[:7])
        return "initialized"
    previous = row[0]
    if previous == current:
        logger.debug("Branch unchanged: %s/%s", repository.id, branch)
        return "unchanged"
    commits, changed_files = commit_metadata(repository, previous, current)
    maximum = max(1, int(os.getenv("GIT_MAIN_WATCH_MAX_COMMITS", "5")))
    message = format_notification(repository, branch, previous, current, commits, changed_files, maximum)
    recipients = sorted(int(value.strip()) for value in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if value.strip())
    for recipient in recipients:
        connection.execute(
            """INSERT INTO git_notifications(repository_id,branch,previous_sha,current_sha,recipient_id,message)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (repository.id, branch, previous, current, recipient, message),
        )
    connection.execute("UPDATE watched_branches SET last_sha=%s, detected_at=now() WHERE repository_id=%s AND branch=%s",
                       (current, repository.id, branch))
    append_event(connection, "GIT_BRANCH_UPDATED", "git-watcher", status="detected",
                 payload={"repository": repository.id, "branch": branch, "previous_sha": previous,
                          "new_sha": current, "commit_count": len(commits)})
    return "updated"


def deliver_one(connection: psycopg.Connection) -> bool:
    row = connection.execute(
        """SELECT id,recipient_id,message,repository_id,branch,current_sha,attempts
           FROM git_notifications WHERE status='pending' AND next_attempt_at <= now()
           ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1"""
    ).fetchone()
    if not row:
        return False
    notification_id, recipient, message, repository, branch, sha, attempts = row
    try:
        send_telegram(recipient, message)
        connection.execute("UPDATE git_notifications SET status='sent',attempts=attempts+1,sent_at=now() WHERE id=%s", (notification_id,))
        append_event(connection, "GIT_NOTIFICATION_SENT", "git-watcher", status="sent",
                     payload={"repository": repository, "branch": branch, "new_sha": sha, "recipient_id": recipient})
    except Exception as exc:
        attempts += 1
        terminal = attempts >= 5
        connection.execute(
            """UPDATE git_notifications SET status=%s,attempts=%s,last_error_type=%s,
               next_attempt_at=now() + make_interval(secs => %s) WHERE id=%s""",
            ("failed" if terminal else "pending", attempts, type(exc).__name__, min(3600, 30 * 2 ** (attempts - 1)), notification_id),
        )
        append_event(connection, "GIT_NOTIFICATION_FAILED", "git-watcher", status="failed" if terminal else "retrying",
                     payload={"repository": repository, "branch": branch, "new_sha": sha,
                              "recipient_id": recipient, "attempt": attempts, "error_type": type(exc).__name__})
        logger.warning("Telegram notification %s failed (%s/5): %s", notification_id, attempts, type(exc).__name__)
    return True


def main() -> None:
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    interval = max(60, int(os.getenv("GIT_MAIN_WATCH_INTERVAL_SECONDS", "300")))
    next_check = 0.0
    while running:
        try:
            with psycopg.connect(database_url(secrets), connect_timeout=3) as connection:
                if time.monotonic() >= next_check:
                    observe(connection)
                    connection.commit()  # durable state/outbox precede external delivery
                    next_check = time.monotonic() + interval
                while deliver_one(connection):
                    connection.commit()
        except Exception as exc:
            logger.warning("Watcher cycle failed: %s", type(exc).__name__)
        time.sleep(2)


if __name__ == "__main__":
    main()
