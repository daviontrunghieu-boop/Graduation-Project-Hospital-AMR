from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

if __package__ in (None, ""):
    from face_states import FaceState
else:
    from .face_states import FaceState


@dataclass(frozen=True, slots=True)
class FaceRenderPayload:
    state: FaceState
    primary_text: str
    secondary_text: str = ""
    queue_code: str = ""
    order_label: str = ""
    room_label: str = ""

    def with_state(self, state: FaceState) -> "FaceRenderPayload":
        return FaceRenderPayload(
            state=state,
            primary_text=self.primary_text,
            secondary_text=self.secondary_text,
            queue_code=self.queue_code,
            order_label=self.order_label,
            room_label=self.room_label,
        )


_SAMPLE_PAYLOADS: Final[dict[FaceState, FaceRenderPayload]] = {
    FaceState.IDLE: FaceRenderPayload(
        state=FaceState.IDLE,
        primary_text="Sẵn sàng hỗ trợ",
        secondary_text="Mời đến gần để bắt đầu",
    ),
    FaceState.ATTENTION: FaceRenderPayload(
        state=FaceState.ATTENTION,
        primary_text="Tôi đang chú ý",
        secondary_text="Xin mời",
    ),
    FaceState.GREETING: FaceRenderPayload(
        state=FaceState.GREETING,
        primary_text="Xin chào, tôi sẽ hỗ trợ bạn",
        secondary_text="Làm ơn nhìn vào robot",
    ),
    FaceState.LISTENING: FaceRenderPayload(
        state=FaceState.LISTENING,
        primary_text="Tôi đang lắng nghe",
        secondary_text="Bạn có thể nói lại nếu cần",
    ),
    FaceState.SPEAKING: FaceRenderPayload(
        state=FaceState.SPEAKING,
        primary_text="Mời bạn chú ý",
        secondary_text="Tôi đang hướng dẫn",
    ),
    FaceState.CALLING_PATIENT: FaceRenderPayload(
        state=FaceState.CALLING_PATIENT,
        primary_text="Mời số A012",
        secondary_text="Đến phòng 3",
        queue_code="Mã A012",
        order_label="STT 12",
        room_label="Phòng 3",
    ),
    FaceState.CONFIRMING: FaceRenderPayload(
        state=FaceState.CONFIRMING,
        primary_text="Đã xác nhận",
        secondary_text="Chuẩn bị dẫn đường",
        queue_code="Mã A012",
        room_label="Phòng 3",
    ),
    FaceState.NAVIGATING: FaceRenderPayload(
        state=FaceState.NAVIGATING,
        primary_text="Mời đi theo tôi",
        secondary_text="Đang đến phòng 3",
        queue_code="Mã A012",
        room_label="Phòng 3",
    ),
    FaceState.ARRIVED: FaceRenderPayload(
        state=FaceState.ARRIVED,
        primary_text="Đã đến nơi",
        secondary_text="Chúc bạn khám tốt",
        room_label="Phòng 3",
    ),
    FaceState.WAITING_RETRY: FaceRenderPayload(
        state=FaceState.WAITING_RETRY,
        primary_text="Tôi chưa nghe rõ",
        secondary_text="Vui lòng thử lại",
    ),
    FaceState.ERROR_OR_HUMAN_ASSISTANCE: FaceRenderPayload(
        state=FaceState.ERROR_OR_HUMAN_ASSISTANCE,
        primary_text="Cần hỗ trợ thêm",
        secondary_text="Vui lòng liên hệ quầy tiếp nhận",
    ),
}
_PUBLIC_SCREEN_TEXT_STATES: Final[frozenset[FaceState]] = frozenset(FaceState)


def sample_payload_for_state(state: FaceState) -> FaceRenderPayload:
    return _SAMPLE_PAYLOADS[state]


def build_runtime_payload(
    state: FaceState,
    *,
    primary_text: str = "",
    secondary_text: str = "",
    queue_code: str = "",
    order_label: str = "",
    room_label: str = "",
) -> FaceRenderPayload:
    base = sample_payload_for_state(state)
    safe_queue_code = _sanitize_queue_code(queue_code)
    safe_order_label = _sanitize_order_label(order_label)
    safe_room_label = _sanitize_room_label(room_label)
    resolved_primary = _resolve_primary_text(
        state=state,
        primary_text=primary_text,
        fallback=base.primary_text,
        queue_code=safe_queue_code,
        order_label=safe_order_label,
        room_label=safe_room_label,
    )
    resolved_secondary = _resolve_secondary_text(
        state=state,
        secondary_text=secondary_text,
        fallback=base.secondary_text,
        room_label=safe_room_label,
    )
    return FaceRenderPayload(
        state=state,
        primary_text=resolved_primary,
        secondary_text=resolved_secondary,
        queue_code=safe_queue_code or base.queue_code,
        order_label=safe_order_label or base.order_label,
        room_label=safe_room_label or base.room_label,
    )


def _resolve_primary_text(
    *,
    state: FaceState,
    primary_text: str,
    fallback: str,
    queue_code: str,
    order_label: str,
    room_label: str,
) -> str:
    if state in _PUBLIC_SCREEN_TEXT_STATES:
        return _default_primary_text(
            state=state,
            fallback=fallback,
            queue_code=queue_code,
            order_label=order_label,
            room_label=room_label,
        )
    return _sanitize_public_text(primary_text, limit=64) or _default_primary_text(
        state=state,
        fallback=fallback,
        queue_code=queue_code,
        order_label=order_label,
        room_label=room_label,
    )


def _resolve_secondary_text(
    *,
    state: FaceState,
    secondary_text: str,
    fallback: str,
    room_label: str,
) -> str:
    if state in _PUBLIC_SCREEN_TEXT_STATES:
        return _default_secondary_text(
            state=state,
            fallback=fallback,
            room_label=room_label,
        )
    return _sanitize_public_text(secondary_text, limit=80) or _default_secondary_text(
        state=state,
        fallback=fallback,
        room_label=room_label,
    )


def _default_primary_text(
    *,
    state: FaceState,
    fallback: str,
    queue_code: str,
    order_label: str,
    room_label: str,
) -> str:
    if state == FaceState.CALLING_PATIENT:
        if queue_code:
            return f"Mời {queue_code}"
        if order_label:
            return f"Mời {order_label}"
    if state == FaceState.CONFIRMING:
        if room_label:
            return "Đã xác nhận lộ trình"
    if state == FaceState.NAVIGATING and room_label:
        return "Mời đi theo tôi"
    if state == FaceState.ARRIVED and room_label:
        return "Đã đến nơi"
    return fallback


def _default_secondary_text(
    *,
    state: FaceState,
    fallback: str,
    room_label: str,
) -> str:
    if state == FaceState.CALLING_PATIENT and room_label:
        return f"Đến {room_label}"
    if state == FaceState.CONFIRMING and room_label:
        return f"Chuẩn bị dẫn đến {room_label}"
    if state == FaceState.NAVIGATING and room_label:
        return f"Đang đến {room_label}"
    if state == FaceState.ARRIVED and room_label:
        return f"Bạn đã đến {room_label}"
    return fallback


def _sanitize_public_text(value: str, *, limit: int) -> str:
    compact = " ".join(value.replace("\n", " ").split())
    return compact[:limit]


def _sanitize_queue_code(value: str) -> str:
    compact = _sanitize_public_text(value, limit=48)
    if not compact:
        return ""

    queue_code_match = re.search(r"(?:M[aã]\s*)?([A-Za-z]{1,4}\d{1,4})", compact, re.IGNORECASE)
    if queue_code_match:
        return f"Mã {queue_code_match.group(1).upper()}"

    number_match = re.search(r"\b(\d{1,4})\b", compact)
    if number_match:
        return f"STT {number_match.group(1)}"

    return ""


def _sanitize_order_label(value: str) -> str:
    compact = _sanitize_public_text(value, limit=48)
    if not compact:
        return ""
    number_match = re.search(r"\b(\d{1,4})\b", compact)
    if number_match:
        return f"STT {number_match.group(1)}"
    return ""


def _sanitize_room_label(value: str) -> str:
    compact = _sanitize_public_text(value, limit=48)
    if not compact:
        return ""

    room_match = re.search(
        r"(?:Ph[oò]ng|P)\s*([A-Za-z]?\d{1,4}[A-Za-z]?)",
        compact,
        re.IGNORECASE,
    )
    if room_match:
        return f"Phòng {room_match.group(1).upper()}"

    number_match = re.search(r"\b(\d{1,4})\b", compact)
    if number_match:
        return f"Phòng {number_match.group(1)}"

    destination_match = re.search(
        r"\b(?P<prefix>Ph[oòóỏõọơờớởỡợ]ng|Phong|Qu[ầấẩẫậàáảãạâầấẩẫậ]y|Quay|Khu|Khoa|"
        r"B[aàáảãạâầấẩẫậ]n|Ban|S[aàáảãạâầấẩẫậ]nh|Sanh|T[oòóỏõọôồốổỗộơờớởỡợ]a|Toa)\s+"
        r"(?P<rest>[A-Za-zÀ-ỹ0-9][A-Za-zÀ-ỹ0-9\s/-]{0,30})",
        compact,
        re.IGNORECASE,
    )
    if destination_match:
        prefix = _canonicalize_destination_prefix(destination_match.group("prefix"))
        rest = destination_match.group("rest").strip(" ,.;:")
        if rest:
            return f"{prefix} {rest}"

    return ""


def _canonicalize_destination_prefix(value: str) -> str:
    normalized = value.casefold()
    if normalized.startswith(("ph",)):
        return "Phòng"
    if normalized.startswith(("qu",)):
        return "Quầy"
    if normalized.startswith("khu"):
        return "Khu"
    if normalized.startswith("khoa"):
        return "Khoa"
    if normalized.startswith("ba"):
        return "Bàn"
    if normalized.startswith("sa"):
        return "Sảnh"
    if normalized.startswith(("to", "tò", "tó", "tỏ", "tõ", "tọ")):
        return "Tòa"
    return value
