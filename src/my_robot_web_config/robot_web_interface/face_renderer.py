from __future__ import annotations

import math
import random
import time
from tkinter import TclError

if __package__ in (None, ""):
    from face_states import FaceState, EyeFocus, MouthMode, STATE_PROFILES
    from payloads import FaceRenderPayload, sample_payload_for_state
    import visual_tokens as vt
else:
    from .face_states import FaceState, EyeFocus, MouthMode, STATE_PROFILES
    from .payloads import FaceRenderPayload, sample_payload_for_state
    from . import visual_tokens as vt


STAGE_CAPTIONS: dict[FaceState, str] = {
    FaceState.IDLE: "Nhịp chờ nhẹ, giữ giao tiếp tối giản",
    FaceState.ATTENTION: "Tập trung chú ý vào người đứng gần",
    FaceState.GREETING: "Mở lời chào với sắc thái thân thiện",
    FaceState.LISTENING: "Giảm chuyển động để ưu tiên nghe",
    FaceState.SPEAKING: "Nhịp nói rõ ràng, dễ theo dõi",
    FaceState.CALLING_PATIENT: "Ưu tiên thu hút chú ý cho lượt khám",
    FaceState.CONFIRMING: "Xác nhận nhanh trước khi dẫn đường",
    FaceState.NAVIGATING: "Ổn định, định hướng và dẫn lối",
    FaceState.ARRIVED: "Kết thúc hành trình với cảm giác hoàn tất",
    FaceState.WAITING_RETRY: "Nhắc lại nhưng vẫn giữ bình tĩnh",
    FaceState.ERROR_OR_HUMAN_ASSISTANCE: "Nghiêm túc, an toàn, ưu tiên hỗ trợ người thật",
}


STATE_LABELS: dict[FaceState, str] = {
    FaceState.IDLE: "TRANG THÁI CHỜ",
    FaceState.ATTENTION: "ĐANG CHÚ Ý",
    FaceState.GREETING: "ĐANG CHÀO",
    FaceState.LISTENING: "ĐANG LẮNG NGHE",
    FaceState.SPEAKING: "ĐANG NÓI",
    FaceState.CALLING_PATIENT: "ĐANG GỌI LƯỢT",
    FaceState.CONFIRMING: "ĐANG XÁC NHẬN",
    FaceState.NAVIGATING: "ĐANG DẪN ĐƯỜNG",
    FaceState.ARRIVED: "ĐÃ ĐẾN NƠI",
    FaceState.WAITING_RETRY: "CHỜ THỬ LẠI",
    FaceState.ERROR_OR_HUMAN_ASSISTANCE: "CẦN HỖ TRỢ",
}

class FaceRenderer:
    def __init__(self, canvas) -> None:
        self.canvas = canvas
        self.running = False
        self.after_id = None
        self.start_ts = time.monotonic()
        self.random = random.Random()
        self.blink_progress = 0.0
        self.blink_started_at = 0.0
        self.blink_duration = 0.22
        self.next_blink_at = 1.5
        self.drift_target = [0.0, 0.0]
        self.drift_current = [0.0, 0.0]
        self.next_drift_at = 1.6
        self.current_payload = sample_payload_for_state(FaceState.IDLE)
        self.from_payload = self.current_payload
        self.transition_started_at = self.start_ts
        self.transition_duration = 0.0
        self.state_label_text = STATE_LABELS[self.current_payload.state]

        self._create_stage()
        self._create_face_parts()
        self._render_frame(self.start_ts)

    def start_idle_animation(self) -> None:
        self.running = True
        self._schedule_next_frame()

    def stop(self) -> None:
        self.running = False
        if self.after_id is not None:
            try:
                self.canvas.after_cancel(self.after_id)
            except TclError:
                pass
            self.after_id = None

    def set_payload(self, payload: FaceRenderPayload, transition_ms: int = 0) -> None:
        now = time.monotonic()
        self.from_payload = self.current_payload
        self.current_payload = payload
        self.transition_started_at = now
        self.transition_duration = max(0.0, transition_ms / 1000.0)
        self.state_label_text = STATE_LABELS[payload.state]

    def _schedule_next_frame(self) -> None:
        if not self.running:
            return
        self.after_id = self.canvas.after(vt.FRAME_MS, self._tick)

    def _tick(self) -> None:
        if not self.running or not self.canvas.winfo_exists():
            return
        now = time.monotonic()
        self._update_idle_motion(now)
        try:
            self._render_frame(now)
        except TclError:
            self.running = False
            return
        self._schedule_next_frame()

    def _create_stage(self) -> None:
        x1, y1, x2, y2 = vt.FACE_STAGE_BOUNDS
        hx1, hy1, hx2, hy2 = vt.FACE_STAGE_HEADER_BOUNDS
        sx1, sy1, sx2, sy2 = vt.FACE_STATUS_BOUNDS

        self.stage_shadow = self.canvas.create_rectangle(
            x1 + 12,
            y1 + 18,
            x2 + 12,
            y2 + 22,
            fill="#02050A",
            outline="",
        )
        self.stage_frame = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=vt.SURFACE_GLOW,
            outline=vt.FACE_OUTLINE,
            width=3,
        )
        self.stage_inner = self.canvas.create_rectangle(
            x1 + 18,
            y1 + 18,
            x2 - 18,
            y2 - 18,
            fill=vt.FACE_FILL,
            outline="#11233A",
            width=2,
        )
        self.header_strip = self.canvas.create_rectangle(
            hx1,
            hy1,
            hx2,
            hy2,
            fill="#081521",
            outline="#15324B",
            width=2,
            state="hidden",
        )
        self.header_title = self.canvas.create_text(
            hx1 + 16,
            hy1 + 10,
            anchor="nw",
            text="",
            fill=vt.TEXT_MUTED,
            font=("Helvetica", 10, "bold"),
            state="hidden",
        )
        self.header_subtitle = self.canvas.create_text(
            hx1 + 16,
            hy1 + 24,
            anchor="nw",
            text="",
            fill=vt.TEXT_PRIMARY,
            font=("Helvetica", 13, "bold"),
            state="hidden",
        )
        self.left_orbit = self.canvas.create_arc(
            x1 + 38,
            y1 + 100,
            x1 + 214,
            y2 - 78,
            start=104,
            extent=160,
            style="arc",
            outline="#17304A",
            width=2,
            state="hidden",
        )
        self.right_orbit = self.canvas.create_arc(
            x2 - 214,
            y1 + 100,
            x2 - 38,
            y2 - 78,
            start=-84,
            extent=160,
            style="arc",
            outline="#17304A",
            width=2,
            state="hidden",
        )
        self.center_axis = self.canvas.create_line(
            (x1 + x2) / 2,
            y1 + 118,
            (x1 + x2) / 2,
            y2 - 108,
            fill="#13314C",
            width=1,
            dash=(6, 9),
            state="hidden",
        )
        self.state_chip = self.canvas.create_rectangle(
            sx1,
            sy1,
            sx2,
            sy2,
            fill="#091421",
            outline=vt.ACCENT_SOFT,
            width=2,
            state="hidden",
        )
        self.state_chip_left = self.canvas.create_rectangle(
            sx1,
            sy1,
            sx1 + 16,
            sy2,
            fill=vt.ACCENT_SOFT,
            outline="",
            state="hidden",
        )
        self.state_chip_label = self.canvas.create_text(
            sx1 + 30,
            sy1 + 12,
            anchor="nw",
            text="TRANG THÁI CHỜ",
            fill=vt.TEXT_PRIMARY,
            font=("Helvetica", 11, "bold"),
            state="hidden",
        )
        self.state_chip_hint = self.canvas.create_text(
            sx1 + 30,
            sy1 + 34,
            anchor="nw",
            width=(sx2 - sx1) - 60,
            text=_chip_copy(self.current_payload),
            fill=vt.TEXT_SOFT,
            font=("Helvetica", 10),
            state="hidden",
        )
        self.left_beacon = self.canvas.create_rectangle(
            x1 + 26,
            176,
            x1 + 40,
            400,
            fill=vt.ACCENT_SOFT,
            outline="",
            state="hidden",
        )
        self.right_beacon = self.canvas.create_rectangle(
            x2 - 40,
            176,
            x2 - 26,
            400,
            fill=vt.ACCENT_SOFT,
            outline="",
            state="hidden",
        )
    def _create_face_parts(self) -> None:
        x1, y1, x2, y2 = vt.FACE_BOUNDS
        self.face_shadow = self.canvas.create_oval(
            x1 - 16,
            y1 + 22,
            x2 + 16,
            y2 + 28,
            fill="#02060D",
            outline="",
        )
        self.face_base = self.canvas.create_oval(
            x1,
            y1,
            x2,
            y2,
            fill=vt.FACE_FILL,
            outline=vt.FACE_OUTLINE,
            width=6,
        )
        self.face_aura = self.canvas.create_oval(
            x1 - 8,
            y1 - 8,
            x2 + 8,
            y2 + 8,
            outline=vt.ACCENT_SOFT,
            width=2,
        )
        self.face_rim = self.canvas.create_oval(
            x1 + 18,
            y1 + 18,
            x2 - 18,
            y2 - 20,
            outline="#132A42",
            width=2,
        )
        self.left_eye = self._create_eye(vt.LEFT_EYE_CENTER)
        self.right_eye = self._create_eye(vt.RIGHT_EYE_CENTER)
        self.nose = self.canvas.create_polygon(
            0,
            0,
            0,
            0,
            0,
            0,
            fill=vt.NOSE_FILL,
            outline="",
            smooth=True,
        )
        self.mouth_line = self.canvas.create_line(
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            fill=vt.MOUTH_STROKE,
            width=5,
            smooth=True,
            splinesteps=24,
            capstyle="round",
        )
        self.mouth_inner = self.canvas.create_oval(
            0,
            0,
            0,
            0,
            fill=vt.MOUTH_FILL,
            outline="",
        )
        self.face_item_ids = (
            self.face_shadow,
            self.face_base,
            self.face_aura,
            self.face_rim,
            self.left_eye["shadow"],
            self.left_eye["halo"],
            self.left_eye["shape"],
            self.left_eye["core"],
            self.left_eye["highlight"],
            self.right_eye["shadow"],
            self.right_eye["halo"],
            self.right_eye["shape"],
            self.right_eye["core"],
            self.right_eye["highlight"],
            self.nose,
            self.mouth_line,
            self.mouth_inner,
        )

    def _set_face_items_visible(self, visible: bool) -> None:
        state = "normal" if visible else "hidden"
        for item_id in self.face_item_ids:
            self.canvas.itemconfigure(item_id, state=state)

    def _hide_stage_chrome(self) -> None:
        for item_id in (
            self.header_strip,
            self.header_title,
            self.header_subtitle,
            self.left_orbit,
            self.right_orbit,
            self.center_axis,
            self.state_chip,
            self.state_chip_left,
            self.state_chip_label,
            self.state_chip_hint,
            self.left_beacon,
            self.right_beacon,
        ):
            self.canvas.itemconfigure(item_id, state="hidden")

    def _create_eye(self, center: tuple[float, float]) -> dict[str, object]:
        cx, cy = center
        eye_w, eye_h = vt.EYE_SIZE
        half_w = eye_w / 2
        half_h = eye_h / 2
        shadow = self.canvas.create_polygon(
            *(
                _ellipse_polygon(
                    cx=cx,
                    cy=cy + 8,
                    radius_x=half_w,
                    radius_y=half_h,
                )
            ),
            fill="#03111A",
            outline="",
            smooth=True,
        )
        halo = self.canvas.create_polygon(
            *(
                _ellipse_polygon(
                    cx=cx,
                    cy=cy,
                    radius_x=half_w * 1.12,
                    radius_y=half_h * 1.08,
                )
            ),
            fill="#0B2433",
            outline="",
            smooth=True,
        )
        shape = self.canvas.create_polygon(
            *(
                _ellipse_polygon(
                    cx=cx,
                    cy=cy,
                    radius_x=half_w,
                    radius_y=half_h,
                )
            ),
            fill=vt.ACCENT,
            outline="",
            smooth=True,
        )
        core = self.canvas.create_polygon(
            *(
                _ellipse_polygon(
                    cx=cx,
                    cy=cy,
                    radius_x=max(vt.IRIS_SIZE * 0.36, half_w * 0.5),
                    radius_y=max(vt.IRIS_SIZE * 0.4, half_h * 0.56),
                )
            ),
            fill=vt.ACCENT_WARM,
            outline="",
            smooth=True,
        )
        highlight = self.canvas.create_oval(
            cx - (vt.PUPIL_SIZE * 0.58),
            cy - (vt.PUPIL_SIZE * 0.76),
            cx - (vt.PUPIL_SIZE * 0.08),
            cy - (vt.PUPIL_SIZE * 0.18),
            fill=vt.TEXT_PRIMARY,
            outline="",
        )
        return {
            "center": center,
            "shadow": shadow,
            "halo": halo,
            "shape": shape,
            "core": core,
            "highlight": highlight,
        }

    def _update_idle_motion(self, now: float) -> None:
        elapsed = now - self.start_ts
        blink_just_started = False
        state_name = self.current_payload.state

        if elapsed >= self.next_blink_at and self.blink_progress == 0.0:
            self.blink_started_at = elapsed
            self.blink_progress = 0.001
            blink_just_started = True

        if self.blink_progress > 0.0 and not blink_just_started:
            blink_elapsed = elapsed - self.blink_started_at
            if blink_elapsed >= self.blink_duration:
                self.blink_progress = 0.0
                blink_delay = self.random.uniform(2.8, 4.9)
                if state_name in (
                    FaceState.SPEAKING,
                    FaceState.CALLING_PATIENT,
                    FaceState.NAVIGATING,
                ):
                    blink_delay += 0.8
                self.next_blink_at = elapsed + blink_delay
            else:
                phase = blink_elapsed / self.blink_duration
                self.blink_progress = math.sin(phase * math.pi)

        if elapsed >= self.next_drift_at:
            self.drift_target = [
                self.random.uniform(-vt.IDLE_DRIFT_X, vt.IDLE_DRIFT_X),
                self.random.uniform(-vt.IDLE_DRIFT_Y, vt.IDLE_DRIFT_Y),
            ]
            self.next_drift_at = elapsed + self.random.uniform(1.4, 2.4)

        self.drift_current[0] += (self.drift_target[0] - self.drift_current[0]) * 0.038
        self.drift_current[1] += (self.drift_target[1] - self.drift_current[1]) * 0.038

    def _render_frame(self, now: float) -> None:
        self._set_face_items_visible(True)

        elapsed = now - self.start_ts
        from_profile = STATE_PROFILES[self.from_payload.state]
        to_profile = STATE_PROFILES[self.current_payload.state]
        transition_t = _ease_in_out(self._transition_progress(now))

        profile = {
            "eye_open": _lerp(from_profile.eye_open, to_profile.eye_open, transition_t),
            "eye_brightness": _lerp(
                from_profile.eye_brightness,
                to_profile.eye_brightness,
                transition_t,
            ),
            "eye_motion": _lerp(from_profile.eye_motion, to_profile.eye_motion, transition_t),
            "info_emphasis": _lerp(
                from_profile.info_emphasis,
                to_profile.info_emphasis,
                transition_t,
            ),
        }
        style = _state_style(self.current_payload.state, elapsed)
        face_bob = math.sin(elapsed * 1.15) * (vt.IDLE_FACE_BOB * (0.32 + profile["eye_motion"]))
        eye_open_factor = max(0.1, profile["eye_open"] * (1.0 - (self.blink_progress * 0.94)))

        x1, y1, x2, y2 = vt.FACE_BOUNDS
        aura_color = style["aura_color"]
        aura_width = style["aura_width"] + (profile["eye_brightness"] * 1.8)
        frame_fill = _mix_color(vt.FACE_FILL, style["panel_tint"], style["panel_mix"])
        outer_color = _mix_color(vt.ACCENT_SOFT, style["accent_color"], profile["eye_brightness"])

        self.canvas.coords(
            self.face_shadow,
            x1 - 16,
            y1 + 22 + face_bob,
            x2 + 16,
            y2 + 28 + face_bob,
        )
        self.canvas.coords(
            self.face_base,
            x1,
            y1 + face_bob,
            x2,
            y2 + face_bob,
        )
        self.canvas.coords(
            self.face_aura,
            x1 - 8,
            y1 - 8 + face_bob,
            x2 + 8,
            y2 + 8 + face_bob,
        )
        self.canvas.coords(
            self.face_rim,
            x1 + 18,
            y1 + 18 + face_bob,
            x2 - 18,
            y2 - 20 + face_bob,
        )
        self.canvas.itemconfigure(self.face_base, fill=frame_fill)
        self.canvas.itemconfigure(self.face_aura, outline=aura_color, width=aura_width)
        self.canvas.itemconfigure(self.face_rim, outline=outer_color)
        self.canvas.itemconfigure(
            self.header_strip,
            fill=_mix_color("#081521", str(style["panel_tint"]), 0.72),
            outline=_mix_color("#15324B", str(style["accent_color"]), 0.34),
        )
        self._render_state_chip(style, float(profile["info_emphasis"]))
        self._render_stage_motif(self.current_payload.state, style, elapsed, face_bob)
        self._render_beacons(style, elapsed)

        self._render_eye(
            self.left_eye,
            eye_open_factor=eye_open_factor,
            face_bob=face_bob,
            eye_brightness=profile["eye_brightness"],
            eye_motion=profile["eye_motion"],
            eye_focus=to_profile.eye_focus,
            elapsed=elapsed,
            style=style,
            eye_side=-1,
        )
        self._render_eye(
            self.right_eye,
            eye_open_factor=eye_open_factor,
            face_bob=face_bob,
            eye_brightness=profile["eye_brightness"],
            eye_motion=profile["eye_motion"],
            eye_focus=to_profile.eye_focus,
            elapsed=elapsed,
            style=style,
            eye_side=1,
        )

        self._render_nose(face_bob, elapsed, style)
        self._render_mouth(face_bob, elapsed, style, to_profile.mouth_mode)

    def _render_beacons(self, style: dict[str, float | str], elapsed: float) -> None:
        x1, y1, x2, y2 = vt.FACE_STAGE_BOUNDS
        pulse = 0.65 + ((math.sin(elapsed * float(style["beacon_speed"])) + 1.0) * 0.18)
        base_height = float(style["beacon_height"]) * pulse
        center_y = (y1 + y2) / 2
        top = center_y - (base_height / 2)
        bottom = center_y + (base_height / 2)
        beacon_fill = _mix_color("#102138", str(style["accent_color"]), float(style["beacon_mix"]))
        self.canvas.coords(self.left_beacon, x1 + 26, top, x1 + 40, bottom)
        self.canvas.coords(self.right_beacon, x2 - 40, top, x2 - 26, bottom)
        state = "normal" if float(style["beacon_mix"]) >= 0.22 else "hidden"
        self.canvas.itemconfigure(self.left_beacon, fill=beacon_fill, state=state)
        self.canvas.itemconfigure(self.right_beacon, fill=beacon_fill, state=state)

    def _render_stage_motif(
        self,
        state: FaceState,
        style: dict[str, float | str],
        elapsed: float,
        face_bob: float,
    ) -> None:
        x1, y1, x2, y2 = vt.FACE_STAGE_BOUNDS
        pulse = 1.0 + (math.sin(elapsed * 2.2) * 0.08)
        accent = _mix_color("#17304A", str(style["accent_color"]), float(style["beacon_mix"]))
        orbit_width = 2.0 + (float(style["beacon_mix"]) * 2.4)
        extent = 150
        left_start = 104
        right_start = -84
        axis_dx = 0.0
        axis_bottom_dx = 0.0
        axis_color = _mix_color("#13314C", str(style["accent_color"]), 0.22)
        dash = (6, 9)

        if state in (FaceState.ATTENTION, FaceState.CALLING_PATIENT):
            extent = 212
            orbit_width += 0.8
            axis_color = _mix_color("#13314C", str(style["accent_color"]), 0.4)
        elif state in (FaceState.GREETING, FaceState.CONFIRMING, FaceState.ARRIVED):
            extent = 170
            left_start = 120
            right_start = -100
        elif state == FaceState.NAVIGATING:
            extent = 118
            left_start = 152
            right_start = -18
            orbit_width += 1.4
            axis_dx = 28.0
            axis_bottom_dx = -34.0
            axis_color = _mix_color("#13314C", str(style["accent_color"]), 0.52)
            dash = ()
        elif state == FaceState.WAITING_RETRY:
            extent = 142
            left_start = 98
            right_start = -72
            axis_dx = -6.0
        elif state == FaceState.ERROR_OR_HUMAN_ASSISTANCE:
            extent = 278
            orbit_width += 2.6
            axis_color = _mix_color("#182F41", str(style["accent_color"]), 0.58)

        orbit_top = y1 + 110 + face_bob
        orbit_bottom = y2 - 86 + face_bob
        self.canvas.coords(
            self.left_orbit,
            x1 + 38,
            orbit_top,
            x1 + 214,
            orbit_bottom,
        )
        self.canvas.coords(
            self.right_orbit,
            x2 - 214,
            orbit_top,
            x2 - 38,
            orbit_bottom,
        )
        self.canvas.itemconfigure(
            self.left_orbit,
            start=left_start,
            extent=extent * pulse,
            outline=accent,
            width=orbit_width,
            state="normal" if float(style["motif_mix"]) >= 0.12 else "hidden",
        )
        self.canvas.itemconfigure(
            self.right_orbit,
            start=right_start,
            extent=extent * pulse,
            outline=accent,
            width=orbit_width,
            state="normal" if float(style["motif_mix"]) >= 0.12 else "hidden",
        )
        center_x = (x1 + x2) / 2
        self.canvas.coords(
            self.center_axis,
            center_x + axis_dx,
            y1 + 130,
            center_x + axis_bottom_dx,
            y2 - 118,
        )
        self.canvas.itemconfigure(
            self.center_axis,
            fill=axis_color,
            dash=dash,
            width=1 if dash else 2,
            state="normal" if float(style["motif_mix"]) >= 0.12 else "hidden",
        )

    def _render_state_chip(self, style: dict[str, float | str], info_emphasis: float) -> None:
        for item_id in (
            self.state_chip,
            self.state_chip_left,
            self.state_chip_label,
            self.state_chip_hint,
        ):
            self.canvas.itemconfigure(item_id, state="hidden")

    def _render_eye(
        self,
        eye: dict[str, object],
        *,
        eye_open_factor: float,
        face_bob: float,
        eye_brightness: float,
        eye_motion: float,
        eye_focus: EyeFocus,
        elapsed: float,
        style: dict[str, float | str],
        eye_side: int,
    ) -> None:
        cx, cy = eye["center"]
        half_w = (vt.EYE_SIZE[0] / 2) * float(style["eye_width"])
        base_half_h = (vt.EYE_SIZE[1] / 2) * float(style["eye_height"])
        asymmetry = float(style["asymmetry"]) * eye_side
        half_h = max(14.0, base_half_h * eye_open_factor * (1.0 + asymmetry))

        focus_x, focus_y = self._focus_offset(eye_focus, elapsed)
        eye_x = (
            self.drift_current[0] + focus_x + (float(style["iris_bias_x"]) * eye_side)
        ) * (0.2 + eye_motion * 2.4)
        eye_y = (
            (self.drift_current[1] * eye_open_factor)
            + focus_y
            + float(style["iris_bias_y"])
        ) * (0.18 + eye_motion * 2.2)
        center_x = cx + eye_x
        center_y = cy + eye_y + face_bob
        eye_fill = _mix_color(vt.ACCENT, str(style["accent_color"]), min(1.0, eye_brightness * 0.9))
        shadow_fill = _mix_color("#03111A", "#0A3245", min(1.0, eye_brightness * 0.35))
        halo_fill = _mix_color("#082130", str(style["accent_color"]), min(1.0, 0.28 + (eye_brightness * 0.4)))
        eye_rotation = float(style["eye_rotation"]) * eye_side
        eye_points = _ellipse_polygon(
            cx=center_x,
            cy=center_y,
            radius_x=half_w,
            radius_y=half_h,
            rotation_deg=eye_rotation,
        )
        halo_points = _ellipse_polygon(
            cx=center_x,
            cy=center_y,
            radius_x=half_w * 1.12,
            radius_y=max(18.0, half_h * 1.1),
            rotation_deg=eye_rotation,
        )
        shadow_points = _ellipse_polygon(
            cx=center_x + 8,
            cy=center_y + 8,
            radius_x=half_w,
            radius_y=half_h,
            rotation_deg=eye_rotation,
        )
        core_points = _ellipse_polygon(
            cx=center_x + (float(style["iris_bias_x"]) * eye_side * 0.08),
            cy=center_y + (float(style["iris_bias_y"]) * 0.1),
            radius_x=max(vt.IRIS_SIZE * 0.36, half_w * 0.5),
            radius_y=max(vt.IRIS_SIZE * 0.4, half_h * 0.58),
            rotation_deg=eye_rotation,
        )
        highlight_width = max(8.0, vt.PUPIL_SIZE * 0.46)
        highlight_height = max(6.0, vt.PUPIL_SIZE * 0.3)
        self.canvas.coords(eye["shadow"], *shadow_points)
        self.canvas.coords(eye["halo"], *halo_points)
        self.canvas.coords(eye["shape"], *eye_points)
        self.canvas.coords(eye["core"], *core_points)
        self.canvas.coords(
            eye["highlight"],
            center_x - (half_w * 0.34),
            center_y - (half_h * 0.48),
            center_x - (half_w * 0.34) + highlight_width,
            center_y - (half_h * 0.48) + highlight_height,
        )
        self.canvas.itemconfigure(eye["shadow"], fill=shadow_fill)
        self.canvas.itemconfigure(eye["halo"], fill=halo_fill)
        self.canvas.itemconfigure(eye["shape"], fill=eye_fill)
        self.canvas.itemconfigure(
            eye["core"],
            fill=_mix_color(vt.ACCENT_SUCCESS, str(style["accent_color"]), 0.38),
        )
        self.canvas.itemconfigure(
            eye["highlight"],
            fill=_mix_color(vt.TEXT_PRIMARY, str(style["accent_color"]), 0.12),
        )

    def _render_nose(self, face_bob: float, elapsed: float, style: dict[str, float | str]) -> None:
        cx = vt.MOUTH_CENTER[0]
        cy = 292 + face_bob
        nose_w = vt.NOSE_SIZE[0] * float(style["nose_scale"])
        nose_h = vt.NOSE_SIZE[1] * float(style["nose_scale"])
        pulse = 1.0 + (math.sin(elapsed * 3.2) * float(style["nose_pulse"]))
        self.canvas.coords(
            self.nose,
            cx,
            cy - ((nose_h / 2) * pulse),
            cx - ((nose_w / 2) * pulse),
            cy + ((nose_h / 2) * pulse),
            cx + ((nose_w / 2) * pulse),
            cy + ((nose_h / 2) * pulse),
        )
        self.canvas.itemconfigure(
            self.nose,
            fill=_mix_color(vt.NOSE_FILL, str(style["accent_color"]), float(style["nose_mix"])),
        )

    def _render_mouth(
        self,
        face_bob: float,
        elapsed: float,
        style: dict[str, float | str],
        mouth_mode: MouthMode,
    ) -> None:
        cx, base_y = vt.MOUTH_CENTER
        center_y = base_y + face_bob + float(style["mouth_shift"])
        half_w = (vt.MOUTH_WIDTH / 2) * float(style["mouth_width"])
        line_curve = float(style["mouth_curve"])
        line_depth = 14 * line_curve
        open_factor, talk_bounce = self._mouth_open(mouth_mode, elapsed)
        open_height = max(0.0, (vt.MOUTH_HEIGHT * float(style["mouth_open"])) + (talk_bounce * 10))
        self.canvas.coords(
            self.mouth_line,
            cx - half_w,
            center_y,
            cx - (half_w * 0.38),
            center_y + line_depth,
            cx + (half_w * 0.38),
            center_y + line_depth,
            cx + half_w,
            center_y,
        )
        self.canvas.itemconfigure(
            self.mouth_line,
            fill=_mix_color(vt.MOUTH_STROKE, str(style["accent_color"]), float(style["mouth_mix"])),
            width=4 + (float(style["mouth_open"]) * 2),
        )
        if open_height <= 4:
            self.canvas.itemconfigure(self.mouth_inner, state="hidden")
        else:
            self.canvas.itemconfigure(self.mouth_inner, state="normal")
            self.canvas.coords(
                self.mouth_inner,
                cx - (half_w * 0.55),
                center_y - (open_height / 2),
                cx + (half_w * 0.55),
                center_y + (open_height / 2),
            )
            self.canvas.itemconfigure(
                self.mouth_inner,
                fill=_mix_color(vt.MOUTH_FILL, str(style["accent_color"]), float(style["mouth_mix"]) * 0.4),
            )

    def _mouth_open(self, mouth_mode: MouthMode, elapsed: float) -> tuple[float, float]:
        if mouth_mode == MouthMode.CLOSED:
            return (0.0, 0.0)
        if mouth_mode == MouthMode.SOFT_SPEECH:
            return (0.36, (math.sin(elapsed * 4.0) + 1.0) * 0.12)
        if mouth_mode == MouthMode.CLEAR_SPEECH:
            return (0.54, (math.sin(elapsed * 5.4) + 1.0) * 0.18)
        if mouth_mode == MouthMode.EMPHATIC_SPEECH:
            return (0.78, (math.sin(elapsed * 6.8) + 1.0) * 0.24)
        if mouth_mode == MouthMode.CONFIRM_PULSE:
            return (0.22, (math.sin(elapsed * 3.4) + 1.0) * 0.08)
        if mouth_mode == MouthMode.ARRIVAL_LINE:
            return (0.16, 0.0)
        if mouth_mode == MouthMode.RETRY_PROMPT:
            return (0.18, (math.sin(elapsed * 2.4) + 1.0) * 0.06)
        if mouth_mode == MouthMode.SUPPORT_PROMPT:
            return (0.1, 0.0)
        return (0.0, 0.0)

    def _focus_offset(self, eye_focus: EyeFocus, elapsed: float) -> tuple[float, float]:
        if eye_focus == EyeFocus.GENTLE_SCAN:
            return (math.sin(elapsed * 0.7) * 2.2, math.cos(elapsed * 0.55) * 1.0)
        if eye_focus == EyeFocus.CENTER_LOCK:
            return (0.0, -0.3)
        if eye_focus == EyeFocus.GREETING_LIFT:
            return (math.sin(elapsed * 1.2) * 0.8, -1.9)
        if eye_focus == EyeFocus.LISTEN_LOCK:
            return (0.0, math.sin(elapsed * 1.7) * 0.35 - 0.8)
        if eye_focus == EyeFocus.SPEAK_LOCK:
            return (0.0, -0.5)
        if eye_focus == EyeFocus.PATH_LEAD:
            return (30.0, -1.8)
        if eye_focus == EyeFocus.RELIEF_SOFTEN:
            return (-1.2, -0.7)
        if eye_focus == EyeFocus.HELP_FOCUS:
            return (0.0, 0.6)
        return (0.0, 0.0)

    def _transition_progress(self, now: float) -> float:
        if self.transition_duration <= 0.0:
            return 1.0
        return min(1.0, max(0.0, (now - self.transition_started_at) / self.transition_duration))


def _state_style(state: FaceState, elapsed: float) -> dict[str, float | str]:
    pulse = (math.sin(elapsed * 3.8) + 1.0) / 2.0
    style: dict[str, float | str] = {
        "accent_color": vt.ACCENT,
        "aura_color": vt.ACCENT_SOFT,
        "panel_tint": "#102035",
        "panel_mix": 0.14,
        "aura_width": 3.0,
        "eye_width": 1.0,
        "eye_height": 1.0,
        "eye_start": 0.0,
        "eye_extent": 360.0,
        "eye_rotation": 0.0,
        "brow_lift": 0.0,
        "brow_tilt": 0.0,
        "brow_length": 1.0,
        "iris_bias_x": 0.0,
        "iris_bias_y": 0.0,
        "mouth_width": 1.0,
        "mouth_open": 0.0,
        "mouth_curve": -0.08,
        "mouth_shift": 0.0,
        "mouth_mix": 0.12,
        "nose_scale": 1.0,
        "nose_pulse": 0.0,
        "nose_mix": 0.16,
        "beacon_mix": 0.28,
        "beacon_height": 212.0,
        "beacon_speed": 2.6,
        "motif_mix": 0.24,
        "asymmetry": 0.0,
    }
    if state == FaceState.IDLE:
        return style
    if state == FaceState.ATTENTION:
        style.update(
            eye_width=1.04,
            eye_height=1.24,
            panel_mix=0.24,
            aura_width=4.4,
            beacon_mix=0.42,
            beacon_height=206.0,
            mouth_curve=-0.03,
            nose_scale=1.05,
            motif_mix=0.18,
        )
        return style
    if state == FaceState.GREETING:
        style.update(
            accent_color=vt.ACCENT_SUCCESS,
            aura_color=vt.ACCENT_SUCCESS,
            eye_width=1.0,
            eye_height=1.18,
            eye_rotation=6.0,
            mouth_curve=-0.62,
            mouth_open=0.18,
            mouth_width=0.9,
            mouth_shift=-2.0,
            mouth_mix=0.22,
            nose_pulse=0.05,
            nose_mix=0.26,
            beacon_mix=0.28,
            beacon_height=138.0,
            aura_width=3.4,
            motif_mix=0.16,
        )
        return style
    if state == FaceState.LISTENING:
        style.update(
            eye_width=0.88,
            eye_height=0.92,
            iris_bias_y=-1.0,
            mouth_curve=0.02,
            mouth_width=0.34,
            beacon_height=92.0,
            beacon_mix=0.08,
            aura_width=1.8,
            motif_mix=0.08,
        )
        return style
    if state == FaceState.SPEAKING:
        style.update(
            eye_width=0.78,
            eye_height=1.12,
            eye_rotation=0.0,
            mouth_curve=-0.1,
            mouth_open=0.92,
            mouth_width=0.82,
            mouth_mix=0.48,
            nose_pulse=0.03,
            beacon_height=176.0,
            beacon_mix=0.4,
            aura_width=5.4,
            motif_mix=0.26,
        )
        return style
    if state == FaceState.CALLING_PATIENT:
        style.update(
            accent_color=vt.ACCENT,
            aura_color=vt.ACCENT,
            panel_mix=0.34,
            eye_width=1.02,
            eye_height=1.14,
            eye_rotation=0.0,
            mouth_curve=-0.04,
            mouth_open=0.88,
            mouth_width=1.18,
            mouth_mix=0.58,
            nose_pulse=0.08,
            nose_scale=1.1,
            beacon_mix=0.9,
            beacon_height=256.0 + (pulse * 42.0),
            beacon_speed=5.2,
            aura_width=6.2,
            motif_mix=0.42,
        )
        return style
    if state == FaceState.CONFIRMING:
        style.update(
            accent_color=vt.ACCENT_SUCCESS,
            aura_color=vt.ACCENT_SUCCESS,
            panel_tint="#14333C",
            panel_mix=0.36,
            eye_width=0.8,
            eye_height=1.3,
            eye_rotation=0.0,
            mouth_curve=-0.42,
            mouth_open=0.18,
            mouth_width=0.86,
            mouth_mix=0.26,
            nose_scale=1.04,
            beacon_mix=0.26,
            beacon_height=118.0,
            aura_width=3.8,
            motif_mix=0.18,
        )
        return style
    if state == FaceState.NAVIGATING:
        style.update(
            accent_color=vt.ACCENT,
            aura_color=vt.ACCENT_SOFT,
            panel_tint="#0A1C2C",
            panel_mix=0.18,
            eye_width=0.82,
            eye_height=1.28,
            eye_rotation=0.0,
            iris_bias_x=16.0,
            iris_bias_y=-5.0,
            mouth_curve=0.0,
            mouth_width=0.18,
            mouth_shift=-18.0,
            beacon_mix=0.18,
            beacon_height=84.0,
            aura_width=2.1,
            motif_mix=0.3,
        )
        return style
    if state == FaceState.ARRIVED:
        style.update(
            accent_color=vt.ACCENT_SUCCESS,
            aura_color=vt.ACCENT_SUCCESS,
            eye_width=1.04,
            eye_height=1.26,
            mouth_curve=-0.58,
            mouth_open=0.34,
            mouth_width=0.96,
            mouth_mix=0.22,
            beacon_mix=0.18,
            beacon_height=112.0,
            aura_width=3.6,
            motif_mix=0.14,
        )
        return style
    if state == FaceState.WAITING_RETRY:
        style.update(
            accent_color=vt.ACCENT_ALERT,
            aura_color=vt.ACCENT_WARM,
            eye_width=0.98,
            eye_height=0.68,
            eye_rotation=-8.0,
            iris_bias_x=-6.0,
            iris_bias_y=5.0,
            mouth_curve=0.56,
            mouth_open=0.58,
            mouth_width=1.18,
            mouth_shift=14.0,
            mouth_mix=0.44,
            beacon_mix=0.08,
            beacon_height=88.0,
            asymmetry=1.15,
            aura_width=2.4,
            motif_mix=0.12,
        )
        return style
    style.update(
        accent_color=vt.ACCENT_ALERT,
        aura_color=vt.ACCENT_ALERT,
        panel_tint="#2A3946",
        panel_mix=0.72,
        eye_width=0.76,
        eye_height=1.26,
        eye_rotation=0.0,
        mouth_curve=0.06,
        mouth_width=0.34,
        mouth_mix=0.16,
        nose_scale=0.88,
        nose_mix=0.24,
        beacon_mix=0.64,
        beacon_height=306.0,
        beacon_speed=1.8,
        aura_width=7.0,
        motif_mix=0.36,
    )
    return style


def _chip_copy(payload: FaceRenderPayload) -> str:
    primary = payload.primary_text.strip()
    if primary:
        return primary
    if payload.secondary_text:
        return payload.secondary_text.strip()
    return payload.state.value.replace("_", " ")


def _ellipse_polygon(
    *,
    cx: float,
    cy: float,
    radius_x: float,
    radius_y: float,
    rotation_deg: float = 0.0,
    steps: int = 40,
) -> list[float]:
    points: list[float] = []
    rotation = math.radians(rotation_deg)
    for step in range(steps):
        angle = (2 * math.pi * step) / steps
        px = math.cos(angle) * radius_x
        py = math.sin(angle) * radius_y
        points.extend(_rotate_point(cx, cy, px, py, rotation))
    return points


def _sector_polygon(
    *,
    cx: float,
    cy: float,
    radius_x: float,
    radius_y: float,
    start_deg: float,
    extent_deg: float,
    rotation_deg: float = 0.0,
    steps: int = 24,
) -> list[float]:
    points: list[float] = []
    rotation = math.radians(rotation_deg)
    start = math.radians(start_deg)
    end = math.radians(start_deg + extent_deg)
    total_steps = max(2, steps)
    for index in range(total_steps + 1):
        angle = start + ((end - start) * (index / total_steps))
        px = math.cos(angle) * radius_x
        py = -math.sin(angle) * radius_y
        points.extend(_rotate_point(cx, cy, px, py, rotation))
    return points


def _rotate_point(cx: float, cy: float, px: float, py: float, rotation: float) -> tuple[float, float]:
    rotated_x = (px * math.cos(rotation)) - (py * math.sin(rotation))
    rotated_y = (px * math.sin(rotation)) + (py * math.cos(rotation))
    return (cx + rotated_x, cy + rotated_y)


def _lerp(start: float, end: float, alpha: float) -> float:
    return start + ((end - start) * alpha)


def _ease_in_out(alpha: float) -> float:
    if alpha <= 0.0:
        return 0.0
    if alpha >= 1.0:
        return 1.0
    return alpha * alpha * (3.0 - (2.0 * alpha))


def _mix_color(start_hex: str, end_hex: str, alpha: float) -> str:
    alpha = max(0.0, min(1.0, alpha))
    start = tuple(int(start_hex[idx : idx + 2], 16) for idx in (1, 3, 5))
    end = tuple(int(end_hex[idx : idx + 2], 16) for idx in (1, 3, 5))
    mixed = tuple(int(round(_lerp(left, right, alpha))) for left, right in zip(start, end))
    return f"#{mixed[0]:02X}{mixed[1]:02X}{mixed[2]:02X}"
