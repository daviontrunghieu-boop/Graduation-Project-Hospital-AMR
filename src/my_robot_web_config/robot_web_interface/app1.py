import pathlib
import signal
import sys
import tkinter as tk
import unicodedata

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from face_renderer import FaceRenderer
    from face_states import CANONICAL_FACE_STATES, FaceState
    from input_controller import InputController
    from layout import RuntimeLayoutShell
    from map_runtime import MapRuntimeSnapshot, MapRuntimeSnapshotStore
    from panel_tabs import PanelTabsController
    from payloads import build_runtime_payload, sample_payload_for_state
    from runtime_contract import RuntimeSnapshot, RuntimeSnapshotStore
    from state_model import DEFAULT_STATE_MODEL, FaceRuntimeController
    from visual_tokens import WINDOW_HEIGHT, WINDOW_WIDTH
else:
    from .face_renderer import FaceRenderer
    from .face_states import CANONICAL_FACE_STATES, FaceState
    from .input_controller import InputController
    from .layout import RuntimeLayoutShell
    from .map_runtime import MapRuntimeSnapshot, MapRuntimeSnapshotStore
    from .panel_tabs import PanelTabsController
    from .payloads import build_runtime_payload, sample_payload_for_state
    from .runtime_contract import RuntimeSnapshot, RuntimeSnapshotStore
    from .state_model import DEFAULT_STATE_MODEL, FaceRuntimeController
    from .visual_tokens import WINDOW_HEIGHT, WINDOW_WIDTH


AUTO_CYCLE_SEQUENCE: tuple[FaceState, ...] = (
    FaceState.IDLE,
    FaceState.ATTENTION,
    FaceState.GREETING,
    FaceState.SPEAKING,
    FaceState.CALLING_PATIENT,
    FaceState.CONFIRMING,
    FaceState.NAVIGATING,
    FaceState.ARRIVED,
    FaceState.ATTENTION,
    FaceState.LISTENING,
    FaceState.WAITING_RETRY,
    FaceState.ERROR_OR_HUMAN_ASSISTANCE,
)
AUTO_CYCLE_INTERVAL_MS = 5000


class FaceRuntimeShell:
    """Standalone runtime shell for the Phase 2 face-first robot screen."""

    def __init__(
        self,
        *,
        snapshot_store: RuntimeSnapshotStore | None = None,
        map_snapshot_store: MapRuntimeSnapshotStore | None = None,
        enable_runtime_bridge_polling: bool = True,
        enable_map_bridge_polling: bool = True,
    ) -> None:
        self.root = tk.Tk()
        self.root.title("Robot bệnh viện - màn hình hướng dẫn")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg="#050816")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg="#050816",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.layout_shell = RuntimeLayoutShell(self.canvas)
        self.face_renderer = FaceRenderer(self.canvas)
        self.state_controller = FaceRuntimeController(DEFAULT_STATE_MODEL)
        self.panel_controller = PanelTabsController()
        self.state_order = CANONICAL_FACE_STATES
        self.runtime_snapshot_store = snapshot_store or RuntimeSnapshotStore()
        self.map_snapshot_store = map_snapshot_store or MapRuntimeSnapshotStore()
        self.enable_runtime_bridge_polling = enable_runtime_bridge_polling
        self.enable_map_bridge_polling = enable_map_bridge_polling
        self.last_runtime_sequence = 0
        self.last_map_sequence = 0
        self.current_map_snapshot: MapRuntimeSnapshot | None = None
        self.auto_cycle_enabled = not (
            self.enable_runtime_bridge_polling or self.enable_map_bridge_polling
        )
        self.auto_cycle_index = 0
        self._sync_panel_view(
            self.state_controller.current_payload,
            self.state_controller.state_model.default_panel_tab(self.state_controller.current_state),
        )
        self.face_renderer.set_payload(self.state_controller.current_payload)
        self.input_controller = InputController(
            root=self.root,
            canvas=self.canvas,
            layout_shell=self.layout_shell,
            on_tab_selected=self.select_panel_tab,
            on_action=self.trigger_panel_action,
        )
        self.input_controller.install()
        self.root.bind("<Right>", lambda _event: self.step_state(1))
        self.root.bind("<Left>", lambda _event: self.step_state(-1))
        self.root.bind("1", lambda _event: self.jump_to_state(0))
        self.root.bind("2", lambda _event: self.jump_to_state(1))
        self.root.bind("3", lambda _event: self.jump_to_state(2))
        self.root.bind("4", lambda _event: self.jump_to_state(3))
        self.root.bind("5", lambda _event: self.jump_to_state(4))
        self.root.bind("6", lambda _event: self.jump_to_state(5))
        self.root.bind("7", lambda _event: self.jump_to_state(6))
        self.root.bind("8", lambda _event: self.jump_to_state(7))
        self.root.bind("9", lambda _event: self.jump_to_state(8))
        self.root.bind("0", lambda _event: self.jump_to_state(9))
        self.root.bind("-", lambda _event: self.jump_to_state(10))
        self.face_renderer.start_idle_animation()
        if self.enable_runtime_bridge_polling or self.enable_map_bridge_polling:
            self.root.after(200, self.poll_runtime_bridge)
        if self.auto_cycle_enabled:
            self.root.after(AUTO_CYCLE_INTERVAL_MS, self._advance_auto_cycle)
        self._print_dev_controls()

    def run(self) -> None:
        self.root.mainloop()

    def request_state(
        self,
        target: FaceState,
        *,
        warning_signal_sent: bool = False,
    ) -> bool:
        result = self.state_controller.request_state(
            target,
            payload=sample_payload_for_state(target),
            warning_signal_sent=warning_signal_sent,
        )
        if result.applied:
            self._sync_panel_view(
                result.payload,
                self.state_controller.state_model.default_panel_tab(result.to_state),
            )
            self.face_renderer.set_payload(result.payload, result.transition_ms)
        return result.applied

    def apply_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> bool:
        safe_payload = build_runtime_payload(
            snapshot.state,
            primary_text=snapshot.primary_text,
            secondary_text=snapshot.secondary_text,
            queue_code=snapshot.queue_code,
            order_label=snapshot.order_label,
            room_label=snapshot.room_label,
        )
        result = self.state_controller.request_state(
            snapshot.state,
            payload=safe_payload,
            warning_signal_sent=snapshot.warning_signal_sent,
            now_ms=snapshot.emitted_at_ms,
        )
        if result.applied:
            self.last_runtime_sequence = max(self.last_runtime_sequence, snapshot.sequence)
            self._sync_panel_view(
                result.payload,
                self.state_controller.state_model.default_panel_tab(result.to_state),
            )
            self.face_renderer.set_payload(result.payload, result.transition_ms)
        return result.applied

    def apply_map_runtime_snapshot(self, snapshot: MapRuntimeSnapshot) -> bool:
        self.current_map_snapshot = snapshot
        self.last_map_sequence = max(self.last_map_sequence, snapshot.sequence)
        current_payload = getattr(self.panel_controller, "current_payload", None)
        if current_payload is None:
            view_state = self.panel_controller.sync_runtime_payload(
                self.state_controller.current_payload,
                default_tab=self.state_controller.state_model.default_panel_tab(
                    self.state_controller.current_state
                ),
                map_snapshot=snapshot,
            )
        else:
            view_state = self.panel_controller.sync_map_snapshot(snapshot)
        self.layout_shell.set_view(
            view_state,
            self.panel_controller.tab_specs,
            map_snapshot=snapshot,
        )
        return True

    def select_panel_tab(self, tab_key: str) -> None:
        view_state = self.panel_controller.activate_tab(tab_key)
        self.layout_shell.set_view(
            view_state,
            self.panel_controller.tab_specs,
            map_snapshot=getattr(self, "current_map_snapshot", None),
        )

    def trigger_panel_action(self, action_key: str) -> None:
        if (
            action_key == "confirm_understanding"
            and self.state_controller.current_state == FaceState.ERROR_OR_HUMAN_ASSISTANCE
        ):
            # Keep touch as a short acknowledgment path: in help/error only, this requests
            # a clean handoff reset back to idle without exposing broader robot controls.
            if self.request_state(FaceState.IDLE):
                return
        view_state = self.panel_controller.trigger_action(action_key)
        self.layout_shell.set_view(
            view_state,
            self.panel_controller.tab_specs,
            map_snapshot=getattr(self, "current_map_snapshot", None),
        )

    def step_state(self, step: int) -> None:
        current_index = self.state_order.index(self.state_controller.current_state)
        target_index = (current_index + step) % len(self.state_order)
        self.jump_to_state(target_index)

    def jump_to_state(self, index: int) -> None:
        target = self.state_order[index]
        warning_signal_sent = target == FaceState.ERROR_OR_HUMAN_ASSISTANCE
        if not self.request_state(target, warning_signal_sent=warning_signal_sent):
            print(
                _console_safe(
                    f"Blocked transition: {self.state_controller.current_state.value} -> {target.value}"
                ),
                file=sys.stderr,
            )

    def shutdown(self, *_args) -> None:
        self.auto_cycle_enabled = False
        if self.root.winfo_exists():
            self.face_renderer.stop()
            self.root.quit()
            self.root.destroy()

    def review_info(self) -> None:
        self.trigger_panel_action("view_info")

    def review_map(self) -> None:
        self.trigger_panel_action("view_map")

    def confirm_understanding(self) -> None:
        self.trigger_panel_action("confirm_understanding")

    def _sync_panel_view(self, payload, default_tab: str) -> None:
        current_map_snapshot = getattr(self, "current_map_snapshot", None)
        view_state = self.panel_controller.sync_runtime_payload(
            payload,
            default_tab=default_tab,
            map_snapshot=current_map_snapshot,
        )
        self.layout_shell.set_view(
            view_state,
            self.panel_controller.tab_specs,
            map_snapshot=current_map_snapshot,
        )

    def poll_runtime_bridge(self) -> None:
        store = (
            getattr(self, "runtime_snapshot_store", None)
            if getattr(self, "enable_runtime_bridge_polling", False)
            else None
        )
        root = getattr(self, "root", None)
        if store is not None:
            snapshot = store.read_if_newer(getattr(self, "last_runtime_sequence", 0))
            if snapshot is not None and not self.apply_runtime_snapshot(snapshot):
                print(
                    _console_safe(
                        f"[LIVE SNAPSHOT BLOCKED] {self.state_controller.current_state.value} -> "
                        f"{snapshot.state.value} via {snapshot.trigger}"
                    ),
                    file=sys.stderr,
                )
        map_store = (
            getattr(self, "map_snapshot_store", None)
            if getattr(self, "enable_map_bridge_polling", False)
            else None
        )
        if map_store is not None:
            map_snapshot = map_store.read_if_newer(getattr(self, "last_map_sequence", 0))
            if map_snapshot is not None:
                self.apply_map_runtime_snapshot(map_snapshot)
        if (
            root is not None
            and root.winfo_exists()
            and (
                getattr(self, "enable_runtime_bridge_polling", False)
                or getattr(self, "enable_map_bridge_polling", False)
            )
        ):
            root.after(200, self.poll_runtime_bridge)

    def _print_dev_controls(self) -> None:
        if self.auto_cycle_enabled:
            print(_console_safe("Runtime robot dang o che do tu chay trinh dien."))
            print(_console_safe(f"  Tu chuyen trang thai sau moi {AUTO_CYCLE_INTERVAL_MS // 1000}s"))
            print(_console_safe("  Khuon mat duoc phong to o giua man hinh va khong con bang thong tin ben duoi."))
            return
        print(_console_safe("Điều khiển demo nội bộ cho runtime robot:"))
        print(_console_safe("  Left/Right : duyệt qua các trạng thái khuôn mặt"))
        print(_console_safe("  1..9, 0, - : nhảy trực tiếp đến các trạng thái 1..11"))
        print(
            _console_safe(
                "  i / m / Enter / h : xem thông tin / xem bản đồ / xác nhận đã hiểu / mở tab hỗ trợ"
            )
        )
        for index, state in enumerate(self.state_order, start=1):
            key = "-" if index == 11 else ("0" if index == 10 else str(index))
            print(f"  {key}: {state.value}")

    def _advance_auto_cycle(self) -> None:
        if not self.auto_cycle_enabled or not self.root.winfo_exists():
            return
        self.auto_cycle_index = (self.auto_cycle_index + 1) % len(AUTO_CYCLE_SEQUENCE)
        target = AUTO_CYCLE_SEQUENCE[self.auto_cycle_index]
        warning_signal_sent = target == FaceState.ERROR_OR_HUMAN_ASSISTANCE
        if not self.request_state(target, warning_signal_sent=warning_signal_sent):
            fallback_targets = self.state_controller.state_model.allowed_targets(
                self.state_controller.current_state
            )
            if fallback_targets:
                fallback = fallback_targets[0]
                self.request_state(
                    fallback,
                    warning_signal_sent=fallback == FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                )
                if fallback in AUTO_CYCLE_SEQUENCE:
                    self.auto_cycle_index = AUTO_CYCLE_SEQUENCE.index(fallback)
        self.root.after(AUTO_CYCLE_INTERVAL_MS, self._advance_auto_cycle)


def _console_safe(text: str) -> str:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
    try:
        text.encode(sys.stdout.encoding or "utf-8")
    except UnicodeEncodeError:
        normalized = unicodedata.normalize("NFKD", text)
        return normalized.encode("ascii", "ignore").decode("ascii")
    return text


def main() -> None:
    shell = FaceRuntimeShell()

    signal.signal(signal.SIGINT, shell.shutdown)
    signal.signal(signal.SIGTERM, shell.shutdown)

    shell.run()


if __name__ == "__main__":
    main()
