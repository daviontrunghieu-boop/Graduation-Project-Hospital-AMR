from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

if __package__ in (None, ""):
    from face_states import FaceState
    from payloads import FaceRenderPayload
else:
    from .face_states import FaceState
    from .payloads import FaceRenderPayload


class PanelTabId(str, Enum):
    WAITING = "waiting"
    TURN_INFO = "turn_info"
    MAP = "map"
    ROBOT_STATUS = "robot_status"
    HELP = "help"


class PanelActionId(str, Enum):
    VIEW_INFO = "view_info"
    VIEW_MAP = "view_map"
    CONFIRM_UNDERSTANDING = "confirm_understanding"


@dataclass(frozen=True, slots=True)
class PanelTabSpec:
    key: str
    label: str


@dataclass(frozen=True, slots=True)
class PanelActionState:
    key: str
    label: str
    active: bool = False


@dataclass(frozen=True, slots=True)
class PanelViewState:
    active_tab: str
    title: str
    mode_label: str
    summary: str
    left_label: str
    left_value: str
    right_label: str
    right_value: str
    map_title: str
    map_caption: str
    footer: str
    actions: tuple[PanelActionState, ...]


TAB_SPECS: Final[tuple[PanelTabSpec, ...]] = (
    PanelTabSpec(PanelTabId.WAITING.value, "Trang chờ"),
    PanelTabSpec(PanelTabId.TURN_INFO.value, "Thông tin lượt"),
    PanelTabSpec(PanelTabId.MAP.value, "Bản đồ dẫn đường"),
    PanelTabSpec(PanelTabId.ROBOT_STATUS.value, "Trạng thái robot"),
    PanelTabSpec(PanelTabId.HELP.value, "Cần hỗ trợ"),
)


STATE_LABELS: Final[dict[FaceState, str]] = {
    FaceState.IDLE: "Robot đang chờ bạn",
    FaceState.ATTENTION: "Robot đang chú ý đến bạn",
    FaceState.GREETING: "Robot đang chào bạn",
    FaceState.LISTENING: "Robot đang lắng nghe bạn",
    FaceState.SPEAKING: "Robot đang hướng dẫn bạn",
    FaceState.CALLING_PATIENT: "Robot đang gọi lượt",
    FaceState.CONFIRMING: "Robot đang chờ bạn xác nhận",
    FaceState.NAVIGATING: "Robot đang dẫn bạn đi",
    FaceState.ARRIVED: "Robot đã đưa bạn đến nơi",
    FaceState.WAITING_RETRY: "Robot cần bạn nhắc lại",
    FaceState.ERROR_OR_HUMAN_ASSISTANCE: "Nhân viên sẽ hỗ trợ bạn",
}


STATE_SUMMARIES: Final[dict[FaceState, str]] = {
    FaceState.IDLE: "Xin mời đến gần robot khi bạn cần được hướng dẫn.",
    FaceState.ATTENTION: "Robot đã nhận ra bạn và sẵn sàng hỗ trợ.",
    FaceState.GREETING: "Robot đang chào bạn để bắt đầu hỗ trợ.",
    FaceState.LISTENING: "Robot đang nghe lại yêu cầu của bạn.",
    FaceState.SPEAKING: "Robot đang nói ngắn gọn để hướng dẫn bạn.",
    FaceState.CALLING_PATIENT: "Thông tin lượt của bạn đang được hiển thị để đối chiếu nhanh.",
    FaceState.CONFIRMING: "Robot đang chờ bạn xác nhận trước khi bắt đầu dẫn đường.",
    FaceState.NAVIGATING: "Xin mời đi theo robot và nhìn lối đi khi cần.",
    FaceState.ARRIVED: "Robot đã đưa bạn đến đúng nơi cần đến.",
    FaceState.WAITING_RETRY: "Xin vui lòng nhắc lại để robot hỗ trợ đúng hơn.",
    FaceState.ERROR_OR_HUMAN_ASSISTANCE: "Nếu cần thêm hỗ trợ, xin vui lòng liên hệ quầy tiếp nhận.",
}


class PanelTabsController:
    def __init__(self) -> None:
        self.tab_specs = TAB_SPECS
        self.current_payload: FaceRenderPayload | None = None
        self.current_map_snapshot = None
        self.default_tab = PanelTabId.WAITING.value
        self.active_tab = PanelTabId.WAITING.value
        self.manual_override = False
        self.confirmed = False

    def sync_runtime_payload(
        self,
        payload: FaceRenderPayload,
        *,
        default_tab: str,
        map_snapshot=None,
    ) -> PanelViewState:
        self.current_payload = payload
        self.current_map_snapshot = map_snapshot
        self.default_tab = default_tab
        self.active_tab = default_tab
        self.manual_override = False
        self.confirmed = False
        return self.view_state()

    def sync_map_snapshot(self, map_snapshot) -> PanelViewState:
        self._require_payload()
        self.current_map_snapshot = map_snapshot
        return self.view_state()

    def activate_tab(self, tab_key: str) -> PanelViewState:
        self._require_payload()
        self.active_tab = tab_key
        self.manual_override = tab_key != self.default_tab
        return self.view_state()

    def trigger_action(self, action_key: str) -> PanelViewState:
        self._require_payload()
        if action_key == PanelActionId.VIEW_INFO.value:
            return self.activate_tab(PanelTabId.TURN_INFO.value)
        if action_key == PanelActionId.VIEW_MAP.value:
            return self.activate_tab(PanelTabId.MAP.value)
        if action_key == PanelActionId.CONFIRM_UNDERSTANDING.value:
            self.confirmed = True
            self.manual_override = True
            return self.view_state()
        raise ValueError(f"Unsupported panel action: {action_key}")

    def view_state(self) -> PanelViewState:
        payload = self._require_payload()

        if self.active_tab == PanelTabId.WAITING.value:
            title = "Trang chờ"
            summary = STATE_SUMMARIES[payload.state]
            left_label = "Robot đang"
            left_value = STATE_LABELS[payload.state]
            right_label = "Điểm đến"
            right_value = payload.room_label or "Sẽ hiển thị khi có lượt"
            map_title = "Bản đồ chờ"
            map_caption = "Khi có phòng khám, lối đi sẽ hiện tại đây để bạn nhìn nhanh."
        elif self.active_tab == PanelTabId.TURN_INFO.value:
            title = "Thông tin lượt"
            summary = _join_lines(
                payload.primary_text,
                payload.secondary_text or "Thông tin lượt của bạn đang hiển thị để đối chiếu nhanh.",
            )
            left_label = "Mã hoặc STT"
            left_value = payload.queue_code or payload.order_label or "Chưa có lượt"
            right_label = "Phòng khám"
            right_value = payload.room_label or "Chưa cấp phòng"
            map_title = "Tuyến đến phòng"
            map_caption = _map_caption_for_payload(payload, self.current_map_snapshot)
        elif self.active_tab == PanelTabId.MAP.value:
            title = "Bản đồ dẫn đường"
            summary = _map_summary_for_payload(payload, self.current_map_snapshot)
            left_label = "Mã hoặc STT"
            left_value = payload.queue_code or payload.order_label or "Đang chờ lượt"
            right_label = "Điểm đến"
            right_value = payload.room_label or "Đang chờ phòng khám"
            map_title = "Lộ trình đến phòng"
            map_caption = _map_caption_for_payload(payload, self.current_map_snapshot)
        elif self.active_tab == PanelTabId.ROBOT_STATUS.value:
            title = "Robot đang hỗ trợ bạn"
            summary = STATE_SUMMARIES[payload.state]
            left_label = "Robot đang"
            left_value = STATE_LABELS[payload.state]
            right_label = "Bước hiện tại"
            right_value = _status_tempo(payload.state)
            map_title = "Vị trí lối đi"
            map_caption = "Khi robot bắt đầu dẫn đường, lối đi sẽ hiển thị tại đây."
        else:
            title = "Cần hỗ trợ"
            summary = _help_summary(payload.state)
            left_label = "Liên hệ"
            left_value = "Quầy tiếp nhận"
            right_label = "Điểm gần nhất"
            right_value = payload.room_label or "Nhân viên sẽ hỗ trợ trực tiếp"
            map_title = "Vị trí hỗ trợ"
            map_caption = "Vị trí quầy hỗ trợ sẽ hiển thị tại đây khi cần."

        return PanelViewState(
            active_tab=self.active_tab,
            title=title,
            mode_label=_mode_label(
                payload=payload,
                default_tab=self.default_tab,
                active_tab=self.active_tab,
                manual_override=self.manual_override,
                confirmed=self.confirmed,
            ),
            summary=summary,
            left_label=left_label,
            left_value=left_value,
            right_label=right_label,
            right_value=right_value,
            map_title=map_title,
            map_caption=map_caption,
            footer=_footer_copy(
                active_tab=self.active_tab,
                default_tab=self.default_tab,
                manual_override=self.manual_override,
                confirmed=self.confirmed,
            ),
            actions=_build_actions(active_tab=self.active_tab, confirmed=self.confirmed),
        )

    def _require_payload(self) -> FaceRenderPayload:
        if self.current_payload is None:
            raise RuntimeError("Panel view requested before runtime payload was loaded")
        return self.current_payload


def _mode_label(
    *,
    payload: FaceRenderPayload,
    default_tab: str,
    active_tab: str,
    manual_override: bool,
    confirmed: bool,
) -> str:
    if confirmed:
        return "Đã ghi nhận. Xin mời đi tiếp"
    if manual_override and active_tab != default_tab:
        if active_tab == PanelTabId.MAP.value:
            return "Bạn đang xem lối đi"
        if active_tab == PanelTabId.TURN_INFO.value:
            return "Bạn đang xem lại thông tin lượt"
        if active_tab == PanelTabId.HELP.value:
            return "Bạn đang xem hướng dẫn hỗ trợ"
    return STATE_LABELS[payload.state]


def _footer_copy(
    *,
    active_tab: str,
    default_tab: str,
    manual_override: bool,
    confirmed: bool,
) -> str:
    if confirmed:
        if default_tab == PanelTabId.HELP.value:
            return "Đã ghi nhận. Nhân viên sẽ hỗ trợ bạn trong giây lát."
        return "Đã ghi nhận. Xin mời đi theo robot."
    if manual_override and active_tab != default_tab:
        if active_tab == PanelTabId.MAP.value:
            return "Bạn có thể xem lại lối đi tại đây."
        if active_tab == PanelTabId.TURN_INFO.value:
            return "Bạn có thể xem lại thông tin lượt tại đây."
        if active_tab == PanelTabId.HELP.value:
            return "Nếu cần thêm hỗ trợ, xin vui lòng liên hệ quầy tiếp nhận."
    if active_tab == PanelTabId.MAP.value:
        return "Lối đi đang hiển thị tại đây để bạn đi theo robot."
    if active_tab == PanelTabId.HELP.value:
        return "Nếu cần thêm hỗ trợ, xin vui lòng liên hệ quầy tiếp nhận."
    return "Bạn có thể chạm để xem lại thông tin hoặc lối đi khi cần."


def _build_actions(*, active_tab: str, confirmed: bool) -> tuple[PanelActionState, ...]:
    return (
        PanelActionState(
            PanelActionId.VIEW_INFO.value,
            "Xem lại lượt",
            active=active_tab == PanelTabId.TURN_INFO.value,
        ),
        PanelActionState(
            PanelActionId.VIEW_MAP.value,
            "Xem lối đi",
            active=active_tab == PanelTabId.MAP.value,
        ),
        PanelActionState(
            PanelActionId.CONFIRM_UNDERSTANDING.value,
            "Đã hiểu",
            active=confirmed,
        ),
    )


def _status_tempo(state: FaceState) -> str:
    if state in (FaceState.CALLING_PATIENT, FaceState.CONFIRMING):
        return "Đang gọi và đối chiếu lượt"
    if state == FaceState.NAVIGATING:
        return "Đang dẫn bạn đến nơi"
    if state == FaceState.ERROR_OR_HUMAN_ASSISTANCE:
        return "Đang chờ nhân viên hỗ trợ"
    return "Đang chờ để hỗ trợ bạn"


def _map_caption_for_payload(payload: FaceRenderPayload, map_snapshot=None) -> str:
    if map_snapshot is not None:
        if payload.room_label:
            return f"Lối đi đến {payload.room_label.lower()} đang cập nhật theo thời gian thực."
        return "Lối đi đang cập nhật theo thời gian thực để bạn nhìn nhanh."
    if payload.room_label:
        return f"Khi robot bắt đầu dẫn đường, lối đi đến {payload.room_label.lower()} sẽ hiện tại đây."
    return "Khi robot bắt đầu dẫn đường, lối đi sẽ hiện tại đây để bạn dễ theo dõi."


def _map_summary_for_payload(payload: FaceRenderPayload, map_snapshot) -> str:
    if map_snapshot is None:
        return "Bạn có thể nhìn nhanh vào đây để biết robot sẽ dẫn mình đi đâu."
    destination = payload.room_label or "điểm đến hiện tại"
    return f"Bệnh nhân có thể nhìn nhanh lối đi đang hiển thị để tiếp tục đi theo robot đến {destination.lower()}."


def _join_lines(primary: str, secondary: str) -> str:
    return f"{primary}. {secondary}".strip()


def _help_summary(state: FaceState) -> str:
    if state == FaceState.WAITING_RETRY:
        return "Tôi chưa nghe rõ. Vui lòng thử lại."
    if state == FaceState.ERROR_OR_HUMAN_ASSISTANCE:
        return "Cần hỗ trợ thêm. Vui lòng liên hệ quầy tiếp nhận."
    return "Nếu cần hỗ trợ, vui lòng liên hệ quầy tiếp nhận."
