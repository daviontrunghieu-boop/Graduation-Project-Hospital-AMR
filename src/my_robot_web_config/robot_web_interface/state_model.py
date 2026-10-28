from __future__ import annotations

import time
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from ament_index_python.packages import get_package_share_directory

if __package__ in (None, ""):
    from face_states import (
        OPERATIONAL_SUBSET,
        REQUIRED_STATE_NAMES,
        FaceState,
        STATE_PROFILES,
    )
    from payloads import FaceRenderPayload, sample_payload_for_state
else:
    from .face_states import (
        OPERATIONAL_SUBSET,
        REQUIRED_STATE_NAMES,
        FaceState,
        STATE_PROFILES,
    )
    from .payloads import FaceRenderPayload, sample_payload_for_state


# CẬP NHẬT 1: Sử dụng ament_index_python để lấy đường dẫn cài đặt của ROS 2 package
try:
    _package_share_dir = get_package_share_directory('my_robot_web_config')
    CONFIG_PATH: Final[Path] = Path(_package_share_dir) / "config" / "ui_state_map.yaml"
except Exception:
    # Fallback cho trường hợp chạy test local không thông qua ROS 2 workspace
    CONFIG_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "config" / "ui_state_map.yaml"


DEFAULT_PANEL_TABS: Final[dict[FaceState, str]] = {
    FaceState.IDLE: "waiting",
    FaceState.ATTENTION: "waiting",
    FaceState.GREETING: "waiting",
    FaceState.LISTENING: "robot_status",
    FaceState.SPEAKING: "turn_info",
    FaceState.CALLING_PATIENT: "turn_info",
    FaceState.CONFIRMING: "turn_info",
    FaceState.NAVIGATING: "map",
    FaceState.ARRIVED: "map",
    FaceState.WAITING_RETRY: "robot_status",
    FaceState.ERROR_OR_HUMAN_ASSISTANCE: "help",
}


@dataclass(frozen=True, slots=True)
class TransitionRule:
    target: FaceState
    min_hold_ms: int = 0
    soft_exit_ms: int = 0
    requires_warning_signal: bool = False
    note: str = ""


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    allowed: bool
    rule: TransitionRule | None
    reason: str


@dataclass(frozen=True, slots=True)
class RuntimeTransitionResult:
    applied: bool
    from_state: FaceState
    to_state: FaceState
    payload: FaceRenderPayload
    transition_ms: int
    decision: TransitionDecision


class FaceRuntimeController:
    def __init__(
        self,
        state_model: FaceStateModel,
        *,
        initial_state: FaceState = FaceState.IDLE,
        initial_payload: FaceRenderPayload | None = None,
    ) -> None:
        self.state_model = state_model
        self.current_state = initial_state
        self.current_payload = initial_payload or sample_payload_for_state(initial_state)
        self.entered_at_ms = self._now_ms()

    def request_state(
        self,
        target: FaceState,
        *,
        payload: FaceRenderPayload | None = None,
        warning_signal_sent: bool = False,
        now_ms: float | None = None,
    ) -> RuntimeTransitionResult:
        now_ms = self._now_ms() if now_ms is None else now_ms

        if target == self.current_state:
            next_payload = payload or self.current_payload
            return RuntimeTransitionResult(
                applied=True,
                from_state=self.current_state,
                to_state=target,
                payload=next_payload.with_state(target),
                transition_ms=0,
                decision=TransitionDecision(allowed=True, rule=None, reason="state unchanged"),
            )

        decision = self.state_model.resolve_transition(
            self.current_state,
            target,
            warning_signal_sent=warning_signal_sent,
        )
        if not decision.allowed:
            return RuntimeTransitionResult(
                applied=False,
                from_state=self.current_state,
                to_state=target,
                payload=self.current_payload,
                transition_ms=0,
                decision=decision,
            )

        assert decision.rule is not None
        held_for_ms = now_ms - self.entered_at_ms
        if decision.rule.min_hold_ms and held_for_ms < decision.rule.min_hold_ms:
            return RuntimeTransitionResult(
                applied=False,
                from_state=self.current_state,
                to_state=target,
                payload=self.current_payload,
                transition_ms=0,
                decision=TransitionDecision(
                    allowed=False,
                    rule=decision.rule,
                    reason=(
                        f"state {self.current_state.value} must hold for at least "
                        f"{decision.rule.min_hold_ms}ms before leaving"
                    ),
                ),
            )

        next_payload = (payload or sample_payload_for_state(target)).with_state(target)
        transition_ms = max(
            STATE_PROFILES[target].enter_ms,
            decision.rule.soft_exit_ms,
        )
        previous_state = self.current_state
        self.current_state = target
        self.current_payload = next_payload
        self.entered_at_ms = now_ms
        return RuntimeTransitionResult(
            applied=True,
            from_state=previous_state,
            to_state=target,
            payload=next_payload,
            transition_ms=transition_ms,
            decision=decision,
        )

    def request_trigger(
        self,
        trigger: str,
        *,
        payload: FaceRenderPayload | None = None,
        warning_signal_sent: bool = False,
        now_ms: float | None = None,
    ) -> RuntimeTransitionResult:
        return self.request_state(
            self.state_model.resolve_trigger(trigger),
            payload=payload,
            warning_signal_sent=warning_signal_sent,
            now_ms=now_ms,
        )

    @staticmethod
    def _now_ms() -> float:
        return time.monotonic() * 1000.0


class FaceStateModel:
    def __init__(
        self,
        trigger_map: dict[str, FaceState],
        transition_map: dict[FaceState, tuple[TransitionRule, ...]],
        operational_subset: tuple[FaceState, ...],
    ) -> None:
        self.trigger_map = trigger_map
        self.transition_map = transition_map
        self.operational_subset = operational_subset

    @classmethod
    def from_default_files(cls) -> "FaceStateModel":
        data = _load_state_map(CONFIG_PATH)
        return cls(
            trigger_map=_build_trigger_map(data["trigger_map"]),
            transition_map=_build_transition_map(),
            operational_subset=tuple(FaceState(name) for name in data["operational_subset"]),
        )

    def resolve_trigger(self, trigger: str) -> FaceState:
        return self.trigger_map[trigger]

    def resolve_transition(
        self,
        current: FaceState,
        target: FaceState,
        *,
        warning_signal_sent: bool = False,
    ) -> TransitionDecision:
        for rule in self.transition_map[current]:
            if rule.target != target:
                continue
            if rule.requires_warning_signal and not warning_signal_sent:
                return TransitionDecision(
                    allowed=False,
                    rule=rule,
                    reason="transition requires a short warning signal before entering error state",
                )
            return TransitionDecision(allowed=True, rule=rule, reason=rule.note or "allowed")

        return TransitionDecision(
            allowed=False,
            rule=None,
            reason=f"transition {current.value} -> {target.value} is outside the approved spec",
        )

    def allowed_targets(self, state: FaceState) -> tuple[FaceState, ...]:
        return tuple(rule.target for rule in self.transition_map[state])

    def default_panel_tab(self, state: FaceState) -> str:
        return DEFAULT_PANEL_TABS[state]


def _load_state_map(path: Path) -> dict[str, object]:
    # CẬP NHẬT 2: Đọc file YAML bằng yaml thay vì json
    with open(path, 'r', encoding="utf-8") as file:
        data = yaml.safe_load(file)
        
    catalog = tuple(data["catalog"])
    if catalog != REQUIRED_STATE_NAMES:
        raise ValueError("ui_state_map.yaml catalog does not match the canonical 11-state face set")

    subset = tuple(data["operational_subset"])
    expected_subset = tuple(state.value for state in OPERATIONAL_SUBSET)
    if subset != expected_subset:
        raise ValueError(
            "ui_state_map.yaml operational subset must stay mapped into the canonical catalog"
        )

    return data


def _build_trigger_map(raw_trigger_map: dict[str, str]) -> dict[str, FaceState]:
    return {trigger: FaceState(target_name) for trigger, target_name in raw_trigger_map.items()}


def _rules(*rules: TransitionRule) -> tuple[TransitionRule, ...]:
    return rules


def _build_transition_map() -> dict[FaceState, tuple[TransitionRule, ...]]:
    return {
        FaceState.IDLE: _rules(
            TransitionRule(FaceState.ATTENTION, note="standard awareness entry"),
            TransitionRule(FaceState.CALLING_PATIENT, note="queue-driven call can interrupt idle"),
            TransitionRule(FaceState.SPEAKING, note="short guidance message can start from idle"),
            TransitionRule(
                FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                requires_warning_signal=True,
                note="direct idle to error needs a brief visual warning beat",
            ),
        ),
        FaceState.ATTENTION: _rules(
            TransitionRule(FaceState.GREETING, note="first-contact path"),
            TransitionRule(FaceState.LISTENING, note="ready to receive a response"),
            TransitionRule(FaceState.SPEAKING, note="attention can move into short guidance"),
            TransitionRule(FaceState.CALLING_PATIENT, note="attention can escalate into a queue call"),
            TransitionRule(FaceState.WAITING_RETRY, note="attention can pause for retry"),
            TransitionRule(FaceState.IDLE, soft_exit_ms=180, note="attention can relax back to idle"),
        ),
        FaceState.GREETING: _rules(
            TransitionRule(FaceState.SPEAKING, note="greeting typically flows into speech"),
            TransitionRule(FaceState.ATTENTION, soft_exit_ms=180, note="brief reset before next branch"),
            TransitionRule(FaceState.IDLE, soft_exit_ms=220, note="greeting can settle to idle"),
        ),
        FaceState.LISTENING: _rules(
            TransitionRule(FaceState.WAITING_RETRY, note="retry loop from the spec"),
            TransitionRule(FaceState.CONFIRMING, note="user response confirmed"),
            TransitionRule(FaceState.SPEAKING, note="listening can answer with a short explanation"),
            TransitionRule(FaceState.ATTENTION, soft_exit_ms=180, note="listening can relax to attention"),
            TransitionRule(
                FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                note="listening failure can escalate to human help",
            ),
        ),
        FaceState.SPEAKING: _rules(
            TransitionRule(
                FaceState.IDLE,
                soft_exit_ms=320,
                note="speaking must settle out instead of cutting to idle abruptly",
            ),
            TransitionRule(FaceState.CONFIRMING, note="spoken guidance can end in confirmation"),
            TransitionRule(FaceState.NAVIGATING, note="short prompt can hand off into navigation"),
            TransitionRule(FaceState.WAITING_RETRY, note="unclear response loops into retry"),
            TransitionRule(
                FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                note="speech path can escalate when the flow cannot continue",
            ),
            TransitionRule(
                FaceState.CALLING_PATIENT,
                note="general speech can escalate into a stronger patient call",
            ),
        ),
        FaceState.CALLING_PATIENT: _rules(
            TransitionRule(FaceState.CONFIRMING, note="happy-path queue handoff"),
            TransitionRule(FaceState.SPEAKING, note="call can continue with normal speech"),
            TransitionRule(FaceState.WAITING_RETRY, note="patient did not respond clearly"),
            TransitionRule(
                FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                note="call path can escalate into support mode",
            ),
            TransitionRule(
                FaceState.IDLE,
                min_hold_ms=1800,
                soft_exit_ms=260,
                note="calling_patient cannot collapse back to idle too quickly",
            ),
        ),
        FaceState.CONFIRMING: _rules(
            TransitionRule(FaceState.NAVIGATING, note="confirmed patient moves into guidance"),
            TransitionRule(FaceState.SPEAKING, note="confirmation can add a short spoken step"),
            TransitionRule(
                FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                note="confirmation failure escalates to support mode",
            ),
        ),
        FaceState.NAVIGATING: _rules(
            TransitionRule(FaceState.ARRIVED, note="navigation completion path"),
            TransitionRule(FaceState.SPEAKING, note="short spoken reminder while moving"),
            TransitionRule(
                FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                note="navigation failure escalates to support mode",
            ),
        ),
        FaceState.ARRIVED: _rules(
            TransitionRule(FaceState.IDLE, soft_exit_ms=240, note="arrived settles back to standby"),
            TransitionRule(FaceState.SPEAKING, note="arrival can deliver a short completion message"),
            TransitionRule(FaceState.ATTENTION, note="arrival can hold for the next interaction"),
        ),
        FaceState.WAITING_RETRY: _rules(
            TransitionRule(FaceState.LISTENING, note="required retry loop from the spec"),
            TransitionRule(FaceState.ATTENTION, note="retry can reset into attention"),
            TransitionRule(FaceState.SPEAKING, note="retry can explain the next step"),
            TransitionRule(FaceState.CONFIRMING, note="retry can recover into confirmation"),
            TransitionRule(
                FaceState.ERROR_OR_HUMAN_ASSISTANCE,
                note="retry can escalate when the loop cannot recover",
            ),
        ),
        FaceState.ERROR_OR_HUMAN_ASSISTANCE: _rules(
            TransitionRule(FaceState.IDLE, soft_exit_ms=260, note="support state can reset to idle"),
            TransitionRule(
                FaceState.ATTENTION,
                soft_exit_ms=220,
                note="support state can recover into a supervised retry",
            ),
        ),
    }


DEFAULT_STATE_MODEL: Final[FaceStateModel] = FaceStateModel.from_default_files()