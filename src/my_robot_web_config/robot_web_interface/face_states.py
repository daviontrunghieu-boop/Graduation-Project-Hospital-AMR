#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class FaceState(str, Enum):
    IDLE = "idle"
    ATTENTION = "attention"
    GREETING = "greeting"
    LISTENING = "listening"
    SPEAKING = "speaking"
    CALLING_PATIENT = "calling_patient"
    CONFIRMING = "confirming"
    NAVIGATING = "navigating"
    ARRIVED = "arrived"
    WAITING_RETRY = "waiting_retry"
    ERROR_OR_HUMAN_ASSISTANCE = "error_or_human_assistance"


class EyeFocus(str, Enum):
    GENTLE_SCAN = "gentle_scan"
    CENTER_LOCK = "center_lock"
    GREETING_LIFT = "greeting_lift"
    LISTEN_LOCK = "listen_lock"
    SPEAK_LOCK = "speak_lock"
    PATH_LEAD = "path_lead"
    RELIEF_SOFTEN = "relief_soften"
    HELP_FOCUS = "help_focus"


class MouthMode(str, Enum):
    CLOSED = "closed"
    SOFT_SPEECH = "soft_speech"
    CLEAR_SPEECH = "clear_speech"
    EMPHATIC_SPEECH = "emphatic_speech"
    CONFIRM_PULSE = "confirm_pulse"
    ARRIVAL_LINE = "arrival_line"
    RETRY_PROMPT = "retry_prompt"
    SUPPORT_PROMPT = "support_prompt"


@dataclass(frozen=True, slots=True)
class FaceStateProfile:
    eye_open: float
    eye_brightness: float
    eye_motion: float
    info_emphasis: float
    enter_ms: int
    exit_ms: int
    eye_focus: EyeFocus
    mouth_mode: MouthMode
    summary: str


CANONICAL_FACE_STATES: Final[tuple[FaceState, ...]] = (
    FaceState.IDLE,
    FaceState.ATTENTION,
    FaceState.GREETING,
    FaceState.LISTENING,
    FaceState.SPEAKING,
    FaceState.CALLING_PATIENT,
    FaceState.CONFIRMING,
    FaceState.NAVIGATING,
    FaceState.ARRIVED,
    FaceState.WAITING_RETRY,
    FaceState.ERROR_OR_HUMAN_ASSISTANCE,
)

OPERATIONAL_SUBSET: Final[tuple[FaceState, ...]] = (
    FaceState.IDLE,
    FaceState.ATTENTION,
    FaceState.SPEAKING,
    FaceState.CALLING_PATIENT,
    FaceState.CONFIRMING,
    FaceState.NAVIGATING,
    FaceState.ARRIVED,
    FaceState.WAITING_RETRY,
    FaceState.ERROR_OR_HUMAN_ASSISTANCE,
)

STATE_PROFILES: Final[dict[FaceState, FaceStateProfile]] = {
    FaceState.IDLE: FaceStateProfile(
        eye_open=0.82,
        eye_brightness=0.58,
        eye_motion=0.18,
        info_emphasis=0.18,
        enter_ms=320,
        exit_ms=320,
        eye_focus=EyeFocus.GENTLE_SCAN,
        mouth_mode=MouthMode.CLOSED,
        summary="Calm waiting state with a natural blink loop and low support text emphasis.",
    ),
    FaceState.ATTENTION: FaceStateProfile(
        eye_open=0.96,
        eye_brightness=0.78,
        eye_motion=0.12,
        info_emphasis=0.24,
        enter_ms=220,
        exit_ms=220,
        eye_focus=EyeFocus.CENTER_LOCK,
        mouth_mode=MouthMode.CLOSED,
        summary="Robot has noticed someone and tightens focus without becoming noisy.",
    ),
    FaceState.GREETING: FaceStateProfile(
        eye_open=0.9,
        eye_brightness=0.8,
        eye_motion=0.14,
        info_emphasis=0.34,
        enter_ms=240,
        exit_ms=260,
        eye_focus=EyeFocus.GREETING_LIFT,
        mouth_mode=MouthMode.SOFT_SPEECH,
        summary="Warm first-contact state that feels welcoming instead of playful.",
    ),
    FaceState.LISTENING: FaceStateProfile(
        eye_open=0.62,
        eye_brightness=0.62,
        eye_motion=0.05,
        info_emphasis=0.22,
        enter_ms=180,
        exit_ms=180,
        eye_focus=EyeFocus.LISTEN_LOCK,
        mouth_mode=MouthMode.CLOSED,
        summary="Quiet, patient listening state that is visibly different from idle.",
    ),
    FaceState.SPEAKING: FaceStateProfile(
        eye_open=0.6,
        eye_brightness=0.8,
        eye_motion=0.08,
        info_emphasis=0.4,
        enter_ms=200,
        exit_ms=260,
        eye_focus=EyeFocus.SPEAK_LOCK,
        mouth_mode=MouthMode.CLEAR_SPEECH,
        summary="General speech state with clear mouth rhythm and restrained eye movement.",
    ),
    FaceState.CALLING_PATIENT: FaceStateProfile(
        eye_open=0.68,
        eye_brightness=0.9,
        eye_motion=0.1,
        info_emphasis=0.9,
        enter_ms=180,
        exit_ms=260,
        eye_focus=EyeFocus.CENTER_LOCK,
        mouth_mode=MouthMode.EMPHATIC_SPEECH,
        summary="Higher-priority call state with stronger eye and info emphasis than speaking.",
    ),
    FaceState.CONFIRMING: FaceStateProfile(
        eye_open=0.74,
        eye_brightness=0.82,
        eye_motion=0.06,
        info_emphasis=0.48,
        enter_ms=180,
        exit_ms=220,
        eye_focus=EyeFocus.CENTER_LOCK,
        mouth_mode=MouthMode.CONFIRM_PULSE,
        summary="Short trust-building confirmation beat before the next action.",
    ),
    FaceState.NAVIGATING: FaceStateProfile(
        eye_open=0.56,
        eye_brightness=0.58,
        eye_motion=0.05,
        info_emphasis=0.56,
        enter_ms=200,
        exit_ms=220,
        eye_focus=EyeFocus.PATH_LEAD,
        mouth_mode=MouthMode.CLOSED,
        summary="Focused guidance state with stable eyes and less cute energy than greeting.",
    ),
    FaceState.ARRIVED: FaceStateProfile(
        eye_open=0.92,
        eye_brightness=0.82,
        eye_motion=0.08,
        info_emphasis=0.52,
        enter_ms=220,
        exit_ms=260,
        eye_focus=EyeFocus.RELIEF_SOFTEN,
        mouth_mode=MouthMode.ARRIVAL_LINE,
        summary="Completion state that reads as successful and gently returns toward calm.",
    ),
    FaceState.WAITING_RETRY: FaceStateProfile(
        eye_open=0.6,
        eye_brightness=0.52,
        eye_motion=0.04,
        info_emphasis=0.5,
        enter_ms=180,
        exit_ms=200,
        eye_focus=EyeFocus.RELIEF_SOFTEN,
        mouth_mode=MouthMode.RETRY_PROMPT,
        summary="Retry state with mild confusion but no harsh failure signal.",
    ),
    FaceState.ERROR_OR_HUMAN_ASSISTANCE: FaceStateProfile(
        eye_open=0.5,
        eye_brightness=0.36,
        eye_motion=0.01,
        info_emphasis=0.78,
        enter_ms=160,
        exit_ms=220,
        eye_focus=EyeFocus.HELP_FOCUS,
        mouth_mode=MouthMode.SUPPORT_PROMPT,
        summary="Serious but not scary fallback state that prioritizes human-help guidance.",
    ),
}

REQUIRED_STATE_NAMES: Final[tuple[str, ...]] = tuple(
    state.value for state in CANONICAL_FACE_STATES
)
OPERATIONAL_STATE_NAMES: Final[tuple[str, ...]] = tuple(
    state.value for state in OPERATIONAL_SUBSET
)
