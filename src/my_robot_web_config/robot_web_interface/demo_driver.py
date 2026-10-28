#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import signal
import sys
import unicodedata
from dataclasses import dataclass

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from app1 import FaceRuntimeShell
    from face_states import FaceState
else:
    from .app1 import FaceRuntimeShell
    from .face_states import FaceState


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


@dataclass(frozen=True, slots=True)
class DemoStep:
    state: FaceState | None
    hold_ms: int
    review_focus: str
    panel_action: str | None = None


DEMO_SEQUENCE: tuple[DemoStep, ...] = (
    DemoStep(
        FaceState.IDLE,
        1800,
        "Màn hình mở ở Trang chờ, khuôn mặt vẫn là trung tâm và panel chỉ đóng vai trò bổ trợ.",
    ),
    DemoStep(
        FaceState.CALLING_PATIENT,
        2200,
        "Auto-tab phải chuyển sang Thông tin lượt khi robot bắt đầu gọi lượt bệnh nhân.",
    ),
    DemoStep(
        None,
        1500,
        "Bệnh nhân chạm để xem lại bản đồ mà không làm hỏng hành vi auto-tab.",
        panel_action="view_map",
    ),
    DemoStep(
        None,
        1500,
        "Bệnh nhân có thể quay lại Thông tin lượt chỉ bằng một thao tác chạm ngắn.",
        panel_action="view_info",
    ),
    DemoStep(
        FaceState.CONFIRMING,
        1800,
        "Robot xác nhận lại hướng dẫn trước khi chuyển sang dẫn đường.",
    ),
    DemoStep(
        None,
        1400,
        "Nút Đã hiểu chỉ là một xác nhận ngắn, không mở ra form hay điều khiển khác.",
        panel_action="confirm_understanding",
    ),
    DemoStep(
        FaceState.NAVIGATING,
        2400,
        "Khi robot dẫn đường, tab mặc định phải ưu tiên Bản đồ dẫn đường.",
    ),
    DemoStep(
        FaceState.ERROR_OR_HUMAN_ASSISTANCE,
        2600,
        "Khi cần hỗ trợ, tab mặc định phải chuyển sang Cần hỗ trợ với copy an toàn và rõ ràng.",
    ),
)


class PhaseTwoDemoDriver:
    def __init__(self, *, auto_exit: bool, final_hold_ms: int) -> None:
        self.shell = FaceRuntimeShell(
            enable_runtime_bridge_polling=False,
            enable_map_bridge_polling=False,
        )
        self.auto_exit = auto_exit
        self.final_hold_ms = final_hold_ms
        self.steps = DEMO_SEQUENCE
        self.current_index = 0
        self.completed = False

    def run(self) -> None:
        self._print_review_instructions()
        self.shell.root.after(300, self._run_next_step)
        self.shell.run()

    def shutdown(self, *_args) -> None:
        self.shell.shutdown()

    def _run_next_step(self) -> None:
        if self.current_index >= len(self.steps):
            self._finish_demo()
            return

        step = self.steps[self.current_index]
        self.current_index += 1

        if step.state is not None:
            warning_signal_sent = step.state == FaceState.ERROR_OR_HUMAN_ASSISTANCE
            if not self.shell.request_state(step.state, warning_signal_sent=warning_signal_sent):
                print(
                    _console_safe(
                        f"[DEMO BLOCKED] không thể vào trạng thái {step.state.value} từ "
                        f"{self.shell.state_controller.current_state.value}"
                    ),
                    file=sys.stderr,
                )
                self.shutdown()
                return
        if step.panel_action == "view_map":
            self.shell.review_map()
        elif step.panel_action == "view_info":
            self.shell.review_info()
        elif step.panel_action == "confirm_understanding":
            self.shell.confirm_understanding()

        print(
            _console_safe(
                f"[DEMO] {self.current_index:02d}/{len(self.steps)} "
                f"{step.state.value if step.state is not None else step.panel_action} :: {step.review_focus}"
            )
        )
        self.shell.root.after(step.hold_ms, self._run_next_step)

    def _finish_demo(self) -> None:
        if self.completed:
            return
        self.completed = True
        print(_console_safe("[DEMO] hoàn tất"))
        print(_console_safe("[DEMO] các điểm cần xác nhận:"))
        print(_console_safe("  - Face vẫn chiếm vai trò thị giác chính dù panel và bản đồ đã xuất hiện"))
        print(
            _console_safe(
                "  - Auto-tab tự đổi đúng giữa Trang chờ, Thông tin lượt, Bản đồ dẫn đường và Cần hỗ trợ"
            )
        )
        print(_console_safe("  - Chạm chỉ dùng để xem lại thông tin, xem lại bản đồ hoặc xác nhận đã hiểu"))
        print(
            _console_safe(
                "  - Copy hiển thị chỉ dùng mã lượt, STT, phòng khám và hướng dẫn ngắn, không dùng tên bệnh nhân"
            )
        )
        if self.auto_exit:
            self.shell.root.after(self.final_hold_ms, self.shutdown)

    def _print_review_instructions(self) -> None:
        print(_console_safe("Demo Phase 2 cho robot-first runtime"))
        print(
            _console_safe(
                "Luồng này vẫn độc lập: chưa cần web, chưa cần Nav2 live, chưa cần binding giọng nói thật."
            )
        )
        print(
            _console_safe(
                "Reviewer nên nhìn face trước, sau đó mới xác nhận panel/tab/map có hỗ trợ đúng và không lấn át khuôn mặt."
            )
        )
        print(_console_safe("Chuỗi demo đi qua các điểm chính:"))
        print(_console_safe("  idle -> calling_patient -> chạm xem bản đồ -> chạm xem thông tin"))
        print(_console_safe("  -> confirming -> xác nhận đã hiểu -> navigating -> error_or_human_assistance"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo xác định trước cho Phase 2 robot-first runtime của RobotHospital.",
        add_help=False,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Hiển thị trợ giúp rồi thoát.",
    )
    parser.add_argument(
        "--auto-exit",
        action="store_true",
        help="Tự động đóng cửa sổ sau khi demo kết thúc (mặc định là GIỮ LẠI giao diện).",
    )
    parser.add_argument(
        "--final-hold-ms",
        type=int,
        default=1400,
        help="Thời gian giữ trạng thái cuối trước khi tự đóng cửa sổ (chỉ kích hoạt nếu dùng --auto-exit).",
    )
    args = parser.parse_args()
    if args.help:
        print(_console_safe(parser.format_help()))
        raise SystemExit(0)
    return args


def main() -> None:
    args = _parse_args()
    driver = PhaseTwoDemoDriver(
        auto_exit=args.auto_exit,
        final_hold_ms=max(0, args.final_hold_ms),
    )
    signal.signal(signal.SIGINT, driver.shutdown)
    signal.signal(signal.SIGTERM, driver.shutdown)
    driver.run()


if __name__ == "__main__":
    main()