from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._validation import canonical_json, load_json_object, non_empty_string, strict_mapping


@dataclass(frozen=True, slots=True)
class ReviewIdentity:
    repository: str
    pr_id: str
    head_sha: str
    review_policy_version: str

    def __post_init__(self) -> None:
        for field in (
            "repository",
            "pr_id",
            "head_sha",
            "review_policy_version",
        ):
            object.__setattr__(
                self,
                field,
                non_empty_string(getattr(self, field), field=field),
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "pr_id": self.pr_id,
            "head_sha": self.head_sha,
            "review_policy_version": self.review_policy_version,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> ReviewIdentity:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset(
                {"repository", "pr_id", "head_sha", "review_policy_version"}
            ),
        )
        return cls(
            repository=data["repository"],
            pr_id=data["pr_id"],
            head_sha=data["head_sha"],
            review_policy_version=data["review_policy_version"],
        )

    @classmethod
    def from_json(cls, payload: str) -> ReviewIdentity:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))
