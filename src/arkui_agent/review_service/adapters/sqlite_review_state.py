from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from ..domain import FastMvpReviewIdentity
from ..domain._validation import non_empty_string
from ..ports import ResultStoreError


class SqliteReviewState:
    """Durable completed-only dedup state for one local poller process."""

    def __init__(self, path: Path) -> None:
        self._path = path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute(
                    """CREATE TABLE IF NOT EXISTS completed_reviews (
                        repository TEXT NOT NULL,
                        pr_id TEXT NOT NULL,
                        base_sha TEXT NOT NULL,
                        head_sha TEXT NOT NULL,
                        review_policy_version TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status = 'completed'),
                        published_comment_id TEXT NOT NULL,
                        reviewed_at TEXT NOT NULL,
                        PRIMARY KEY (
                            repository, pr_id, base_sha, head_sha,
                            review_policy_version
                        )
                    )"""
                )
        except (OSError, sqlite3.Error) as error:
            raise ResultStoreError(
                f"review state initialization failed: {type(error).__name__}"
            ) from None

    def has_completed(self, identity: FastMvpReviewIdentity) -> bool:
        try:
            with closing(sqlite3.connect(self._path)) as db:
                row = db.execute(
                    """SELECT 1 FROM completed_reviews WHERE repository = ?
                    AND pr_id = ? AND base_sha = ? AND head_sha = ?
                    AND review_policy_version = ?""",
                    _key(identity),
                ).fetchone()
        except sqlite3.Error as error:
            raise ResultStoreError(
                f"review state lookup failed: {type(error).__name__}"
            ) from None
        return row is not None

    def record_completed(
        self, identity: FastMvpReviewIdentity, comment_id: str
    ) -> None:
        normalized_comment = non_empty_string(comment_id, field="comment_id")
        try:
            with closing(sqlite3.connect(self._path)) as db, db:
                db.execute(
                    """INSERT INTO completed_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        *_key(identity),
                        "completed",
                        normalized_comment,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except sqlite3.Error as error:
            raise ResultStoreError(
                f"review state persistence failed after publish: {type(error).__name__}"
            ) from None


def _key(identity: FastMvpReviewIdentity) -> tuple[str, str, str, str, str]:
    return (
        identity.repository,
        identity.pr_id,
        identity.base_sha,
        identity.head_sha,
        identity.review_policy_version,
    )
