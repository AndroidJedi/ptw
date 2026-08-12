from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Repository:
    id: str
    name: str
    clone_url: str
    default_branch: str
    enabled: bool
    project_type: str | None
    metadata: dict[str, Any]


class RepositoryRegistry:
    """PostgreSQL-backed allowlist. Callers accept IDs, never arbitrary URLs."""

    def __init__(self, connection: Any):
        self.connection = connection

    def get(self, repository_id: str) -> Repository:
        row = self.connection.execute(
            """SELECT id, name, clone_url, default_branch, enabled, project_type, metadata
               FROM repositories WHERE id = %s AND enabled""",
            (repository_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Repository is not enabled: {repository_id}")
        return Repository(*row)

