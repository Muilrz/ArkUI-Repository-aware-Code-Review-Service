from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


def non_empty_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def optional_non_empty_string(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return non_empty_string(value, field=field)


def positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def non_negative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def confidence_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("confidence must be a number between 0 and 1")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError("confidence must be a number between 0 and 1")
    return normalized


def strict_mapping(
    value: object,
    *,
    type_name: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{type_name} must be a JSON object")
    actual = set(value)
    missing = required - actual
    unknown = actual - required - optional
    if missing:
        raise ValueError(f"{type_name} missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{type_name} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def tuple_of_strings(value: object, *, field: str, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a sequence of strings")
    result = tuple(non_empty_string(item, field=field) for item in value)
    if not allow_empty and not result:
        raise ValueError(f"{field} must not be empty")
    return result


def load_json_object(payload: str, *, type_name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"{type_name} must be valid JSON") from error
    if not isinstance(value, Mapping):
        raise ValueError(f"{type_name} must be a JSON object")
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
