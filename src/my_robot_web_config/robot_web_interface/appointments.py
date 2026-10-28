from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterable


DEFAULT_DB_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_DB_PATH",
        Path(__file__).resolve().parents[1] / "patient_booking.db",
    )
)

DEFAULT_ROBOT_STATE_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_ROBOT_STATE_PATH",
        Path(__file__).resolve().parents[1] / "robot_state.json",
    )
)

DEFAULT_SYMPTOM_ROOM_RULES_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_SYMPTOM_RULES_PATH",
        Path(__file__).resolve().parents[1] / "symptom_room_rules.json",
    )
)


@dataclass(slots=True)
class Appointment:
    id: int
    patient_name: str
    phone: str
    department: str
    appointment_date: str
    appointment_time: str
    symptoms: str
    created_at: str


@dataclass(slots=True)
class RobotState:
    robot_name: str
    status: str
    current_zone: str
    battery_level: int
    queue_limit: int
    auto_dispatch: bool
    note: str
    updated_at: str


@dataclass(slots=True)
class SymptomRoomRule:
    id: int
    symptom_keywords: str
    department: str
    room_label: str
    note: str


class AppointmentStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    department TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    appointment_time TEXT NOT NULL,
                    symptoms TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def create_appointment(
        self,
        *,
        patient_name: str,
        phone: str,
        department: str,
        appointment_date: str,
        appointment_time: str,
        symptoms: str,
    ) -> Appointment:
        patient_name = patient_name.strip()
        phone = phone.strip()
        department = department.strip()
        appointment_date = appointment_date.strip()
        appointment_time = appointment_time.strip()
        symptoms = symptoms.strip()

        if not patient_name:
            raise ValueError("Tên bệnh nhân không được để trống.")
        if not phone:
            raise ValueError("Số điện thoại không được để trống.")
        if not department:
            raise ValueError("Khoa khám không được để trống.")
        if not appointment_date:
            raise ValueError("Ngày khám không được để trống.")
        if not appointment_time:
            raise ValueError("Giờ khám không được để trống.")

        created_at = datetime.now().isoformat(timespec="seconds")

        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO appointments (
                    patient_name,
                    phone,
                    department,
                    appointment_date,
                    appointment_time,
                    symptoms,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_name,
                    phone,
                    department,
                    appointment_date,
                    appointment_time,
                    symptoms,
                    created_at,
                ),
            )
            connection.commit()
            appointment_id = int(cursor.lastrowid)

        return Appointment(
            id=appointment_id,
            patient_name=patient_name,
            phone=phone,
            department=department,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            symptoms=symptoms,
            created_at=created_at,
        )

    def list_appointments(self, limit: int = 25) -> list[Appointment]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    patient_name,
                    phone,
                    department,
                    appointment_date,
                    appointment_time,
                    symptoms,
                    created_at
                FROM appointments
                ORDER BY appointment_date ASC, appointment_time ASC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_appointment(row) for row in rows]

    def list_appointments_by_phone(self, phone: str, limit: int = 20) -> list[Appointment]:
        normalized_phone = "".join(character for character in phone if character.isdigit())
        if not normalized_phone:
            return []

        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    patient_name,
                    phone,
                    department,
                    appointment_date,
                    appointment_time,
                    symptoms,
                    created_at
                FROM appointments
                WHERE phone = ?
                ORDER BY appointment_date DESC, appointment_time DESC, id DESC
                LIMIT ?
                """,
                (normalized_phone, limit),
            ).fetchall()
        return [self._row_to_appointment(row) for row in rows]

    def count_appointments(self) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM appointments"
            ).fetchone()
        return int(row["total"])

    @staticmethod
    def _row_to_appointment(row: sqlite3.Row) -> Appointment:
        return Appointment(
            id=int(row["id"]),
            patient_name=str(row["patient_name"]),
            phone=str(row["phone"]),
            department=str(row["department"]),
            appointment_date=str(row["appointment_date"]),
            appointment_time=str(row["appointment_time"]),
            symptoms=str(row["symptoms"]),
            created_at=str(row["created_at"]),
        )


class RobotStateStore:
    def __init__(self, state_path: Path | str = DEFAULT_ROBOT_STATE_PATH) -> None:
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> RobotState:
        if not self.state_path.exists():
            state = self.default_state()
            self.save(state)
            return state

        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = self.default_state()
            self.save(state)
            return state

        return RobotState(
            robot_name=str(raw.get("robot_name", "AURORA")),
            status=str(raw.get("status", "Sẵn sàng")),
            current_zone=str(raw.get("current_zone", "Cổng bệnh viện")),
            battery_level=int(raw.get("battery_level", 88)),
            queue_limit=int(raw.get("queue_limit", 10)),
            auto_dispatch=bool(raw.get("auto_dispatch", True)),
            note=str(raw.get("note", "Robot đang chờ hướng dẫn bệnh nhân tiếp theo.")),
            updated_at=str(raw.get("updated_at", datetime.now().isoformat(timespec="seconds"))),
        )

    def save(self, state: RobotState) -> RobotState:
        payload = {
            "robot_name": state.robot_name,
            "status": state.status,
            "current_zone": state.current_zone,
            "battery_level": int(state.battery_level),
            "queue_limit": int(state.queue_limit),
            "auto_dispatch": bool(state.auto_dispatch),
            "note": state.note,
            "updated_at": state.updated_at,
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def update(
        self,
        *,
        robot_name: str,
        status: str,
        current_zone: str,
        battery_level: int,
        queue_limit: int,
        auto_dispatch: bool,
        note: str,
    ) -> RobotState:
        state = RobotState(
            robot_name=robot_name.strip() or "AURORA",
            status=status.strip() or "Sẵn sàng",
            current_zone=current_zone.strip() or "Cổng bệnh viện",
            battery_level=max(0, min(100, int(battery_level))),
            queue_limit=max(1, int(queue_limit)),
            auto_dispatch=bool(auto_dispatch),
            note=note.strip(),
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
        return self.save(state)

    @staticmethod
    def default_state() -> RobotState:
        return RobotState(
            robot_name="AURORA",
            status="Sẵn sàng",
            current_zone="Cổng bệnh viện",
            battery_level=88,
            queue_limit=10,
            auto_dispatch=True,
            note="Robot đang chờ hướng dẫn bệnh nhân tiếp theo.",
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )


class SymptomRoomRuleStore:
    def __init__(self, path: Path | str = DEFAULT_SYMPTOM_ROOM_RULES_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_rules(self) -> list[SymptomRoomRule]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        rules: list[SymptomRoomRule] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            rules.append(
                SymptomRoomRule(
                    id=int(item.get("id", len(rules) + 1)),
                    symptom_keywords=str(item.get("symptom_keywords", "")).strip(),
                    department=str(item.get("department", "")).strip(),
                    room_label=str(item.get("room_label", "")).strip(),
                    note=str(item.get("note", "")).strip(),
                )
            )
        return sorted(rules, key=lambda rule: rule.id)

    def create_rule(
        self,
        *,
        symptom_keywords: str,
        room_label: str,
        department: str = "",
        note: str = "",
    ) -> SymptomRoomRule:
        symptom_keywords = symptom_keywords.strip()
        room_label = room_label.strip()
        department = department.strip()
        note = note.strip()

        if not symptom_keywords:
            raise ValueError("Triệu chứng không được để trống.")
        if not room_label:
            raise ValueError("Phòng khám không được để trống.")

        rules = self.list_rules()
        next_id = max((rule.id for rule in rules), default=0) + 1
        rule = SymptomRoomRule(
            id=next_id,
            symptom_keywords=symptom_keywords,
            department=department,
            room_label=room_label,
            note=note,
        )
        rules.append(rule)
        self._save_rules(rules)
        return rule

    def delete_rule(self, rule_id: int) -> bool:
        rules = self.list_rules()
        remaining = [rule for rule in rules if rule.id != int(rule_id)]
        if len(remaining) == len(rules):
            return False
        self._save_rules(remaining)
        return True

    def _save_rules(self, rules: Iterable[SymptomRoomRule]) -> None:
        payload = [
            {
                "id": rule.id,
                "symptom_keywords": rule.symptom_keywords,
                "department": rule.department,
                "room_label": rule.room_label,
                "note": rule.note,
            }
            for rule in rules
        ]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def format_appointments(appointments: Iterable[Appointment]) -> list[dict[str, str]]:
    return [
        {
            "id": str(appointment.id),
            "patient_name": appointment.patient_name,
            "phone": appointment.phone,
            "department": appointment.department,
            "appointment_date": appointment.appointment_date,
            "appointment_time": appointment.appointment_time,
            "symptoms": appointment.symptoms or "Chưa ghi chú",
            "created_at": appointment.created_at,
        }
        for appointment in appointments
    ]


def format_symptom_room_rules(rules: Iterable[SymptomRoomRule]) -> list[dict[str, str]]:
    return [
        {
            "id": str(rule.id),
            "symptom_keywords": rule.symptom_keywords,
            "department": rule.department or "Chưa gán khoa",
            "room_label": rule.room_label,
            "note": rule.note or "Không có ghi chú",
        }
        for rule in rules
    ]
