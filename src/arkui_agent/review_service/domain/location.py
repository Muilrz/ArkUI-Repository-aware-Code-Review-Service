from __future__ import annotations

from dataclasses import dataclass

from ._validation import (
    canonical_json,
    load_json_object,
    non_negative_int,
    positive_int,
    strict_mapping,
)


@dataclass(frozen=True, slots=True)
class SourceRange:
    start_line: int
    end_line: int
    start_column: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "start_line",
            positive_int(self.start_line, field="start_line"),
        )
        object.__setattr__(
            self,
            "end_line",
            positive_int(self.end_line, field="end_line"),
        )
        if self.start_column is not None:
            object.__setattr__(
                self,
                "start_column",
                non_negative_int(self.start_column, field="start_column"),
            )
        if self.end_column is not None:
            object.__setattr__(
                self,
                "end_column",
                non_negative_int(self.end_column, field="end_column"),
            )
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        if (
            self.end_line == self.start_line
            and self.start_column is not None
            and self.end_column is not None
            and self.end_column < self.start_column
        ):
            raise ValueError(
                "end_column must be greater than or equal to start_column "
                "for a single-line range"
            )

    def to_dict(self) -> dict[str, int | None]:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_column": self.start_column,
            "end_column": self.end_column,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> SourceRange:
        data = strict_mapping(
            value,
            type_name=cls.__name__,
            required=frozenset(
                {"start_line", "end_line", "start_column", "end_column"}
            ),
        )
        return cls(
            start_line=data["start_line"],
            end_line=data["end_line"],
            start_column=data["start_column"],
            end_column=data["end_column"],
        )

    @classmethod
    def from_json(cls, payload: str) -> SourceRange:
        return cls.from_dict(load_json_object(payload, type_name=cls.__name__))
