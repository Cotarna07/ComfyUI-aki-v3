from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class TaskStatus:
    task_id: str
    stage: str
    status: str
    started_at: str
    finished_at: str | None = None
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    error_message: str | None = None
    retry_count: int = 0

    @classmethod
    def started(cls, stage: str, input_refs: list[str] | None = None, retry_count: int = 0) -> "TaskStatus":
        return cls(
            task_id=f"{stage}-{uuid4().hex[:10]}",
            stage=stage,
            status="running",
            started_at=utc_now_iso(),
            input_refs=input_refs or [],
            retry_count=retry_count,
        )

    def complete(self, output_refs: list[str] | None = None) -> None:
        self.status = "succeeded"
        self.finished_at = utc_now_iso()
        self.output_refs = output_refs or []
        self.error_message = None

    def reuse(self, output_refs: list[str] | None = None) -> None:
        self.status = "reused"
        self.finished_at = utc_now_iso()
        self.output_refs = output_refs or []
        self.error_message = None

    def fail(self, error: Exception) -> None:
        self.status = "failed"
        self.finished_at = utc_now_iso()
        self.error_message = str(error)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "stage": self.stage,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "input_refs": self.input_refs,
            "output_refs": self.output_refs,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
        }
