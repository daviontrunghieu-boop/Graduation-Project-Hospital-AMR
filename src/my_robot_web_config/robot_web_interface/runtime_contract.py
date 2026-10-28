from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

if __package__ in (None, ""):
    from face_states import FaceState
    from payloads import FaceRenderPayload
else:
    from .face_states import FaceState
    from .payloads import FaceRenderPayload


SNAPSHOT_ENV_VAR: Final[str] = "ROBOT_UI_SNAPSHOT_PATH"
DEFAULT_SNAPSHOT_BASENAME: Final[str] = "robothospital_runtime_snapshot.json"


def default_snapshot_path() -> Path:
    override = os.environ.get(SNAPSHOT_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return Path(tempfile.gettempdir(), DEFAULT_SNAPSHOT_BASENAME).resolve()


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    sequence: int
    emitted_at_ms: float
    source: str
    trigger: str
    state: FaceState
    primary_text: str
    secondary_text: str = ""
    queue_code: str = ""
    order_label: str = ""
    room_label: str = ""
    warning_signal_sent: bool = False

    def to_payload(self) -> FaceRenderPayload:
        return FaceRenderPayload(
            state=self.state,
            primary_text=self.primary_text,
            secondary_text=self.secondary_text,
            queue_code=self.queue_code,
            order_label=self.order_label,
            room_label=self.room_label,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "emitted_at_ms": self.emitted_at_ms,
            "source": self.source,
            "trigger": self.trigger,
            "state": self.state.value,
            "primary_text": self.primary_text,
            "secondary_text": self.secondary_text,
            "queue_code": self.queue_code,
            "order_label": self.order_label,
            "room_label": self.room_label,
            "warning_signal_sent": self.warning_signal_sent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RuntimeSnapshot":
        return cls(
            sequence=int(data["sequence"]),
            emitted_at_ms=float(data["emitted_at_ms"]),
            source=str(data["source"]),
            trigger=str(data["trigger"]),
            state=FaceState(str(data["state"])),
            primary_text=str(data.get("primary_text", "")),
            secondary_text=str(data.get("secondary_text", "")),
            queue_code=str(data.get("queue_code", "")),
            order_label=str(data.get("order_label", "")),
            room_label=str(data.get("room_label", "")),
            warning_signal_sent=bool(data.get("warning_signal_sent", False)),
        )


class RuntimeSnapshotStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_snapshot_path()

    def write(self, snapshot: RuntimeSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def read(self) -> RuntimeSnapshot | None:
        if not self.path.exists():
            return None
        return RuntimeSnapshot.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def read_if_newer(self, sequence: int) -> RuntimeSnapshot | None:
        snapshot = self.read()
        if snapshot is None or snapshot.sequence <= sequence:
            return None
        return snapshot
