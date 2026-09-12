from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ._validation import (
    canonical_json,
    load_json_object,
    non_empty_string,
    strict_mapping,
    tuple_of_strings,
)
from .identity import ReviewIdentity
from .location import SourceRange


@dataclass(frozen=True, slots=True)
class ChangeRef:
    file: str
    old_range: SourceRange | None = None
    new_range: SourceRange | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "file", non_empty_string(self.file, field="file"))
        if self.old_range is None and self.new_range is None:
            raise ValueError("ChangeRef requires old_range, new_range, or both")
        if self.old_range is not None and not isinstance(self.old_range, SourceRange):
            raise ValueError("old_range must be SourceRange or None")
        if self.new_range is not None and not isinstance(self.new_range, SourceRange):
            raise ValueError("new_range must be SourceRange or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "old_range": None if self.old_range is None else self.old_range.to_dict(),
            "new_range": None if self.new_range is None else self.new_range.to_dict(),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ChangeRef:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset({"file", "old_range", "new_range"}),
        )
        return cls(
            file=data["file"],
            old_range=(
                None
                if data["old_range"] is None
                else SourceRange.from_dict(data["old_range"])
            ),
            new_range=(
                None
                if data["new_range"] is None
                else SourceRange.from_dict(data["new_range"])
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> ChangeRef:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    identity: ReviewIdentity
    base_sha: str
    diff: str
    changed_files: tuple[str, ...]
    changes: tuple[ChangeRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ReviewIdentity):
            raise ValueError("identity must be ReviewIdentity")
        object.__setattr__(
            self,
            "base_sha",
            non_empty_string(self.base_sha, field="base_sha"),
        )
        object.__setattr__(self, "diff", non_empty_string(self.diff, field="diff"))
        object.__setattr__(
            self,
            "changed_files",
            tuple_of_strings(
                self.changed_files,
                field="changed_files",
                allow_empty=False,
            ),
        )
        if len(self.changed_files) != len(set(self.changed_files)):
            raise ValueError("changed_files must not contain duplicates")
        if not isinstance(self.changes, Sequence):
            raise ValueError("changes must be a sequence of ChangeRef")
        changes = tuple(self.changes)
        if not changes or any(not isinstance(change, ChangeRef) for change in changes):
            raise ValueError("changes must contain at least one ChangeRef")
        unknown_files = sorted(
            {change.file for change in changes} - set(self.changed_files)
        )
        if unknown_files:
            raise ValueError(
                "change refs must belong to changed_files: " + ", ".join(unknown_files)
            )
        object.__setattr__(self, "changes", changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "base_sha": self.base_sha,
            "diff": self.diff,
            "changed_files": list(self.changed_files),
            "changes": [change.to_dict() for change in self.changes],
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ReviewRequest:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset(
                {"identity", "base_sha", "diff", "changed_files", "changes"}
            ),
        )
        try:
            changes = tuple(ChangeRef.from_dict(item) for item in data["changes"])
        except TypeError as error:
            raise ValueError("changes must be a sequence of ChangeRef objects") from error
        return cls(
            identity=ReviewIdentity.from_dict(data["identity"]),
            base_sha=data["base_sha"],
            diff=data["diff"],
            changed_files=data["changed_files"],
            changes=changes,
        )

    @classmethod
    def from_json(cls, payload: str) -> ReviewRequest:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))
