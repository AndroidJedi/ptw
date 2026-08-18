from __future__ import annotations

from contextlib import contextmanager
import unittest

from owner_gateway.read_models import DomainReadModels


class _EmptyConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, query: str, params: tuple[object, ...]) -> "_EmptyConnection":
        self.calls.append((query, params))
        return self

    def fetchall(self) -> list[object]:
        return []


class ReadModelTests(unittest.TestCase):
    def test_post_review_filter_does_not_send_untyped_nullable_parameters(self) -> None:
        for review_status, expected_clause in (
            (None, ""),
            ("pending", "AND review.feedback_id IS NULL"),
            ("reviewed", "AND review.feedback_id IS NOT NULL"),
        ):
            connection = _EmptyConnection()
            read = DomainReadModels("postgres://idea", "postgres://commander")

            @contextmanager
            def connect(_url: str):
                yield connection

            read._connect = connect  # type: ignore[method-assign]
            self.assertEqual(read.posts(limit=20, review_status=review_status), {"items": [], "next_cursor": None})
            singles_query, singles_params = connection.calls[1]
            self.assertEqual(singles_params, (20,))
            self.assertNotIn("%s IS NULL", singles_query)
            if expected_clause:
                self.assertIn(expected_clause, singles_query)


if __name__ == "__main__":
    unittest.main()
