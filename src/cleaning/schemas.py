"""Pydantic schemas for Data-Cleaning Proposals, Operations, and Audit Logs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AllowedOperation = Literal[
    "drop_duplicates",
    "strip_whitespace",
    "normalize_case",
    "parse_dates",
    "to_numeric",
    "fill_missing",
    "map_categories",
    "flag_outliers",
]


class CleaningStep(BaseModel):
    """An atomic, deterministic cleaning transformation proposed for human approval."""

    step_id: int = Field(..., description="Unique incremental sequence integer")
    column: str = Field(..., description="Target column name, or '_row' for whole-table actions")
    issue: str = Field(..., description="Identified data quality issue")
    operation: AllowedOperation = Field(..., description="Whitelisted operation to execute")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters required by the operation (e.g. mapping, strategy, mode)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the proposed operation between 0.0 and 1.0",
    )
    rationale: str = Field(..., description="Human-readable business justification for the step")


class CleaningPlan(BaseModel):
    """Collection of proposed steps for a dataset."""

    table_name: str = Field(..., description="Target dataset name")
    summary: str = Field(..., description="Executive summary of data health and proposed fixes")
    steps: list[CleaningStep] = Field(
        default_factory=list, description="Ordered sequence of cleaning steps"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Planner execution metadata (fallback status, step counts)"
    )


class AuditLogEntry(BaseModel):
    """Execution record for an approved step."""

    step_id: int
    column: str
    operation: str
    params: dict[str, Any]
    rows_affected: int
    before_samples: list[Any]
    after_samples: list[Any]
    status: Literal["applied", "rejected_by_human", "skipped", "error"]
    message: str


class CleaningReport(BaseModel):
    """Final summary report of the cleaning execution."""

    table_name: str
    original_rows: int
    final_rows: int
    steps_applied: int
    steps_rejected: int
    audit_log: list[AuditLogEntry]
