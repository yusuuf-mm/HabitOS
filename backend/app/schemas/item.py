"""Item schemas (commitments and deadlines)."""
import re
from datetime import date, datetime, time as dtime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_START_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

_COMMITMENT_ONLY = ("dueOn", "prepMinutes", "reminderOffsets")
_DEADLINE_FORBIDDEN = (
    "startDate",
    "startTime",
    "durationMinutes",
    "recurrence",
    "recurrenceUntil",
    "weekdays",
    "runDays",
)


def _parse_start_time(value: str) -> dtime:
    match = _START_TIME_RE.match(value)
    if not match:
        raise ValueError("startTime must be HH:MM (24h)")
    minute = int(match.group(2))
    if minute % 15 != 0:
        raise ValueError("startTime minutes must be a multiple of 15")
    return dtime(hour=int(match.group(1)), minute=minute)


class ItemCreate(BaseModel):
    """Create commitment or deadline request."""

    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["commitment", "deadline"]
    title: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = None
    isPrivate: bool = Field(default=False)
    startDate: Optional[date] = Field(None)
    startTime: Optional[str] = Field(None)
    durationMinutes: Optional[int] = Field(None)
    recurrence: Optional[Literal["once", "daily", "weekdays", "weekly"]] = Field(None)
    recurrenceUntil: Optional[date] = Field(None)
    runDays: Optional[int] = Field(None, ge=1)
    weekdays: Optional[List[int]] = Field(None)
    dueOn: Optional[date] = Field(None)
    prepMinutes: Optional[int] = Field(None, ge=0)
    prepLeadDays: Optional[int] = Field(None, ge=0)
    reminderOffsets: Optional[List[int]] = Field(None)

    @field_validator("startTime")
    @classmethod
    def validate_start_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        _parse_start_time(v)
        return v

    @field_validator("durationMinutes")
    @classmethod
    def validate_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 15 or v > 1440:
            raise ValueError("durationMinutes must be between 15 and 1440")
        if v % 15 != 0:
            raise ValueError("durationMinutes must be a multiple of 15")
        return v

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is None:
            return v
        if any(not isinstance(d, int) or d < 0 or d > 6 for d in v):
            raise ValueError("weekdays must be a list of ints 0..6 (0=Mon)")
        return v

    @field_validator("reminderOffsets")
    @classmethod
    def validate_reminder_offsets(
        cls, v: Optional[List[int]]
    ) -> Optional[List[int]]:
        if v is None:
            return v
        if any(not isinstance(o, int) or o < 0 for o in v):
            raise ValueError("reminderOffsets must be a list of non-negative ints")
        return v

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "ItemCreate":
        """Cross-kind fields are a 422 error, never silently dropped."""
        if self.kind == "commitment":
            missing = [
                f
                for f in ("startDate", "startTime", "durationMinutes", "recurrence")
                if getattr(self, f) is None
            ]
            if missing:
                raise ValueError(
                    f"commitment requires {', '.join(missing)}"
                )
            carried = [f for f in _COMMITMENT_ONLY if getattr(self, f) is not None]
            if carried:
                raise ValueError(
                    f"commitment must not carry {', '.join(carried)}"
                )
        else:
            if self.dueOn is None:
                raise ValueError("deadline requires dueOn")
            carried = [f for f in _DEADLINE_FORBIDDEN if getattr(self, f) is not None]
            if carried:
                raise ValueError(
                    f"deadline must not carry {', '.join(carried)}"
                )
        return self


class ItemUpdate(BaseModel):
    """Update item request (kind cannot change; light validation only)."""

    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    notes: Optional[str] = Field(None)
    isPrivate: Optional[bool] = Field(None)
    startDate: Optional[date] = Field(None)
    startTime: Optional[str] = Field(None)
    durationMinutes: Optional[int] = Field(None)
    recurrence: Optional[Literal["once", "daily", "weekdays", "weekly"]] = Field(None)
    recurrenceUntil: Optional[date] = Field(None)
    runDays: Optional[int] = Field(None, ge=1)
    weekdays: Optional[List[int]] = Field(None)
    dueOn: Optional[date] = Field(None)
    prepMinutes: Optional[int] = Field(None, ge=0)
    prepLeadDays: Optional[int] = Field(None, ge=0)
    reminderOffsets: Optional[List[int]] = Field(None)

    @field_validator("startTime")
    @classmethod
    def validate_start_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        _parse_start_time(v)
        return v

    @field_validator("durationMinutes")
    @classmethod
    def validate_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 15 or v > 1440:
            raise ValueError("durationMinutes must be between 15 and 1440")
        if v % 15 != 0:
            raise ValueError("durationMinutes must be a multiple of 15")
        return v

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is None:
            return v
        if any(not isinstance(d, int) or d < 0 or d > 6 for d in v):
            raise ValueError("weekdays must be a list of ints 0..6 (0=Mon)")
        return v

    @field_validator("reminderOffsets")
    @classmethod
    def validate_reminder_offsets(
        cls, v: Optional[List[int]]
    ) -> Optional[List[int]]:
        if v is None:
            return v
        if any(not isinstance(o, int) or o < 0 for o in v):
            raise ValueError("reminderOffsets must be a list of non-negative ints")
        return v


def _weekday_bitmask_to_list(value: object) -> object:
    if isinstance(value, int) and not isinstance(value, bool):
        return [i for i in range(7) if value & (1 << i)]
    return value


def _time_to_hhmm(value: object) -> object:
    if isinstance(value, dtime):
        return value.strftime("%H:%M")
    return value


class ItemResponse(BaseModel):
    """Item response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    kind: str
    title: str
    notes: Optional[str] = None
    isPrivate: bool = Field(
        ..., validation_alias="is_private", serialization_alias="isPrivate"
    )
    startDate: Optional[date] = Field(
        None, validation_alias="start_date", serialization_alias="startDate"
    )
    startTime: Optional[str] = Field(
        None, validation_alias="start_time", serialization_alias="startTime"
    )
    timezone: Optional[str] = None
    durationMinutes: Optional[int] = Field(
        None,
        validation_alias="duration_minutes",
        serialization_alias="durationMinutes",
    )
    recurrence: Optional[str] = None
    recurrenceUntil: Optional[date] = Field(
        None,
        validation_alias="recurrence_until",
        serialization_alias="recurrenceUntil",
    )
    weekdays: Optional[List[int]] = Field(
        None, validation_alias="weekdays", serialization_alias="weekdays"
    )
    dueOn: Optional[date] = Field(
        None, validation_alias="due_on", serialization_alias="dueOn"
    )
    prepMinutes: Optional[int] = Field(
        None, validation_alias="prep_minutes", serialization_alias="prepMinutes"
    )
    prepLeadDays: Optional[int] = Field(
        None, validation_alias="prep_lead_days", serialization_alias="prepLeadDays"
    )
    reminderOffsets: Optional[List[int]] = Field(
        None,
        validation_alias="reminder_offsets",
        serialization_alias="reminderOffsets",
    )
    warnings: List[str] = Field(default_factory=list)
    createdAt: Optional[datetime] = Field(
        None, validation_alias="created_at", serialization_alias="createdAt"
    )

    @field_validator("weekdays", mode="before")
    @classmethod
    def convert_weekday_bitmask(cls, v: object) -> object:
        return _weekday_bitmask_to_list(v)

    @field_validator("startTime", mode="before")
    @classmethod
    def render_start_time(cls, v: object) -> object:
        return _time_to_hhmm(v)
