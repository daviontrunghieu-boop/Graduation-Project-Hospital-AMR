#!/usr/bin/env python3
from __future__ import annotations

import base64
from datetime import date, datetime
import json
import logging
import os
from pathlib import Path
import re
import unicodedata

from fastapi import Request
from fastapi.responses import JSONResponse
from nicegui import app
from nicegui import run as nicegui_run
from nicegui import ui

try:
    from wed_server.web.appointments import AppointmentStore, SymptomRoomRuleStore, format_appointments
except ModuleNotFoundError:
    from appointments import AppointmentStore, SymptomRoomRuleStore, format_appointments

try:
    import wed_server.web.admin as _admin_pages
except ModuleNotFoundError:
    import admin as _admin_pages


DEPARTMENTS = [
    "Khám tổng quát",
    "Nội khoa",
    "Ngoại khoa",
    "Nhi khoa",
    "Tai mũi họng",
    "Răng hàm mặt",
]

FACILITY_ADDRESS = "Số 1 Võ Văn Ngân, phường Linh Chiểu, TP. Thủ Đức, TP. Hồ Chí Minh"
FACILITY_MAP_QUERY = "Số 1 Võ Văn Ngân, TP Thủ Đức, TP Hồ Chí Minh"
ACISLAB_IMAGE_URL = "https://lookaside.fbsbx.com/lookaside/crawler/media/?media_id=239943628903570"
OPEN_HOUR = 7
CLOSE_HOUR = 17
ACCOUNT_STORE_PATH = Path(
    os.getenv(
        "ROBOT_HOSPITAL_ACCOUNT_PATH",
        Path(__file__).resolve().parents[1] / "patient_accounts.json",
    )
)
FACE_PROFILE_PATH = Path("/home/hieu/ros2_ws/src/my_robot_web_config/robot_web_interface/user_information/patient_face_profiles.json")
FACE_CAPTURE_DIR = Path("/home/hieu/ros2_ws/src/my_robot_web_config/robot_web_interface/user_information/patient_face_images")
ROBOT_PATIENT_PROFILE_PATH = Path("/home/hieu/ros2_ws/src/my_robot_web_config/robot_web_interface/user_information/robot_patient_profiles.json")
PATIENT_INFORMATION_PATH = Path("/home/hieu/ros2_ws/src/my_robot_web_config/robot_web_interface/user_information/patient_information.json")

DEFAULT_ROOM_DESTINATIONS = {
    "101": {"x": 2.5, "y": 1.2, "z": 0.0, "w": 1.0},
    "201": {"x": 3.6, "y": 0.3, "z": 0.0, "w": 1.0},
    "301": {"x": 4.8, "y": -0.7, "z": 0.0, "w": 1.0},
    "401": {"x": 6.0, "y": -1.5, "z": 0.0, "w": 1.0},
    "501": {"x": 7.1, "y": -2.3, "z": 0.0, "w": 1.0},
}
account_dialog = None
CURRENT_LANGUAGE = "vi"

TRANSLATIONS = {
    "vi": {
        "download_app": "Tải ứng dụng",
        "account": "Tài khoản",
        "create_account": "Tạo tài khoản",
        "create_account_first": "Vui lòng tạo tài khoản trước",
        "create_account_prompt": "Bạn cần tạo tài khoản bệnh nhân trước khi đăng ký lịch khám. Sau khi tạo tài khoản, hãy bấm Đặt khám ngay lại.",
        "cancel": "Hủy",
        "close": "Đóng",
        "later": "Để sau",
        "full_name": "Họ và tên",
        "phone": "Số điện thoại",
        "email": "Email",
        "password": "Mật khẩu",
        "account_intro": "Nhập thông tin để tạo tài khoản bệnh nhân.",
        "account_required_fields": "Vui lòng nhập họ tên, số điện thoại và mật khẩu.",
        "account_created": "Đã tạo tài khoản cho {name}.",
        "language_changed": "Đã đổi ngôn ngữ.",
        "home": "Trang chủ",
        "book_now": "Đặt khám ngay",
        "address": "Địa chỉ",
        "time": "Thời gian",
        "hotline": "Tổng đài đặt khám nhanh",
        "contact_info": "Thông tin liên hệ",
        "description": "Mô tả",
        "services": "Các dịch vụ",
        "intro": "Giới thiệu",
        "specialty": "Chuyên khoa",
        "pricing": "Bảng giá",
        "guide_visit": "Hướng dẫn đi khám",
        "book_visit_title": "Đặt khám ngay",
        "book_visit_intro": "Điền thông tin để bệnh viện xác nhận lịch khám.",
        "department": "Khoa khám",
        "visit_date": "Ngày khám",
        "visit_time": "Giờ khám",
        "symptoms": "Triệu chứng ban đầu",
        "confirm_booking": "Xác nhận đặt lịch",
        "need_account_before_booking": "Bạn cần tạo tài khoản bằng số điện thoại này trước khi đặt lịch khám.",
        "booking_success": "Đặt khám thành công",
        "queue_number": "Số thứ tự của bạn: {id}",
        "robot_notice": "HÃY GẶP ROBOT AURORA Ở TRƯỚC CỔNG BỆNH VIỆN VÀ BÁO SỐ THỨ TỰ CHO ROBOT NHÉ. XIN CẢM ƠN",
        "patient_info": "Thông tin bệnh nhân",
        "visit_schedule": "Lịch khám",
        "understood": "Tôi đã hiểu",
        "open_status": "Thời gian: Đang mở cửa (07:00 - 17:00)",
        "closed_status": "Thời gian: Đóng cửa (mở cửa 07:00 - 17:00)",
    },
    "en": {
        "download_app": "Download app",
        "account": "Account",
        "create_account": "Create account",
        "create_account_first": "Please create an account first",
        "create_account_prompt": "You need a patient account before booking an appointment. After creating it, please click Book now again.",
        "cancel": "Cancel",
        "close": "Close",
        "later": "Later",
        "full_name": "Full name",
        "phone": "Phone number",
        "email": "Email",
        "password": "Password",
        "account_intro": "Enter your information to create a patient account.",
        "account_required_fields": "Please enter full name, phone number, and password.",
        "account_created": "Account created for {name}.",
        "language_changed": "Language changed.",
        "home": "Home",
        "book_now": "Book now",
        "address": "Address",
        "time": "Hours",
        "hotline": "Quick booking hotline",
        "contact_info": "Contact information",
        "description": "Description",
        "services": "Services",
        "intro": "Introduction",
        "specialty": "Specialties",
        "pricing": "Pricing",
        "guide_visit": "Visit guide",
        "book_visit_title": "Book an appointment",
        "book_visit_intro": "Fill in your information so the hospital can confirm your appointment.",
        "department": "Department",
        "visit_date": "Appointment date",
        "visit_time": "Appointment time",
        "symptoms": "Initial symptoms",
        "confirm_booking": "Confirm booking",
        "need_account_before_booking": "You need to create an account with this phone number before booking.",
        "booking_success": "Booking successful",
        "queue_number": "Your queue number: {id}",
        "robot_notice": "PLEASE MEET ROBOT AURORA AT THE HOSPITAL GATE AND TELL THE ROBOT YOUR QUEUE NUMBER. THANK YOU.",
        "patient_info": "Patient information",
        "visit_schedule": "Appointment",
        "understood": "I understand",
        "open_status": "Hours: Open now (07:00 - 17:00)",
        "closed_status": "Hours: Closed now (open 07:00 - 17:00)",
    },
    "km": {
        "download_app": "ទាញយកកម្មវិធី",
        "account": "គណនី",
        "create_account": "បង្កើតគណនី",
        "create_account_first": "សូមបង្កើតគណនីជាមុន",
        "create_account_prompt": "អ្នកត្រូវការគណនីអ្នកជំងឺមុនពេលកក់ពិនិត្យ។ បន្ទាប់ពីបង្កើតរួច សូមចុចកក់ម្តងទៀត។",
        "cancel": "បោះបង់",
        "close": "បិទ",
        "later": "ពេលក្រោយ",
        "full_name": "ឈ្មោះពេញ",
        "phone": "លេខទូរស័ព្ទ",
        "email": "អ៊ីមែល",
        "password": "ពាក្យសម្ងាត់",
        "account_intro": "បញ្ចូលព័ត៌មានដើម្បីបង្កើតគណនីអ្នកជំងឺ។",
        "account_required_fields": "សូមបញ្ចូលឈ្មោះ លេខទូរស័ព្ទ និងពាក្យសម្ងាត់។",
        "account_created": "បានបង្កើតគណនីសម្រាប់ {name}។",
        "language_changed": "បានប្ដូរភាសា។",
        "home": "ទំព័រដើម",
        "book_now": "កក់ឥឡូវ",
        "address": "អាសយដ្ឋាន",
        "time": "ម៉ោង",
        "hotline": "លេខទូរស័ព្ទកក់រហ័ស",
        "contact_info": "ព័ត៌មានទំនាក់ទំនង",
        "description": "ពិពណ៌នា",
        "services": "សេវាកម្ម",
        "intro": "ណែនាំ",
        "specialty": "ជំនាញ",
        "pricing": "តារាងតម្លៃ",
        "guide_visit": "ការណែនាំពេលមកពិនិត្យ",
        "book_visit_title": "កក់ការពិនិត្យ",
        "book_visit_intro": "បំពេញព័ត៌មានរបស់អ្នក ដើម្បីឲ្យមន្ទីរពេទ្យបញ្ជាក់ការណាត់ជួប។",
        "department": "ផ្នែកពិនិត្យ",
        "visit_date": "ថ្ងៃពិនិត្យ",
        "visit_time": "ម៉ោងពិនិត្យ",
        "symptoms": "រោគសញ្ញាដំបូង",
        "confirm_booking": "បញ្ជាក់ការកក់",
        "need_account_before_booking": "អ្នកត្រូវបង្កើតគណនីដោយលេខទូរស័ព្ទនេះ មុនពេលកក់។",
        "booking_success": "កក់បានជោគជ័យ",
        "queue_number": "លេខរៀងរបស់អ្នក: {id}",
        "robot_notice": "សូមជួបរ៉ូបូត AURORA នៅមុខច្រកមន្ទីរពេទ្យ ហើយប្រាប់លេខរៀងរបស់អ្នកទៅរ៉ូបូត។ សូមអរគុណ។",
        "patient_info": "ព័ត៌មានអ្នកជំងឺ",
        "visit_schedule": "កាលវិភាគពិនិត្យ",
        "understood": "ខ្ញុំយល់ហើយ",
        "open_status": "ម៉ោង: កំពុងបើក (07:00 - 17:00)",
        "closed_status": "ម៉ោង: បិទ (បើក 07:00 - 17:00)",
    },
}

NAV_ITEMS = [
    (
        "Cơ sở y tế",
        [
            "Bệnh viện công",
            "Bệnh viện tư",
            "Phòng khám",
            "Phòng mạch",
            "Xét nghiệm",
            "Y tế tại nhà",
            "Tiêm chủng",
        ],
    ),
    (
        "Dịch vụ y tế",
        [
            "Đặt khám tại cơ sở",
            "Đặt khám chuyên khoa",
            "Gọi video với bác sĩ",
            "Đặt lịch xét nghiệm",
            "Mua thuốc tại An Khang",
            "Giúp việc cá nhân",
            "Khám doanh nghiệp",
            "Đặt khám theo bác sĩ",
            "Đặt lịch Chụp hình & Nội soi",
            "Đặt lịch Tầm soát/Tổng quát",
            "Thanh toán Viện phí",
            "Gói khám sức khỏe",
            "Y tế tại nhà",
        ],
    ),
    ("Khám sức khỏe doanh nghiệp", []),
    ("Tin tức", ["Tin dịch vụ", "Tin y tế", "Y học thường thức"]),
    (
        "Hướng dẫn",
        [
            "Cài đặt ứng dụng",
            "Đặt lịch khám",
            "Tư vấn khám bệnh qua video",
            "Quy trình hoàn phí",
            "Câu hỏi thường gặp",
            "Quy trình đi khám",
            "Cộng đồng hỏi đáp khám chữa bệnh",
        ],
    ),
    ("Liên hệ hợp tác", ["Cơ sở y tế", "Phòng mạch", "Quảng cáo", "Tuyển Dụng", "Về Medpro"]),
]

HEADER_NAV_LINKS = [
    ("Giới thiệu", "/gioi-thieu"),
    ("Chuyên khoa", "/chuyen-khoa"),
    ("Bảng giá", "/bang-gia"),
    ("Hướng dẫn", "#guide-section"),
]

DOCTOR_TEAM = [
    {
        "image": "/images/bacsi1.jpg?v=1",
        "name": "TS.BS Dương Minh Hoàng",
        "title": "Trưởng khoa Ngoại tổng hợp",
        "section_id": "doctor-duong-minh-hoang",
        "search_terms": ["duong minh hoang", "ngoai tong hop", "khoa ngoai"],
    },
    {
        "image": "/images/bacsi2.jpg?v=1",
        "name": "TS.BS Nguyễn Vũ Trung Hiếu",
        "title": "Trưởng khoa Tim mạch",
        "section_id": "doctor-nguyen-vu-trung-hieu",
        "search_terms": ["nguyen vu trung hieu", "tim mach", "khoa tim mach"],
    },
    {
        "image": "/images/bacsi3.jpg?v=1",
        "name": "TS.BS Lê Minh Yến",
        "title": "Trưởng khoa Hô hấp",
        "section_id": "doctor-le-minh-yen",
        "search_terms": ["le minh yen", "ho hap", "khoa ho hap"],
    },
]

SPECIALTY_SECTIONS = [
    {
        "name": "Khoa Nội tổng quát",
        "summary": "Tiếp nhận sốt, mệt mỏi, đau đầu, mất ngủ và các triệu chứng nội khoa thường gặp.",
        "room_label": "101",
        "section_id": "specialty-noi-tong-quat",
        "search_terms": ["noi tong quat", "noi khoa", "khoa noi tong quat"],
    },
    {
        "name": "Khoa Tim mạch",
        "summary": "Phù hợp với đau ngực, khó thở khi gắng sức, hồi hộp, tim đập nhanh và các bệnh lý tim mạch.",
        "room_label": "201",
        "section_id": "specialty-tim-mach",
        "search_terms": ["tim mach", "khoa tim mach", "tim"],
    },
    {
        "name": "Khoa Hô hấp",
        "summary": "Khám ho khan, ho có đờm, đau họng, khó thở và các vấn đề đường hô hấp.",
        "room_label": "301",
        "section_id": "specialty-ho-hap",
        "search_terms": ["ho hap", "khoa ho hap", "ho"],
    },
    {
        "name": "Khoa Tiêu hóa",
        "summary": "Khám đau bụng, buồn nôn, đầy hơi, tiêu chảy hoặc táo bón kéo dài.",
        "room_label": "401",
        "section_id": "specialty-tieu-hoa",
        "search_terms": ["tieu hoa", "khoa tieu hoa", "da day", "ruot"],
    },
    {
        "name": "Khoa Ngoại",
        "summary": "Khám chấn thương, vết thương, gãy xương, khối bất thường và các trường hợp ngoại khoa.",
        "room_label": "501",
        "section_id": "specialty-ngoai",
        "search_terms": ["ngoai", "ngoai khoa", "khoa ngoai"],
    },
]

store = AppointmentStore()
symptom_rule_store = SymptomRoomRuleStore()
ASSETS_DIR = Path("/home/hieu/ros2_ws/src/my_robot_web_config/assets/images")
FACE_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
app.add_static_files("/images", ASSETS_DIR)
app.add_static_files("/face-captures", FACE_CAPTURE_DIR)
ROBOT_FACE_STATES = [
    {"label": "Chờ hướng dẫn", "source": "/images/idle.png?v=1", "duration": 2.8},
    {"label": "Đang nói", "source": "/images/speaking.png?v=3", "duration": 1.0},
    {"label": "Gọi bệnh nhân", "source": "/images/calling_patient.png?v=1", "duration": 1.5},
    {"label": "Đang dẫn đường", "source": "/images/navigating.png?v=1", "duration": 1.5},
    {"label": "Đang hỗ trợ", "source": "/images/error_or_human_assistance.png?v=1", "duration": 1.8},
]


_original_setup = nicegui_run.setup


def _safe_nicegui_setup() -> None:
    try:
        _original_setup()
    except PermissionError:
        logging.warning(
            "NiceGUI process pool could not start in this environment; continuing without cpu_bound support."
        )


nicegui_run.setup = _safe_nicegui_setup


def opening_status_text(now: datetime | None = None) -> str:
    current = now or datetime.now()
    if OPEN_HOUR <= current.hour < CLOSE_HOUR:
        return tr("open_status")
    return tr("closed_status")


def tr(key: str, **kwargs: str) -> str:
    text = TRANSLATIONS.get(CURRENT_LANGUAGE, TRANSLATIONS["vi"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def normalize_search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold())
    stripped = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped).split())


def search_section_target(query: str) -> tuple[str, str] | None:
    normalized_query = normalize_search_text(query)
    if not normalized_query:
        return None

    candidates = [
        ("intro-section", ["gioi thieu", "gioi thiệu", "aurora", "trung tam y te"]),
        ("doctor-team-section", ["doi ngu bac si", "bac si", "doi ngu chung toi"]),
        ("specialty-section", ["chuyen khoa", "khoa kham", "khoa"]),
        ("guide-section", ["huong dan", "robot", "checkin", "stt"]),
    ]
    for doctor in DOCTOR_TEAM:
        candidates.append((doctor["section_id"], list(doctor["search_terms"])))
    for specialty in SPECIALTY_SECTIONS:
        candidates.append((specialty["section_id"], list(specialty["search_terms"])))

    for target_id, keywords in candidates:
        if any(normalized_query in normalize_search_text(keyword) or normalize_search_text(keyword) in normalized_query for keyword in keywords):
            return target_id, normalized_query
    return None


def attach_robot_face_rotation(image_element, status_label=None) -> None:
    state_index = {"value": 0}

    def show_current_state() -> None:
        state = ROBOT_FACE_STATES[state_index["value"]]
        image_element.set_source(state["source"])
        if status_label is not None:
            status_label.set_text(state["label"])

    def advance_state() -> None:
        state_index["value"] = (state_index["value"] + 1) % len(ROBOT_FACE_STATES)
        show_current_state()
        schedule_next_state()

    def schedule_next_state() -> None:
        duration = float(ROBOT_FACE_STATES[state_index["value"]]["duration"])
        ui.timer(duration, advance_state, once=True, immediate=False)

    show_current_state()
    schedule_next_state()


def normalize_phone(phone: str) -> str:
    return "".join(character for character in phone if character.isdigit())


def _load_registered_patient_phones() -> set[str]:
    try:
        if not ACCOUNT_STORE_PATH.exists():
            return set()
        stored_phones = json.loads(ACCOUNT_STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(stored_phones, list):
            return set()
        return {
            normalized
            for phone in stored_phones
            if isinstance(phone, str)
            for normalized in [normalize_phone(phone)]
            if normalized
        }
    except (OSError, json.JSONDecodeError):
        logging.warning("Could not load patient account store; starting with empty account list.")
        return set()


def _save_registered_patient_phones() -> None:
    try:
        ACCOUNT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ACCOUNT_STORE_PATH.write_text(
            json.dumps(sorted(REGISTERED_PATIENT_PHONES), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        logging.warning("Could not save patient account store.")


def clear_registered_patient_phones() -> None:
    REGISTERED_PATIENT_PHONES.clear()
    try:
        ACCOUNT_STORE_PATH.unlink(missing_ok=True)
    except OSError:
        logging.warning("Could not remove patient account store.")


REGISTERED_PATIENT_PHONES: set[str] = _load_registered_patient_phones()
CURRENT_ACCOUNT_PHONE = ""


def list_registered_patient_phones() -> list[str]:
    return sorted(REGISTERED_PATIENT_PHONES)


def register_patient_phone(phone: str) -> None:
    normalized_phone = normalize_phone(phone)
    if normalized_phone:
        REGISTERED_PATIENT_PHONES.add(normalized_phone)
        _save_registered_patient_phones()


def set_current_account_phone(phone: str) -> None:
    global CURRENT_ACCOUNT_PHONE
    CURRENT_ACCOUNT_PHONE = normalize_phone(phone)


def patient_has_account(phone: str) -> bool:
    return normalize_phone(phone) in REGISTERED_PATIENT_PHONES


def load_json_dictionary(path_like: Path | str) -> dict[str, dict]:
    path = Path(path_like)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_json_dictionary(data: dict[str, dict], path_like: Path | str) -> None:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_face_profiles(profile_path: Path | str = FACE_PROFILE_PATH) -> dict[str, dict]:
    return load_json_dictionary(profile_path)


def save_face_profiles(profiles: dict[str, dict], profile_path: Path | str = FACE_PROFILE_PATH) -> None:
    save_json_dictionary(profiles, profile_path)


def load_robot_patient_profiles(profile_path: Path | str = ROBOT_PATIENT_PROFILE_PATH) -> dict[str, dict]:
    raw = load_json_dictionary(profile_path)
    patients = raw.get("patients", {})
    if isinstance(patients, dict):
        return patients
    return raw


def save_robot_patient_profiles(
    profiles: dict[str, dict],
    profile_path: Path | str = ROBOT_PATIENT_PROFILE_PATH,
) -> None:
    save_json_dictionary(
        {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "patient_count": len(profiles),
            "patients": profiles,
        },
        profile_path,
    )


def load_patient_information(path_like: Path | str = PATIENT_INFORMATION_PATH) -> dict[str, object]:
    raw = load_json_dictionary(path_like)
    patients = raw.get("patients", {})
    if not isinstance(patients, dict):
        patients = {}
    queue_index = raw.get("queue_index", {})
    if not isinstance(queue_index, dict):
        queue_index = {}
    room_destinations = raw.get("room_destinations", {})
    if not isinstance(room_destinations, dict):
        room_destinations = {}

    merged_room_destinations = {
        room_label: dict(destination)
        for room_label, destination in DEFAULT_ROOM_DESTINATIONS.items()
    }
    for room_label, destination in room_destinations.items():
        if isinstance(destination, dict):
            merged_room_destinations[str(room_label)] = dict(destination)

    return {
        "updated_at": str(raw.get("updated_at", "")),
        "patient_count": len(patients),
        "queue_count": len(queue_index),
        "room_destinations": merged_room_destinations,
        "patients": patients,
        "queue_index": queue_index,
    }


def save_patient_information(
    *,
    patients: dict[str, dict],
    queue_index: dict[str, dict],
    room_destinations: dict[str, dict] | None = None,
    path_like: Path | str = PATIENT_INFORMATION_PATH,
) -> None:
    save_json_dictionary(
        {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "patient_count": len(patients),
            "queue_count": len(queue_index),
            "room_destinations": room_destinations or DEFAULT_ROOM_DESTINATIONS,
            "patients": patients,
            "queue_index": queue_index,
        },
        path_like,
    )


def resolve_destination_pose(
    room_label: str,
    room_destinations: dict[str, dict] | None = None,
) -> dict[str, float | bool]:
    destinations = room_destinations or DEFAULT_ROOM_DESTINATIONS
    destination = destinations.get(room_label.strip())
    if isinstance(destination, dict):
        return {
            "x": float(destination.get("x", 0.0)),
            "y": float(destination.get("y", 0.0)),
            "z": float(destination.get("z", 0.0)),
            "w": float(destination.get("w", 1.0)),
            "configured": True,
        }
    return {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0, "configured": False}


def sync_patient_information(
    patient_name: str,
    phone: str,
    *,
    appointment,
    room_label: str,
    matched_phrases: list[str] | None = None,
    path_like: Path | str = PATIENT_INFORMATION_PATH,
) -> dict[str, object]:
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        raise ValueError("Vui lòng nhập số điện thoại hợp lệ để lưu patient_information.")

    payload = load_patient_information(path_like)
    patients = payload["patients"] if isinstance(payload["patients"], dict) else {}
    queue_index = payload["queue_index"] if isinstance(payload["queue_index"], dict) else {}
    room_destinations = payload["room_destinations"] if isinstance(payload["room_destinations"], dict) else DEFAULT_ROOM_DESTINATIONS
    destination_pose = resolve_destination_pose(room_label, room_destinations)
    safe_name = (patient_name or "").strip() or f"benhnhan_{normalized_phone}"
    queue_number = int(appointment.id)
    updated_at = datetime.now().isoformat(timespec="seconds")

    patient_record = {
        "patient_name": safe_name,
        "phone": normalized_phone,
        "queue_number": queue_number,
        "order_label": f"STT {queue_number}",
        "department": str(appointment.department),
        "room_label": room_label.strip(),
        "symptoms": str(appointment.symptoms),
        "appointment_date": str(appointment.appointment_date),
        "appointment_time": str(appointment.appointment_time),
        "created_at": str(appointment.created_at),
        "updated_at": updated_at,
        "matched_phrases": list(matched_phrases or []),
        "destination_pose": destination_pose,
    }
    patients[normalized_phone] = patient_record
    queue_index[str(queue_number)] = {
        "queue_number": queue_number,
        "order_label": f"STT {queue_number}",
        "patient_phone": normalized_phone,
        "patient_name": safe_name,
        "room_label": room_label.strip(),
        "department": str(appointment.department),
        "symptoms": str(appointment.symptoms),
        "destination_pose": destination_pose,
        "updated_at": updated_at,
    }
    save_patient_information(
        patients=patients,
        queue_index=queue_index,
        room_destinations=room_destinations,
        path_like=path_like,
    )
    return patient_record


def sync_robot_patient_profile(
    patient_name: str,
    phone: str,
    *,
    face_capture: dict[str, str] | None = None,
    appointment=None,
    room_label: str = "",
    matched_phrases: list[str] | None = None,
    profile_path: Path | str = ROBOT_PATIENT_PROFILE_PATH,
    patient_information_path: Path | str = PATIENT_INFORMATION_PATH,
) -> dict[str, object]:
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        raise ValueError("Vui lòng nhập số điện thoại hợp lệ để đồng bộ hồ sơ bệnh nhân.")

    profiles = load_robot_patient_profiles(profile_path)
    current_profile = profiles.get(normalized_phone, {})
    face_captures = current_profile.get("face_captures", [])
    if not isinstance(face_captures, list):
        face_captures = []

    now = datetime.now().isoformat(timespec="seconds")
    safe_name = (patient_name or "").strip() or str(current_profile.get("patient_name", "")).strip() or f"benhnhan_{normalized_phone}"

    if face_capture is not None:
        face_captures.append(
            {
                "filename": str(face_capture.get("filename", "")),
                "image_url": str(face_capture.get("image_url", "")),
                "captured_at": str(face_capture.get("captured_at", now)),
                "mime_type": str(face_capture.get("mime_type", "")),
            }
        )
        face_captures = face_captures[-10:]

    updated_profile: dict[str, object] = dict(current_profile)
    updated_profile["patient_name"] = safe_name
    updated_profile["phone"] = normalized_phone
    updated_profile["updated_at"] = now
    updated_profile["face_captures"] = face_captures
    updated_profile["face_capture_count"] = len(face_captures)
    updated_profile["latest_capture_at"] = (
        str(face_captures[-1].get("captured_at", "")) if face_captures else str(current_profile.get("latest_capture_at", ""))
    )
    updated_profile["latest_face_image_url"] = (
        str(face_captures[-1].get("image_url", "")) if face_captures else str(current_profile.get("latest_face_image_url", ""))
    )

    if appointment is not None:
        latest_appointment = {
            "queue_number": int(appointment.id),
            "department": str(appointment.department),
            "room_label": room_label.strip(),
            "appointment_date": str(appointment.appointment_date),
            "appointment_time": str(appointment.appointment_time),
            "symptoms": str(appointment.symptoms),
            "created_at": str(appointment.created_at),
            "matched_phrases": list(matched_phrases or []),
        }
        updated_profile["latest_appointment"] = latest_appointment
        updated_profile["queue_number"] = latest_appointment["queue_number"]
        updated_profile["room_label"] = latest_appointment["room_label"]
        updated_profile["symptoms"] = latest_appointment["symptoms"]
        updated_profile["department"] = latest_appointment["department"]
        updated_profile["appointment_date"] = latest_appointment["appointment_date"]
        updated_profile["appointment_time"] = latest_appointment["appointment_time"]
        updated_profile["voice_node"] = {
            "status": "ready",
            "source": "web_booking",
            "queue_number": latest_appointment["queue_number"],
            "topic": "/voice_manager/patient_queue_map",
            "updated_at": now,
        }
        sync_patient_information(
            safe_name,
            normalized_phone,
            appointment=appointment,
            room_label=room_label,
            matched_phrases=matched_phrases,
            path_like=patient_information_path,
        )

    profiles[normalized_phone] = updated_profile
    save_robot_patient_profiles(profiles, profile_path)
    return updated_profile


def save_face_capture(
    patient_name: str,
    phone: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    profile_path: Path | str = FACE_PROFILE_PATH,
    capture_dir: Path | str = FACE_CAPTURE_DIR,
    robot_profile_path: Path | str = ROBOT_PATIENT_PROFILE_PATH,
) -> dict[str, str | int]:
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        raise ValueError("Vui lòng nhập số điện thoại trước khi lưu ảnh khuôn mặt.")
    if not image_bytes:
        raise ValueError("Không nhận được ảnh khuôn mặt từ trình duyệt.")

    safe_name = (patient_name or "").strip() or f"benhnhan_{normalized_phone}"
    extension = {
        "image/png": "png",
        "image/webp": "webp",
    }.get(mime_type, "jpg")

    target_dir = Path(capture_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{normalized_phone}_{timestamp}.{extension}"
    file_path = target_dir / filename
    file_path.write_bytes(image_bytes)

    profiles = load_face_profiles(profile_path)
    profile = profiles.get(normalized_phone, {})
    captures = profile.get("captures", [])
    if not isinstance(captures, list):
        captures = []

    capture_record = {
        "filename": filename,
        "image_url": f"/face-captures/{filename}",
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "mime_type": mime_type,
    }
    captures.append(capture_record)

    profiles[normalized_phone] = {
        "patient_name": safe_name,
        "phone": normalized_phone,
        "updated_at": capture_record["captured_at"],
        "captures": captures[-10:],
    }
    save_face_profiles(profiles, profile_path)
    sync_robot_patient_profile(
        safe_name,
        normalized_phone,
        face_capture=capture_record,
        profile_path=robot_profile_path,
    )

    return {
        "patient_name": safe_name,
        "phone": normalized_phone,
        "image_url": str(capture_record["image_url"]),
        "filename": filename,
        "capture_count": len(captures[-10:]),
        "captured_at": str(capture_record["captured_at"]),
    }


def split_symptom_keywords(symptom_keywords: str) -> list[str]:
    return [
        " ".join(line.split())
        for line in symptom_keywords.splitlines()
        if " ".join(line.split())
    ]


def normalize_matching_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold())
    without_accents = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
    cleaned = re.sub(r"[^a-z0-9]+", " ", without_accents)
    return " ".join(cleaned.split())


def extract_meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_matching_text(text).split()
        if len(token) > 1
    }


def infer_department_and_room_from_symptoms(symptoms_text: str) -> tuple[str, str, list[str]]:
    patient_text = symptoms_text.strip()
    if not patient_text:
        raise ValueError("Vui lòng nhập triệu chứng ban đầu trước khi đặt lịch khám.")

    patient_normalized = normalize_matching_text(patient_text)
    patient_tokens = extract_meaningful_tokens(patient_text)
    if not patient_tokens:
        raise ValueError("Vui lòng nhập triệu chứng rõ hơn để hệ thống xác định khoa khám.")

    best_rank = (0, 0, 0)
    best_result: tuple[str, str, list[str]] | None = None
    ambiguous_target: tuple[str, str] | None = None

    for rule in symptom_rule_store.list_rules():
        matched_phrases: list[str] = []
        total_score = 0
        strongest_phrase_score = 0

        for phrase in split_symptom_keywords(rule.symptom_keywords):
            phrase_normalized = normalize_matching_text(phrase)
            phrase_tokens = extract_meaningful_tokens(phrase)
            if not phrase_tokens:
                continue

            overlap = len(patient_tokens & phrase_tokens)
            if overlap == 0:
                continue

            coverage = overlap / len(phrase_tokens)
            phrase_score = overlap * 10
            if phrase_normalized and phrase_normalized in patient_normalized:
                phrase_score += 40
            if coverage >= 1:
                phrase_score += 30
            elif coverage >= 0.75:
                phrase_score += 18
            elif coverage >= 0.5:
                phrase_score += 8

            matched_phrases.append(phrase)
            total_score += phrase_score
            strongest_phrase_score = max(strongest_phrase_score, phrase_score)

        rank = (total_score, len(matched_phrases), strongest_phrase_score)
        target = (rule.department.strip(), rule.room_label.strip())

        if rank > best_rank:
            best_rank = rank
            best_result = (target[0], target[1], matched_phrases)
            ambiguous_target = None
        elif rank == best_rank and rank > (0, 0, 0) and best_result is not None:
            if target != (best_result[0], best_result[1]):
                ambiguous_target = target

    if best_result is None or best_rank == (0, 0, 0):
        raise ValueError(
            "Chưa xác định được khoa khám từ triệu chứng bạn nhập. Vui lòng nhập rõ hơn hoặc cập nhật bảng triệu chứng trên web admin."
        )
    if ambiguous_target is not None:
        raise ValueError("Triệu chứng đang phù hợp với nhiều khoa khác nhau. Vui lòng nhập cụ thể hơn để hệ thống xếp đúng phòng khám.")

    department, room_label, matched_phrases = best_result
    return department or "Chưa gán khoa", room_label or "Chưa gán phòng", matched_phrases


def normalize_appointment_time(raw_time: str) -> str:
    value = raw_time.strip()
    matched = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", value)
    if not matched:
        raise ValueError("Giờ khám phải theo định dạng 24 giờ HH:MM, ví dụ 08:30 hoặc 14:45.")
    return f"{int(matched.group(1)):02d}:{matched.group(2)}"


def open_account_dialog() -> None:
    if account_dialog is not None:
        account_dialog.open()


def show_create_account_required() -> None:
    required_dialog = ui.dialog()
    with required_dialog, ui.card().classes("w-[520px] max-w-[94vw] rounded-3xl p-7 text-center shadow-2xl"):
        ui.icon("account_circle").classes("mx-auto text-6xl text-cyan-500")
        ui.label(tr("create_account_first")).classes("mt-4 text-2xl font-black text-slate-900")
        ui.label(tr("create_account_prompt")).classes("mt-3 text-base leading-7 text-slate-600")
        with ui.row().classes("mt-6 w-full gap-3"):
            ui.button(tr("later"), on_click=required_dialog.close).props("flat no-caps").classes("flex-1")

            def open_registration() -> None:
                required_dialog.close()
                open_account_dialog()

            ui.button(tr("create_account"), on_click=open_registration).props("unelevated no-caps").classes(
                "flex-1 rounded-full bg-cyan-500 py-3 font-bold text-white"
            )
    required_dialog.open()


def build_account_registration_form(card_classes: str, redirect_to_home: bool = False) -> None:
    """Biểu mẫu tài khoản dùng HTTP trực tiếp và giữ dữ liệu khi chuyển trang."""
    form_suffix = "account_page" if redirect_to_home else "account_dialog"
    form_id = f"create_account_form_{form_suffix}"
    status_id = f"create_account_status_{form_suffix}"
    name_id = f"create_account_name_{form_suffix}"
    phone_id = f"create_account_phone_{form_suffix}"
    password_id = f"create_account_password_{form_suffix}"
    back_id = f"create_account_back_{form_suffix}"

    with ui.card().classes(card_classes):
        ui.label(tr("create_account")).classes("text-2xl font-black text-slate-900")
        ui.label(tr("account_intro")).classes("text-sm text-slate-500")

        ui.html(
            f"""
            <form id="{form_id}" style="margin-top:22px;width:100%;">
                <label for="{name_id}" style="display:block;margin-bottom:5px;color:#64748b;font-size:13px;">{tr('full_name')}</label>
                <input id="{name_id}" name="name" autocomplete="name" required
                    style="width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;padding:11px 12px;margin-bottom:14px;font-size:15px;outline:none;" />

                <label for="{phone_id}" style="display:block;margin-bottom:5px;color:#64748b;font-size:13px;">{tr('phone')}</label>
                <input id="{phone_id}" name="phone" inputmode="numeric" autocomplete="tel" required
                    style="width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;padding:11px 12px;margin-bottom:14px;font-size:15px;outline:none;" />

                <label for="{password_id}" style="display:block;margin-bottom:5px;color:#64748b;font-size:13px;">{tr('password')}</label>
                <input id="{password_id}" name="password" type="password" autocomplete="new-password" required
                    style="width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;padding:11px 12px;margin-bottom:10px;font-size:15px;outline:none;" />

                <div id="{status_id}" style="min-height:24px;margin:4px 0 12px;font-size:14px;font-weight:600;"></div>

                <div style="display:flex;gap:14px;align-items:center;">
                    <a id="{back_id}" href="/" style="flex:1;text-align:center;text-decoration:none;color:#3b82f6;font-weight:600;padding:10px;">Về trang chủ</a>
                    <button id="{form_id}_submit" type="submit"
                        style="flex:1;border:0;border-radius:4px;background:#68a5dc;color:white;font-weight:700;padding:12px 16px;cursor:pointer;">
                        {tr('create_account')}
                    </button>
                </div>
            </form>
            """,
            sanitize=False,
        ).classes("w-full")

    ui.add_body_html(
        f"""
        <script>
        (() => {{
            const handlerKey = '__create_account_handler_{form_suffix}';
            if (window[handlerKey]) return;
            window[handlerKey] = true;

            const BOOKING_DRAFT_KEY = 'aurora_booking_draft_v2';
            const ACCOUNT_KEY = 'aurora_account_v1';
            const ACCOUNT_FORM_KEY = 'aurora_account_form_draft_v1';

            const getReturnPath = () => {{
                const requested = new URLSearchParams(window.location.search).get('return') || '/';
                return requested.startsWith('/') && !requested.startsWith('//') ? requested : '/';
            }};

            const restoreAccountForm = () => {{
                const nameElement = document.getElementById('{name_id}');
                const phoneElement = document.getElementById('{phone_id}');
                const backElement = document.getElementById('{back_id}');
                if (!nameElement || !phoneElement) return false;

                let bookingDraft = {{}};
                let account = {{}};
                let formDraft = {{}};
                try {{ bookingDraft = JSON.parse(localStorage.getItem(BOOKING_DRAFT_KEY) || '{{}}'); }} catch (_) {{}}
                try {{ account = JSON.parse(localStorage.getItem(ACCOUNT_KEY) || '{{}}'); }} catch (_) {{}}
                try {{ formDraft = JSON.parse(sessionStorage.getItem(ACCOUNT_FORM_KEY) || '{{}}'); }} catch (_) {{}}

                nameElement.value = formDraft.name || bookingDraft.patient_name || account.name || nameElement.value || '';
                phoneElement.value = formDraft.phone || bookingDraft.phone || account.phone || phoneElement.value || '';

                const saveFormDraft = () => {{
                    sessionStorage.setItem(ACCOUNT_FORM_KEY, JSON.stringify({{
                        name: nameElement.value.trim(),
                        phone: phoneElement.value.trim(),
                    }}));
                }};
                nameElement.addEventListener('input', saveFormDraft);
                phoneElement.addEventListener('input', saveFormDraft);

                const returnTo = getReturnPath();
                if (backElement) {{
                    backElement.href = returnTo;
                    backElement.textContent = returnTo.startsWith('/booking') ? 'Quay lại đặt khám' : 'Về trang chủ';
                }}
                return true;
            }};

            const scheduleAccountRestore = (attempt = 0) => {{
                if (restoreAccountForm()) return;
                if (attempt < 50) setTimeout(() => scheduleAccountRestore(attempt + 1), 100);
            }};
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', () => scheduleAccountRestore(), {{once:true}});
            }} else {{
                setTimeout(() => scheduleAccountRestore(), 0);
            }}

            document.addEventListener('submit', async (event) => {{
                if (!event.target || event.target.id !== '{form_id}') return;
                event.preventDefault();

                const status = document.getElementById('{status_id}');
                const submitButton = document.getElementById('{form_id}_submit');
                const nameElement = document.getElementById('{name_id}');
                const phoneElement = document.getElementById('{phone_id}');
                const passwordElement = document.getElementById('{password_id}');
                if (!status || !submitButton || !nameElement || !phoneElement || !passwordElement) return;

                const name = nameElement.value.trim();
                const phone = phoneElement.value.trim();
                const password = passwordElement.value;

                status.style.color = '#475569';
                status.textContent = 'Đang tạo tài khoản...';
                submitButton.disabled = true;
                submitButton.style.opacity = '0.65';

                try {{
                    const response = await fetch('/api/create-account', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{name, phone, password}}),
                    }});
                    const result = await response.json();
                    if (!response.ok || !result.ok) {{
                        throw new Error(result.message || 'Không thể tạo tài khoản.');
                    }}

                    localStorage.setItem(ACCOUNT_KEY, JSON.stringify({{
                        name: result.name || name,
                        phone: result.phone || phone,
                    }}));
                    sessionStorage.removeItem(ACCOUNT_FORM_KEY);

                    status.style.color = '#16a34a';
                    status.textContent = result.message || 'Tạo tài khoản thành công.';
                    const returnTo = getReturnPath();
                    setTimeout(() => window.location.href = returnTo, 650);
                }} catch (error) {{
                    status.style.color = '#dc2626';
                    status.textContent = error.message || 'Không thể tạo tài khoản.';
                    submitButton.disabled = false;
                    submitButton.style.opacity = '1';
                }}
            }}, true);
        }})();
        </script>
        """
    )


def build_account_history_card(card_classes: str) -> None:
    """Tra cứu lịch sử bằng HTTP trực tiếp để không phụ thuộc NiceGUI WebSocket."""
    with ui.card().classes(card_classes):
        ui.label("Lịch sử đặt lịch").classes("text-2xl font-black text-slate-900")
        ui.label("Nhập số điện thoại tài khoản để xem lại các lịch khám đã đặt.").classes(
            "text-sm leading-6 text-slate-500"
        )
        ui.html(
            """
            <form id="native_history_form" style="margin-top:22px;width:100%;">
                <input id="native_history_phone" inputmode="numeric" autocomplete="tel"
                    placeholder="Số điện thoại tra cứu"
                    style="width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;padding:12px;font-size:15px;" />
                <div id="native_history_status" style="min-height:24px;margin:18px 0 12px;font-size:14px;font-weight:700;color:#475569;">
                    Nhập số điện thoại rồi bấm Xem lịch sử để tải các lịch đã đặt.
                </div>
                <div style="display:flex;gap:14px;align-items:center;">
                    <button type="submit"
                        style="flex:1;border:0;border-radius:4px;background:#4f9bd8;color:#fff;font-weight:700;padding:12px 16px;cursor:pointer;">
                        ↻ &nbsp; Xem lịch sử
                    </button>
                    <a href="/" style="flex:1;text-align:center;text-decoration:none;color:#3b82f6;font-weight:600;padding:10px;">Về trang chủ</a>
                </div>
            </form>
            <div id="native_history_results" style="display:grid;gap:12px;margin-top:18px;"></div>
            """,
            sanitize=False,
        ).classes("w-full")

    ui.add_body_html(
        r"""
        <script>
        (() => {
            if (window.__nativeHistoryHandlerInstalled) return;
            window.__nativeHistoryHandlerInstalled = true;
            const escapeHtml = (value) => String(value ?? '')
                .replaceAll('&', '&amp;').replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');

            document.addEventListener('submit', async (event) => {
                if (!event.target || event.target.id !== 'native_history_form') return;
                event.preventDefault();
                const phoneInput = document.getElementById('native_history_phone');
                const status = document.getElementById('native_history_status');
                const results = document.getElementById('native_history_results');
                if (!phoneInput || !status || !results) return;

                const phone = phoneInput.value.trim();
                status.style.color = '#475569';
                status.textContent = 'Đang tải lịch sử...';
                results.innerHTML = '';
                try {
                    const response = await fetch('/api/appointment-history?phone=' + encodeURIComponent(phone));
                    const data = await response.json();
                    if (!response.ok || !data.ok) throw new Error(data.message || 'Không thể tải lịch sử.');
                    const items = data.appointments || [];
                    if (!items.length) {
                        status.textContent = 'Chưa tìm thấy lịch đặt nào cho số điện thoại này.';
                        return;
                    }
                    status.style.color = '#16a34a';
                    status.textContent = `Tìm thấy ${items.length} lịch hẹn.`;
                    results.innerHTML = items.map(item => `
                        <div style="border-radius:18px;background:#f8fafc;padding:16px;border:1px solid #e2e8f0;">
                            <div style="font-weight:900;color:#0f172a;font-size:17px;">STT ${escapeHtml(item.id)} — ${escapeHtml(item.patient_name)}</div>
                            <div style="margin-top:8px;color:#334155;line-height:1.7;">
                                Khoa: ${escapeHtml(item.department)}<br>
                                Ngày: ${escapeHtml(item.appointment_date)} — Giờ: ${escapeHtml(item.appointment_time)}<br>
                                Triệu chứng: ${escapeHtml(item.symptoms || 'Chưa ghi chú')}
                            </div>
                        </div>
                    `).join('');
                } catch (error) {
                    status.style.color = '#dc2626';
                    status.textContent = error.message || 'Không thể tải lịch sử.';
                }
            }, true);
        })();
        </script>
        """
    )


def switch_language(language: str) -> None:
    global CURRENT_LANGUAGE
    CURRENT_LANGUAGE = language
    ui.notify(tr("language_changed"), color="positive")
    ui.run_javascript("window.location.reload()")


@app.post("/api/create-account")
async def create_account_api(request: Request) -> JSONResponse:
    """Tạo tài khoản bằng HTTP trực tiếp, không phụ thuộc callback WebSocket của NiceGUI."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"ok": False, "message": "Dữ liệu gửi lên không hợp lệ."},
            status_code=400,
        )

    name = str(payload.get("name", "")).strip()
    phone = normalize_phone(str(payload.get("phone", "")))
    password = str(payload.get("password", "")).strip()

    if not name or not phone or not password:
        return JSONResponse(
            {"ok": False, "message": tr("account_required_fields")},
            status_code=400,
        )

    if len(phone) < 3:
        return JSONResponse(
            {"ok": False, "message": "Số điện thoại không hợp lệ."},
            status_code=400,
        )

    try:
        REGISTERED_PATIENT_PHONES.add(phone)
        ACCOUNT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ACCOUNT_STORE_PATH.write_text(
            json.dumps(sorted(REGISTERED_PATIENT_PHONES), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        set_current_account_phone(phone)
    except OSError as error:
        logging.exception("Không thể lưu tài khoản bệnh nhân: %s", error)
        return JSONResponse(
            {
                "ok": False,
                "message": "Không thể lưu tài khoản. Hãy kiểm tra quyền ghi file patient_accounts.json.",
            },
            status_code=500,
        )

    return JSONResponse(
        {
            "ok": True,
            "message": tr("account_created", name=name),
            "name": name,
            "phone": phone,
        }
    )



def _registered_phone_exists(phone: str) -> bool:
    """Kiểm tra tài khoản trực tiếp từ file thay vì chỉ dựa vào dữ liệu RAM."""
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    REGISTERED_PATIENT_PHONES.update(_load_registered_patient_phones())
    return normalized in REGISTERED_PATIENT_PHONES


def _appointment_to_payload(appointment) -> dict[str, object]:
    return {
        "id": int(appointment.id),
        "patient_name": str(appointment.patient_name),
        "phone": str(appointment.phone),
        "department": str(appointment.department),
        "appointment_date": str(appointment.appointment_date),
        "appointment_time": str(appointment.appointment_time),
        "symptoms": str(appointment.symptoms),
        "created_at": str(appointment.created_at),
    }


@app.post("/api/create-booking")
async def create_booking_api(request: Request) -> JSONResponse:
    """Đặt lịch bằng HTTP trực tiếp, không phụ thuộc callback WebSocket NiceGUI."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "message": "Dữ liệu gửi lên không hợp lệ."}, status_code=400)

    patient_name = str(payload.get("patient_name", "")).strip()
    phone = normalize_phone(str(payload.get("phone", "")))
    appointment_date = str(payload.get("appointment_date", "")).strip()
    appointment_time = str(payload.get("appointment_time", "")).strip()
    symptoms = str(payload.get("symptoms", "")).strip()

    if not patient_name or not phone or not appointment_date or not appointment_time or not symptoms:
        return JSONResponse(
            {"ok": False, "message": "Vui lòng nhập đầy đủ họ tên, số điện thoại, ngày, giờ và triệu chứng."},
            status_code=400,
        )

    if not _registered_phone_exists(phone):
        return JSONResponse(
            {
                "ok": False,
                "need_account": True,
                "message": "Số điện thoại này chưa có tài khoản. Vui lòng tạo tài khoản trước khi đặt lịch.",
            },
            status_code=403,
        )

    try:
        parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
        if parsed_date < date.today():
            raise ValueError("Ngày khám không được nhỏ hơn ngày hiện tại.")
        normalized_time = normalize_appointment_time(appointment_time)
        department_value, room_label, matched_phrases = infer_department_and_room_from_symptoms(symptoms)
    except ValueError as error:
        return JSONResponse({"ok": False, "message": str(error)}, status_code=400)

    try:
        appointment = store.create_appointment(
            patient_name=patient_name,
            phone=phone,
            department=department_value,
            appointment_date=appointment_date,
            appointment_time=normalized_time,
            symptoms=symptoms,
        )
        sync_robot_patient_profile(
            patient_name,
            phone,
            appointment=appointment,
            room_label=room_label,
            matched_phrases=matched_phrases,
        )
    except ValueError as error:
        return JSONResponse({"ok": False, "message": str(error)}, status_code=400)
    except Exception as error:
        logging.exception("Không thể hoàn tất đặt lịch: %s", error)
        return JSONResponse(
            {
                "ok": False,
                "message": "Không thể đồng bộ lịch khám. Hãy kiểm tra terminal và quyền ghi các file dữ liệu.",
            },
            status_code=500,
        )

    return JSONResponse(
        {
            "ok": True,
            "message": "Đặt khám thành công.",
            "appointment": _appointment_to_payload(appointment),
            "room_label": room_label,
            "matched_phrases": matched_phrases,
        }
    )


@app.get("/api/appointment-history")
async def appointment_history_api(request: Request) -> JSONResponse:
    phone = normalize_phone(str(request.query_params.get("phone", "")))
    if not phone:
        return JSONResponse({"ok": False, "message": "Vui lòng nhập số điện thoại."}, status_code=400)

    try:
        appointments = store.list_appointments_by_phone(phone, limit=20)
    except Exception as error:
        logging.exception("Không thể đọc lịch sử đặt lịch: %s", error)
        return JSONResponse({"ok": False, "message": "Không thể tải lịch sử đặt lịch."}, status_code=500)

    return JSONResponse(
        {
            "ok": True,
            "phone": phone,
            "appointments": [_appointment_to_payload(item) for item in appointments],
        }
    )


@app.post("/api/face-registration")
async def face_registration_api(request: Request) -> JSONResponse:
    payload = await request.json()
    patient_name = str(payload.get("patient_name", "")).strip()
    phone = str(payload.get("phone", "")).strip()
    image_data = str(payload.get("image_data", "")).strip()

    matched = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", image_data, flags=re.DOTALL)
    if not matched:
        return JSONResponse(
            {"ok": False, "message": "Ảnh chụp không hợp lệ. Vui lòng bật camera và chụp lại."},
            status_code=400,
        )

    mime_type = matched.group(1)
    base64_payload = matched.group(2)
    try:
        image_bytes = base64.b64decode(base64_payload, validate=True)
        saved = save_face_capture(patient_name, phone, image_bytes, mime_type)
    except ValueError as error:
        return JSONResponse({"ok": False, "message": str(error)}, status_code=400)
    except (OSError, json.JSONDecodeError, base64.binascii.Error):
        return JSONResponse(
            {"ok": False, "message": "Không thể lưu ảnh khuôn mặt. Vui lòng thử lại."},
            status_code=500,
        )

    return JSONResponse({"ok": True, **saved})


def build_dashboard() -> None:
    ui.add_head_html(
        """
        <style>
            html {
                scroll-behavior: smooth;
            }
            body {
                margin: 0;
                background:
                    radial-gradient(circle at top left, rgba(2, 132, 199, 0.25), transparent 28%),
                    radial-gradient(circle at bottom right, rgba(34, 197, 94, 0.22), transparent 24%),
                    linear-gradient(135deg, #eff6ff 0%, #f8fafc 45%, #ecfeff 100%);
            }
            .site-header {
                background: rgba(255, 255, 255, 0.96);
                border-bottom: 1px solid rgba(15, 23, 42, 0.08);
                box-shadow: 0 18px 38px rgba(15, 23, 42, 0.08);
            }
            .brand-cluster {
                background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(240,249,255,0.94));
                border: 1px solid rgba(14, 165, 233, 0.14);
                border-radius: 22px;
                box-shadow: 0 14px 32px rgba(14, 165, 233, 0.10);
                padding: 10px 14px;
            }
            .brand-chip {
                align-items: center;
                background: white;
                border-radius: 16px;
                box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
                display: inline-flex;
                justify-content: center;
                padding: 6px 10px;
            }
            .social-link {
                color: #073b5a;
                font-size: 16px;
                font-weight: 800;
                white-space: nowrap;
            }
            .social-logo {
                align-items: center;
                color: #073b5a;
                display: inline-flex;
                font-size: 20px;
                font-weight: 900;
                justify-content: center;
                line-height: 1;
                width: 22px;
            }
            .social-zalo {
                border: 1.5px solid #073b5a;
                border-radius: 4px;
                font-size: 9px;
                height: 16px;
                letter-spacing: -0.08em;
                width: 22px;
            }
            .header-search .q-field__control {
                height: 56px;
                border-radius: 999px;
                background: #f1f5f9;
            }
            .header-search .q-field__control:before,
            .header-search .q-field__control:after {
                border: 0 !important;
            }
            .booking-form .q-field__native,
            .booking-form .q-field__input,
            .booking-form .q-field__prefix,
            .booking-form .q-field__suffix,
            .booking-form .q-field__append,
            .booking-form .q-field__prepend,
            .booking-form .q-field__marginal,
            .booking-form .q-select__dropdown-icon,
            .booking-form input,
            .booking-form textarea {
                color: #f8fafc !important;
            }
            .booking-form .q-field__label,
            .booking-form .q-placeholder {
                color: rgba(226, 232, 240, 0.78) !important;
            }
            .booking-form .q-field--outlined .q-field__control:before,
            .booking-form .q-field--outlined .q-field__control:after {
                border-color: rgba(148, 163, 184, 0.55) !important;
            }
            .booking-form .q-field--focused .q-field__control:after,
            .booking-form .q-field--highlighted .q-field__control:after {
                border-color: #22d3ee !important;
                border-width: 2px;
            }
            .booking-form .q-field__control {
                background: rgba(15, 23, 42, 0.55);
                border-radius: 16px;
            }
            .booking-form .q-textarea .q-field__native {
                min-height: 140px;
            }
            .main-nav .q-btn {
                color: #073b5a !important;
                font-size: 18px;
                font-weight: 800;
                letter-spacing: 0.01em;
                padding: 18px 10px;
                border-radius: 0;
                white-space: nowrap;
            }
            .main-nav .q-btn__content {
                align-items: center;
                display: inline-flex;
                flex-direction: row !important;
                flex-wrap: nowrap;
                gap: 8px;
                white-space: nowrap;
            }
            .main-nav .q-btn .q-icon {
                margin-left: 6px;
            }
            .language-trigger .q-btn__content {
                gap: 10px;
            }
            .main-nav .q-btn:before {
                box-shadow: none;
            }
            .main-nav .q-btn:hover {
                color: #0284c7 !important;
                background: rgba(14, 165, 233, 0.08);
            }
            .main-nav .q-btn:hover:after {
                content: "";
                position: absolute;
                left: 12px;
                right: 12px;
                bottom: 0;
                height: 3px;
                background: #22c3ee;
            }
            .nav-menu {
                min-width: 250px;
                border-top: 3px solid #22c3ee;
                border-radius: 0 0 10px 10px;
                box-shadow: 0 18px 36px rgba(15, 23, 42, 0.14);
            }
            .nav-menu .q-item {
                min-height: 56px;
                color: #083955;
                font-weight: 700;
                font-size: 16px;
            }
            .nav-menu .q-item:hover {
                background: rgba(14, 165, 233, 0.08);
                color: #0284c7;
            }
            .language-menu {
                min-width: 230px;
                border-radius: 18px;
                box-shadow: 0 18px 36px rgba(15, 23, 42, 0.16);
                padding: 8px 0;
            }
            .language-menu .q-item {
                min-height: 58px;
                color: #0f4c81;
                font-size: 18px;
                font-weight: 800;
            }
            .facility-map iframe {
                width: 100%;
                height: 420px;
                border: 0;
                border-radius: 28px;
                box-shadow: 0 24px 48px rgba(15, 23, 42, 0.14);
            }
            .award-gallery img {
                display: block;
                width: 100%;
                height: 260px;
                object-fit: cover;
                border-radius: 28px;
                box-shadow: 0 20px 42px rgba(15, 23, 42, 0.14);
            }
            .hospital-gallery .main-photo img {
                height: 460px;
                object-fit: cover;
                border-radius: 18px;
            }
            .hospital-gallery .side-photo img {
                height: 146px;
                object-fit: cover;
                border-radius: 14px;
            }
            .hospital-card {
                box-shadow: 0 16px 38px rgba(15, 23, 42, 0.16);
            }
            .floating-contact-panel {
                position: fixed;
                right: 24px;
                bottom: 24px;
                z-index: 1400;
                align-items: flex-end;
            }
            .floating-contact-row {
                display: flex;
                gap: 14px;
                margin-bottom: 14px;
                opacity: 0;
                pointer-events: none;
                transform: translateY(10px) scale(0.96);
                transform-origin: bottom right;
                transition: opacity 0.22s ease, transform 0.22s ease;
            }
            .floating-contact-panel:hover .floating-contact-row {
                opacity: 1;
                pointer-events: auto;
                transform: translateY(0) scale(1);
            }
            .floating-mini-btn .q-btn__content,
            .floating-main-btn .q-btn__content {
                flex-direction: column;
                gap: 4px;
            }
            .floating-mini-btn {
                width: 74px;
                height: 74px;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.97);
                box-shadow: 0 16px 30px rgba(15, 23, 42, 0.20);
                color: #0f4c81;
                font-weight: 900;
            }
            .floating-mini-btn .q-icon {
                font-size: 30px;
            }
            .floating-mini-label {
                font-size: 11px;
                font-weight: 900;
                line-height: 1.05;
                text-align: center;
            }
            .floating-main-btn {
                width: 78px;
                height: 78px;
                border-radius: 999px;
                background: linear-gradient(135deg, #ffbf5f, #fb923c);
                box-shadow: 0 18px 32px rgba(249, 115, 22, 0.35);
                color: white;
            }
            .floating-main-btn .q-icon {
                font-size: 36px;
            }
            .floating-main-phone-icon,
            .floating-main-close-icon {
                font-size: 36px;
                line-height: 1;
            }
            .floating-main-close-icon {
                display: none;
                font-weight: 900;
            }
            .floating-contact-panel:hover .floating-main-phone-icon {
                display: none;
            }
            .floating-contact-panel:hover .floating-main-close-icon {
                display: inline-flex;
            }
        </style>
        """
    )

    ui.query("body").classes("text-slate-900")
    search_index = [
        {"id": "intro-section", "keywords": ["gioi thieu", "aurora", "trung tam y te"]},
        {"id": "doctor-team-section", "keywords": ["doi ngu bac si", "bac si"]},
        {"id": "specialty-section", "keywords": ["chuyen khoa", "khoa kham"]},
        {"id": "guide-section", "keywords": ["huong dan", "robot", "stt", "checkin"]},
    ]
    search_index.extend(
        {"id": doctor["section_id"], "keywords": doctor["search_terms"]}
        for doctor in DOCTOR_TEAM
    )
    search_index.extend(
        {"id": specialty["section_id"], "keywords": specialty["search_terms"]}
        for specialty in SPECIALTY_SECTIONS
    )
    ui.add_head_html(
        f"""
        <script>
            window.robotSearchIndex = {json.dumps(search_index, ensure_ascii=False)};
            window.normalizeRobotSearch = function(text) {{
                return (text || '')
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .replace(/[^a-z0-9]+/g, ' ')
                    .trim();
            }};
            window.runRobotHeaderSearch = function() {{
                const input = document.querySelector('.header-search input');
                if (!input) return;
                const query = window.normalizeRobotSearch(input.value);
                if (!query) return;
                const targets = window.robotSearchIndex || [];
                const match = targets.find(item =>
                    (item.keywords || []).some(keyword => {{
                        const normalizedKeyword = window.normalizeRobotSearch(keyword);
                        return normalizedKeyword.includes(query) || query.includes(normalizedKeyword);
                    }})
                );
                if (!match) return;
                const target = document.getElementById(match.id);
                if (target) {{
                    target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                }}
            }};
            document.addEventListener('keydown', function(event) {{
                const input = document.querySelector('.header-search input');
                if (!input) return;
                if (event.key === 'Enter' && document.activeElement === input) {{
                    event.preventDefault();
                    window.runRobotHeaderSearch();
                }}
            }});
        </script>
        """
    )

    with ui.column().classes("min-h-screen w-full justify-between"):
        with ui.column().classes("w-full"):
            build_site_header()

            with ui.column().classes("w-full flex-1 items-center px-6 py-8 md:px-10 xl:px-16"):
                build_hospital_detail_header()
                build_facility_overview()

        build_site_footer()

    build_floating_contact_buttons()


def build_site_header() -> None:
    global account_dialog
    account_dialog = ui.dialog()
    with account_dialog:
        build_account_registration_form("w-[420px] max-w-[92vw] rounded-3xl p-6 shadow-2xl")

    def open_search_target(query: str) -> None:
        match = search_section_target(query)
        if match is None:
            ui.notify("Chưa tìm thấy bác sĩ hoặc chuyên khoa phù hợp.", color="warning")
            return
        target_id, _normalized_query = match
        ui.run_javascript(
            f"const target = document.getElementById('{target_id}'); if (target) {{ target.scrollIntoView({{behavior:'smooth', block:'start'}}); }}"
        )

    with ui.column().classes("site-header w-full items-center"):
        with ui.row().classes(
            "w-full max-w-[1800px] flex-nowrap items-center gap-5 overflow-x-auto px-6 py-5 md:px-10 xl:px-16"
        ):
            with ui.row().classes("brand-cluster shrink-0 items-center gap-3"):
                with ui.row().classes("brand-chip"):
                    ui.image("/images/aurora.png?v=5").classes("h-14 w-[190px] object-contain")
                with ui.row().classes("brand-chip"):
                    ui.image("/images/hcmute.png?v=1").classes("h-12 w-12 object-contain")
                with ui.row().classes("brand-chip"):
                    ui.image("/images/aurora1.png?v=2").classes("h-14 w-[140px] object-contain")

            with ui.row().classes("shrink-0 items-center gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("♪").classes("social-logo")
                    ui.label("Tiktok").classes("social-link")
                ui.separator().props("vertical").classes("h-5 shrink-0")
                with ui.row().classes("items-center gap-2 cursor-pointer").on(
                    "click", lambda: ui.run_javascript("window.open('https://www.facebook.com/hcmute.acislab', '_blank')")
                ):
                    ui.label("f").classes("social-logo")
                    ui.label("Facebook").classes("social-link")
                ui.separator().props("vertical").classes("h-5 shrink-0")
                with ui.row().classes("items-center gap-2"):
                    ui.label("Zalo").classes("social-logo social-zalo")
                    ui.label("Zalo").classes("social-link")
                ui.separator().props("vertical").classes("h-5 shrink-0")
                with ui.row().classes("items-center gap-2 cursor-pointer").on(
                    "click", lambda: ui.run_javascript("window.open('https://www.youtube.com/@acislab2767', '_blank')")
                ):
                    ui.icon("smart_display").classes("text-xl text-sky-950")
                    ui.label("Youtube").classes("social-link")

            ui.html(
                f"""
                <a href="/account" style="display:inline-flex;align-items:center;gap:9px;white-space:nowrap;
                    border:1.5px solid #38bdf8;border-radius:999px;padding:11px 20px;text-decoration:none;
                    color:#3b82f6;font-weight:800;background:white;">
                    <span style="font-size:20px;line-height:1;">👤</span>{tr('account')}
                </a>
                """,
                sanitize=False,
            ).classes("shrink-0")
            with ui.button().props("outline no-caps icon-right=keyboard_arrow_down").classes(
                "language-trigger shrink-0 rounded-2xl border-slate-300 px-3 py-2 text-base font-bold text-slate-800"
            ):
                ui.label("🇻🇳").classes("text-2xl")
                with ui.menu().classes("language-menu"):
                    ui.menu_item("🇻🇳  Tiếng Việt", on_click=lambda: switch_language("vi"))
                    ui.menu_item("🇬🇧  English", on_click=lambda: switch_language("en"))

        with ui.row().classes(
            "w-full max-w-[1800px] flex-nowrap items-center gap-6 border-t border-slate-100 px-6 py-3 md:px-10 xl:px-16"
        ):
            ui.input(placeholder="Tìm kiếm bệnh viện, chuyên khoa, bác sĩ...").props("borderless dense").classes(
                "header-search w-[320px] shrink-0 max-w-full"
            )
            build_navigation()


def build_navigation() -> None:
    with ui.row().classes(
        "main-nav min-w-0 flex-1 flex-nowrap items-center justify-between gap-2 overflow-x-auto"
    ):
        for title, target in HEADER_NAV_LINKS:
            if target.startswith("#"):
                ui.button(
                    title,
                    on_click=lambda target_id=target[1:]: ui.run_javascript(
                        f"const target = document.getElementById('{target_id}'); if (target) {{ target.scrollIntoView({{behavior:'smooth', block:'start'}}); }}"
                    ),
                ).props("flat no-caps")
            else:
                ui.button(title, on_click=lambda path=target: ui.navigate.to(path)).props("flat no-caps")


def build_floating_contact_buttons() -> None:
    with ui.column().classes("floating-contact-panel"):
        with ui.row().classes("floating-contact-row"):
            with ui.button(on_click=lambda: ui.notify("Tổng đài liên hệ: 0706004634", color="primary")).props(
                "round unelevated"
            ).classes("floating-mini-btn"):
                ui.icon("support_agent")
                ui.label("Care 247").classes("floating-mini-label text-emerald-600")

            with ui.button(
                on_click=lambda: ui.run_javascript("window.open('https://www.facebook.com/hcmute.acislab', '_blank')")
            ).props("round unelevated").classes("floating-mini-btn"):
                ui.icon("chat")
                ui.label("Messenger").classes("floating-mini-label text-sky-500")

            with ui.button(on_click=lambda: ui.notify("Zalo đang cập nhật liên kết chính thức.", color="info")).props(
                "round unelevated"
            ).classes("floating-mini-btn"):
                ui.label("Zalo").classes("text-xl font-black text-sky-600")

        with ui.button(on_click=lambda: ui.run_javascript("window.location.href='tel:0706004634'")).props(
            "round unelevated"
        ).classes("floating-main-btn"):
            ui.icon("call").classes("floating-main-phone-icon")
            ui.label("×").classes("floating-main-close-icon")


def build_site_footer() -> None:
    with ui.column().classes("w-full items-center justify-center px-6 pb-10 pt-6 text-center"):
        with ui.card().classes("mx-auto w-auto max-w-[92vw] rounded-3xl border-0 bg-white/75 px-8 py-5 shadow-none"):
            ui.label("© 2026 ACIS Lab — Advanced Control & Intelligent System").classes(
                "text-base font-bold text-slate-700"
            )
            ui.label("Designed by Nguyen Vu Trung Hieu and Duong Minh Hoang").classes(
                "mt-1 text-sm font-medium text-slate-500"
            )


def build_award_gallery() -> None:
    images = [
        "/images/Vinh%20danh%203.jpg?v=1",
        "/images/Vinh%20danh%204.jpg?v=1",
        "/images/Vinh%20danh%205.jpg?v=1",
    ]
    with ui.row().classes("award-gallery mb-8 w-full max-w-[1800px] gap-6 max-[900px]:flex-col"):
        for image_path in images:
            with ui.card().classes("flex-1 border-0 bg-white/80 p-2 shadow-none"):
                ui.image(image_path).classes("w-full")


def show_booking_success(appointment, room_label: str = "") -> None:
    success_dialog = ui.dialog()
    with success_dialog, ui.card().classes("w-[620px] max-w-[94vw] rounded-3xl p-8 text-center shadow-2xl"):
        ui.icon("check_circle").classes("mx-auto text-7xl text-emerald-500")
        ui.label("Đặt khám thành công").classes("mt-4 text-3xl font-black text-slate-900")
        ui.label(f"Số thứ tự của bạn: {appointment.id}").classes(
            "mt-3 rounded-full bg-cyan-50 px-5 py-3 text-xl font-black text-cyan-700"
        )
        ui.label(
            "HÃY GẶP ROBOT AURORA Ở TRƯỚC CỔNG BỆNH VIỆN "
            "VÀ BÁO SỐ THỨ TỰ CHO ROBOT NHÉ. XIN CẢM ƠN"
        ).classes("mt-5 text-xl font-black leading-9 text-slate-900")
        with ui.card().classes("mt-6 w-full rounded-2xl bg-slate-50 p-5 text-left shadow-none"):
            ui.label("Thông tin bệnh nhân").classes("text-lg font-black text-slate-900")
            ui.label(f"Họ và tên: {appointment.patient_name}").classes("mt-3 text-base text-slate-700")
            ui.label(f"Số điện thoại: {appointment.phone}").classes("text-base text-slate-700")
            ui.label(f"Khoa khám: {appointment.department}").classes("text-base text-slate-700")
            ui.label(f"Phòng khám: {room_label or 'Sẽ được cập nhật tại quầy'}").classes("text-base font-bold text-cyan-700")
            ui.label(f"Ngày khám: {appointment.appointment_date}").classes("text-base text-slate-700")
            ui.label(f"Giờ khám: {appointment.appointment_time}").classes("text-base text-slate-700")
            ui.label(f"Triệu chứng: {appointment.symptoms or 'Chưa ghi chú'}").classes("text-base text-slate-700")
        ui.button("Tôi đã hiểu", on_click=success_dialog.close).props("unelevated no-caps").classes(
            "mt-6 rounded-full bg-cyan-500 px-10 py-3 text-base font-bold text-white"
        )
    success_dialog.open()


def build_booking_dialog():
    ui.add_head_html(
        """
        <style>
            .booking-face-shell {
                display: grid;
                gap: 14px;
            }
            .booking-face-video-shell {
                position: relative;
                overflow: hidden;
                border-radius: 24px;
                background: linear-gradient(135deg, #020617, #0f172a);
                min-height: 240px;
                box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.18);
            }
            .booking-face-video,
            .booking-face-preview {
                width: 100%;
                height: 100%;
                min-height: 240px;
                display: block;
                object-fit: cover;
            }
            .booking-face-preview {
                display: none;
            }
            .booking-face-status {
                border-radius: 18px;
                background: rgba(8, 145, 178, 0.12);
                color: #cffafe;
                font-size: 14px;
                font-weight: 700;
                line-height: 1.6;
                min-height: 54px;
                padding: 12px 14px;
            }
            .booking-face-hint {
                color: #cbd5e1;
                font-size: 13px;
                line-height: 1.6;
            }
        </style>
        <script>
            window.bookingFaceState = window.bookingFaceState || {stream: null};

            window.startBookingFaceCamera = async function () {
                const status = document.getElementById('booking_face_status');
                const video = document.getElementById('booking_face_video');
                const preview = document.getElementById('booking_face_preview');
                if (!status || !video || !preview) return;
                try {
                    if (window.bookingFaceState.stream) {
                        window.bookingFaceState.stream.getTracks().forEach(track => track.stop());
                    }
                    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
                    window.bookingFaceState.stream = stream;
                    video.srcObject = stream;
                    preview.style.display = 'none';
                    video.style.display = 'block';
                    status.textContent = 'Camera đã bật trong phần đặt lịch. Bạn có thể chụp ảnh khuôn mặt ngay tại đây.';
                } catch (error) {
                    status.textContent = 'Không thể mở camera. Hãy dùng localhost hoặc HTTPS và cho phép trình duyệt truy cập camera.';
                }
            };

            window.stopBookingFaceCamera = function () {
                const status = document.getElementById('booking_face_status');
                const video = document.getElementById('booking_face_video');
                if (window.bookingFaceState.stream) {
                    window.bookingFaceState.stream.getTracks().forEach(track => track.stop());
                    window.bookingFaceState.stream = null;
                }
                if (video) {
                    video.srcObject = null;
                }
                if (status) {
                    status.textContent = 'Camera đã tắt. Bạn vẫn có thể đặt lịch, hoặc bật lại để chụp ảnh khuôn mặt.';
                }
            };

            window.captureBookingFaceImage = async function () {
                const status = document.getElementById('booking_face_status');
                const video = document.getElementById('booking_face_video');
                const canvas = document.getElementById('booking_face_canvas');
                const preview = document.getElementById('booking_face_preview');
                const patientName = arguments[0] || '';
                const phone = arguments[1] || '';
                if (!status || !video || !canvas || !preview) return;

                if (!patientName.trim() || !phone.trim()) {
                    status.textContent = 'Vui lòng nhập họ tên và số điện thoại trong form đặt lịch trước khi chụp ảnh khuôn mặt.';
                    return;
                }
                if (!window.bookingFaceState.stream || !video.videoWidth) {
                    status.textContent = 'Bạn cần bật camera trước khi chụp ảnh.';
                    return;
                }

                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const context = canvas.getContext('2d');
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const imageData = canvas.toDataURL('image/jpeg', 0.92);
                preview.src = imageData;
                preview.style.display = 'block';
                video.style.display = 'none';
                status.textContent = 'Đang lưu ảnh khuôn mặt...';

                try {
                    const response = await fetch('/api/face-registration', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            patient_name: patientName,
                            phone: phone,
                            image_data: imageData,
                        }),
                    });
                    const result = await response.json();
                    if (!response.ok || !result.ok) {
                        throw new Error(result.message || 'Không thể lưu ảnh khuôn mặt.');
                    }
                    status.textContent = `Đã lưu ảnh khuôn mặt cho ${result.patient_name}. Tổng số ảnh đã lưu: ${result.capture_count}.`;
                } catch (error) {
                    preview.style.display = 'none';
                    video.style.display = 'block';
                    status.textContent = error.message || 'Không thể lưu ảnh khuôn mặt.';
                }
            };
        </script>
        """
    )
    booking_dialog = ui.dialog()
    with booking_dialog, ui.card().classes("booking-form w-[560px] max-w-[94vw] rounded-3xl bg-slate-950 p-7 text-white"):
        ui.label("Đặt khám ngay").classes("text-2xl font-black")
        ui.label("Điền thông tin để bệnh viện xác nhận lịch khám.").classes("mt-1 text-sm text-slate-300")

        patient_name = ui.input("Họ và tên").props("outlined dense dark color=cyan-4 id=booking_patient_name").classes("mt-5 w-full")
        phone = ui.input("Số điện thoại").props("outlined dense dark color=cyan-4 id=booking_patient_phone").classes("w-full")
        appointment_date = (
            ui.input("Ngày khám", value=str(date.today()))
            .props("outlined dense type=date dark color=cyan-4")
            .classes("w-full")
        )
        appointment_time = (
            ui.input("Giờ khám", placeholder="HH:MM", value="08:00")
            .props("outlined dense dark color=cyan-4 maxlength=5")
            .classes("w-full")
        )
        ui.label("Triệu chứng ban đầu").classes("mt-1 text-sm font-bold text-cyan-200")
        ui.label("Bạn nhập triệu chứng như ban đầu, hệ thống sẽ so khớp với bảng triệu chứng trên web admin để tự xếp khoa và phòng khám.").classes(
            "text-xs leading-5 text-slate-300"
        )
        symptoms = ui.textarea("Nhập triệu chứng", placeholder="Ví dụ: sốt, đau đầu, khó thở nhẹ")
        symptoms.props("outlined dark color=cyan-4")
        symptoms.classes("w-full")
        with ui.card().classes("mt-2 w-full rounded-3xl border border-cyan-400/20 bg-slate-900/60 p-4 shadow-none"):
            ui.label("Đăng ký khuôn mặt khi đặt lịch").classes("text-base font-black text-cyan-200")
            ui.label(
                "Bạn có thể bật camera và lưu ảnh khuôn mặt ngay trong lúc đặt lịch để dùng cho bước xác minh với robot sau này."
            ).classes("mt-2 text-xs leading-5 text-slate-300")
            ui.html(
                """
                <div class="booking-face-shell">
                    <div class="booking-face-video-shell">
                        <video id="booking_face_video" class="booking-face-video" autoplay playsinline muted></video>
                        <img id="booking_face_preview" class="booking-face-preview" alt="Ảnh khuôn mặt đã chụp trong form đặt lịch" />
                        <canvas id="booking_face_canvas" style="display:none;"></canvas>
                    </div>
                    <div id="booking_face_status" class="booking-face-status">
                        Bạn có thể bỏ qua bước này nếu chỉ muốn đặt lịch. Nếu dùng, hãy nhập họ tên và số điện thoại trước rồi bấm "Bật camera".
                    </div>
                    <div class="booking-face-hint">
                        Gợi ý: nên chụp ảnh chính diện, đủ sáng, không ngược sáng để sau này robot xác minh ổn định hơn.
                    </div>
                </div>
                """
            ).classes("mt-3 w-full")
            with ui.row().classes("mt-4 w-full flex-wrap gap-3"):
                ui.button(
                    "Bật camera",
                    on_click=lambda: ui.run_javascript(
                        "window.startBookingFaceCamera && window.startBookingFaceCamera()"
                    ),
                ).props("unelevated no-caps icon=videocam").classes(
                    "rounded-full bg-cyan-500 px-4 py-3 font-bold text-white"
                )
                ui.button(
                    "Chụp và lưu ảnh",
                    on_click=lambda: ui.run_javascript(
                        f"window.captureBookingFaceImage && window.captureBookingFaceImage({json.dumps(patient_name.value or '')}, {json.dumps(phone.value or '')})"
                    ),
                ).props("unelevated no-caps icon=photo_camera").classes(
                    "rounded-full bg-emerald-500 px-4 py-3 font-bold text-white"
                )
                ui.button(
                    "Tắt camera",
                    on_click=lambda: ui.run_javascript(
                        "window.stopBookingFaceCamera && window.stopBookingFaceCamera()"
                    ),
                ).props("outline no-caps icon=videocam_off").classes(
                    "rounded-full border-slate-500 px-4 py-3 font-bold text-slate-200"
                )

        def submit_booking() -> None:
            if not patient_has_account(phone.value or ""):
                ui.notify("Bạn cần tạo tài khoản bằng số điện thoại này trước khi đặt lịch khám.", color="negative")
                return

            try:
                normalized_time = normalize_appointment_time(appointment_time.value or "")
                department_value, room_label, matched_phrases = infer_department_and_room_from_symptoms(symptoms.value or "")
            except ValueError as error:
                ui.notify(str(error), color="negative")
                return

            try:
                appointment = store.create_appointment(
                    patient_name=patient_name.value or "",
                    phone=phone.value or "",
                    department=department_value,
                    appointment_date=appointment_date.value or "",
                    appointment_time=normalized_time,
                    symptoms=symptoms.value or "",
                )
            except ValueError as error:
                ui.notify(str(error), color="negative")
                return

            sync_robot_patient_profile(
                patient_name.value or "",
                phone.value or "",
                appointment=appointment,
                room_label=room_label,
                matched_phrases=matched_phrases,
            )

            if "appointments_table" in globals():
                appointments_table.rows = format_appointments(store.list_appointments())
                appointments_table.update()
            booking_dialog.close()
            show_booking_success(appointment, room_label=room_label)
            ui.notify(
                f"Đã xếp {department_value} - phòng {room_label} dựa trên triệu chứng: {', '.join(matched_phrases)}",
                color="positive",
            )

        with ui.row().classes("mt-3 w-full gap-3"):
            ui.button("Đóng", on_click=booking_dialog.close).props("flat no-caps").classes("flex-1 text-slate-200")
            ui.button("Xác nhận đặt lịch", on_click=submit_booking).props("unelevated no-caps").classes(
                "flex-1 rounded-full bg-cyan-500 py-3 font-bold text-white"
            )

    return booking_dialog


def build_hospital_detail_header() -> None:
    # Đặt khám dùng trang /booking và API HTTP trực tiếp.

    with ui.row().classes("w-full max-w-[1680px] items-center gap-3 self-center px-2 pb-6 text-lg font-bold"):
        ui.label("Trang chủ").classes("text-slate-900")
        ui.icon("chevron_right").classes("text-slate-400")
        ui.label("AURORA - Trung tâm y tế kỹ thuật cao").classes("text-cyan-500")

    with ui.row().classes("hospital-gallery w-full max-w-[1680px] items-stretch gap-7 max-[1100px]:flex-col"):
        with ui.card().classes(
            "hospital-card w-[400px] max-w-full shrink-0 rounded-3xl border-0 bg-white p-5 max-[1100px]:w-full"
        ):
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button(icon="favorite_border").props("flat round").classes("bg-slate-50 text-sky-900")
                ui.button(icon="share").props("flat round").classes("bg-slate-50 text-sky-900")

            ui.image("/images/logo truong.png?v=2").classes("mx-auto h-20 w-20 object-contain")
            with ui.row().classes("mt-4 items-center justify-center gap-1"):
                ui.label("AURORA - Trung tâm y tế kỹ thuật cao").classes("text-center text-xl font-black leading-7 text-cyan-500")
                ui.icon("verified").classes("text-cyan-500")

            with ui.row().classes("mt-3 items-center justify-center gap-2"):
                ui.label("(4.7/5)").classes("text-base font-bold text-orange-400")
                ui.label("★ ★ ★ ★ ★").classes("text-xl tracking-wider text-orange-400")
                ui.link("0 đánh giá", "#").classes("text-base text-slate-900 underline")

            ui.separator().classes("my-4")

            ui.label(f"Địa chỉ: {FACILITY_ADDRESS}").classes("text-base leading-6 text-slate-800")
            hospital_status_label = ui.label(opening_status_text()).classes("mt-3 text-base font-bold text-slate-800")
            ui.label("Tổng đài đặt khám nhanh: 0706004634").classes("mt-3 text-base font-bold text-slate-800")
            ui.html(
                """
                <a href="/booking" style="display:block;width:100%;box-sizing:border-box;margin-top:20px;
                    border-radius:999px;background:#22c3ee;color:white;text-align:center;text-decoration:none;
                    padding:13px 18px;font-size:16px;font-weight:900;">Đặt khám ngay</a>
                """,
                sanitize=False,
            ).classes("w-full")

        with ui.row().classes("min-w-0 flex-1 gap-4 max-[1100px]:w-full max-[900px]:flex-col"):
            with ui.column().classes("min-w-0 flex-1 gap-4"):
                ui.image("/images/Vinh%20danh%203.jpg?v=3").classes("main-photo w-full")
            with ui.column().classes("w-[285px] shrink-0 gap-4 max-[900px]:w-full max-[900px]:flex-row max-[700px]:flex-col"):
                ui.image("/images/Vinh%20danh%204.jpg?v=3").classes("side-photo w-full")
                ui.image("/images/Vinh%20danh%205.jpg?v=3").classes("side-photo w-full")
                face_gallery_image = ui.image(ROBOT_FACE_STATES[0]["source"]).classes(
                    "side-photo w-full bg-slate-950 p-2 object-contain"
                )
                attach_robot_face_rotation(face_gallery_image)


def build_hero() -> None:
    with ui.card().classes(
        "w-full flex-1 border-0 bg-white/80 p-8 shadow-2xl shadow-cyan-100 backdrop-blur"
    ):
        with ui.row().classes("w-full items-center gap-5 max-[700px]:flex-col max-[700px]:items-start"):
            ui.image("/images/logo truong.png?v=2").classes(
                "h-16 w-16 rounded-2xl object-contain bg-white p-2 shadow-md"
            )
            ui.image("/images/aurora1.png?v=1").classes(
                "h-20 w-[320px] max-w-full rounded-2xl object-contain bg-slate-950 shadow-lg shadow-cyan-100"
            )
        ui.label("Đặt lịch khám bệnh trực tuyến").classes("mt-3 text-4xl font-black leading-tight text-slate-900")
        ui.label(
            "Bệnh nhân có thể tự chọn khoa, ngày giờ khám và để lại triệu chứng ban đầu. "
            "Lịch hẹn được lưu vào SQLite để bệnh viện theo dõi."
        ).classes("mt-4 max-w-2xl text-base leading-7 text-slate-600")

        total_label = ui.label(f"{store.count_appointments()} lịch hẹn đã được tạo").classes(
            "mt-6 inline-flex rounded-full bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-700"
        )

        with ui.row().classes("mt-8 w-full gap-4 max-[700px]:flex-col"):
            stat_card("Mở cho mọi người", "Truy cập qua IP nội bộ hoặc public host")
            stat_card("Phản hồi nhanh", "Lưu lịch ngay sau khi bệnh nhân gửi form")
            stat_card("Dễ tích hợp", "Có thể nối tiếp sang robot hoặc hệ thống quản lý")

        def refresh_total() -> None:
            total_label.set_text(f"{store.count_appointments()} lịch hẹn đã được tạo")

        ui.timer(5.0, refresh_total)


def stat_card(title: str, body: str):
    card = ui.card().classes("min-w-[180px] flex-1 border border-cyan-100 bg-cyan-50/70 p-4 shadow-sm")
    with card:
        ui.label(title).classes("text-sm font-bold text-slate-900")
        ui.label(body).classes("mt-2 text-sm leading-6 text-slate-600")
    return card


def build_facility_overview() -> None:
    services = [
        ("event_available", "Đặt khám theo chuyên khoa"),
        ("stethoscope", "Đặt khám theo bác sĩ"),
        ("vaccines", "Đặt lịch tiêm chủng"),
        ("face_retouching_natural", "Khám Tạo Hình Thẩm Mỹ"),
    ]
    map_src = (
        "https://www.google.com/maps?q="
        + FACILITY_MAP_QUERY.replace(" ", "+")
        + "&output=embed"
    )

    with ui.row().classes("mt-8 w-full max-w-[1680px] items-start gap-8 max-[1100px]:flex-col"):
        with ui.column().classes("min-w-0 flex-[2]"):
            ui.label("Địa chỉ").classes("text-3xl font-black text-slate-900")
            with ui.card().classes("mt-4 w-full rounded-3xl border-0 bg-white/90 p-6 shadow-xl shadow-cyan-100"):
                with ui.row().classes("items-start gap-3"):
                    ui.icon("location_on").classes("mt-1 text-3xl text-cyan-600")
                    with ui.column().classes("gap-1"):
                        ui.label("AURORA - Trung tâm y tế kỹ thuật cao").classes("text-xl font-black text-slate-900")
                        ui.label(FACILITY_ADDRESS).classes("text-base leading-7 text-slate-600")
                        ui.link("Mở địa chỉ trên Google Maps", f"https://www.google.com/maps/search/?api=1&query={FACILITY_MAP_QUERY.replace(' ', '+')}").classes(
                            "mt-2 font-bold text-cyan-700"
                        )

            ui.label("Mô tả").classes("mt-8 text-3xl font-black text-slate-900")
            ui.label(
                "AURORA hỗ trợ bệnh nhân đặt lịch khám trực tuyến, chọn chuyên khoa, "
                "đặt lịch theo bác sĩ và theo dõi thông tin lịch hẹn nhanh chóng. "
                "Hệ thống hướng tới trải nghiệm y tế hiện đại, rõ ràng và thuận tiện cho bệnh nhân."
            ).classes("mt-3 text-lg leading-8 text-slate-700")

            ui.label("Các dịch vụ").classes("mt-8 text-3xl font-black text-slate-900")
            with ui.row().classes("mt-4 w-full gap-5 max-[900px]:flex-col"):
                for icon_name, title in services:
                    with ui.card().classes("min-h-[170px] flex-1 items-center justify-center rounded-3xl border-0 bg-white/95 p-5 text-center shadow-lg shadow-slate-200"):
                        ui.icon(icon_name).classes("text-5xl text-cyan-500")
                        ui.label(title).classes("mt-4 text-lg font-bold leading-6 text-slate-800")

            build_robot_description()
            build_doctor_team()

            with ui.row().classes("mt-8 gap-8 text-xl font-black text-slate-900 max-[700px]:flex-col"):
                ui.label("Giới thiệu")
                ui.label("Chuyên khoa")
                ui.label("Bảng giá")
                ui.label("Hướng dẫn đi khám")

        with ui.column().classes("facility-map min-w-[360px] flex-1 max-[1100px]:w-full"):
            ui.html(
                f"""
                <iframe
                    loading="lazy"
                    referrerpolicy="no-referrer-when-downgrade"
                    src="{map_src}">
                </iframe>
                """
            ).classes("w-full")
            with ui.card().classes("mt-4 w-full rounded-3xl border-0 bg-white/90 p-5 shadow-lg shadow-cyan-100"):
                ui.label("Thông tin liên hệ").classes("text-xl font-black text-slate-900")
                ui.label("Tổng đài đặt khám nhanh: 0706004634").classes("mt-2 text-base text-slate-600")
                contact_status_label = ui.label(opening_status_text()).classes("text-base text-slate-600")
                ui.html(
                    """
                    <a href="/booking" style="display:block;width:100%;box-sizing:border-box;margin-top:16px;
                        border-radius:999px;background:#22c3ee;color:white;text-align:center;text-decoration:none;
                        padding:13px 18px;font-size:16px;font-weight:800;">Đặt khám ngay</a>
                    """,
                    sanitize=False,
                ).classes("w-full")

    def refresh_opening_status() -> None:
        status = opening_status_text()
        hospital_status_label.set_text(status)
        contact_status_label.set_text(status)

    ui.timer(60.0, refresh_opening_status)


def build_robot_description() -> None:
    robot_features = [
        (
            "Hướng dẫn di chuyển",
            "Dẫn người bệnh, đặc biệt là người khiếm thị, đến đúng phòng khám hoặc khu vực chức năng.",
        ),
        (
            "Tư vấn và hỗ trợ thông tin",
            "Cung cấp thông tin về lịch khám, quy trình khám bệnh và giải đáp thắc mắc thông qua giọng nói.",
        ),
        (
            "Nhắc lịch và hỗ trợ bệnh nhân",
            "Nhắc lịch khám, uống thuốc và hỗ trợ theo dõi cơ bản trong thời gian lưu trú.",
        ),
        (
            "Di chuyển an toàn",
            "Tự động phát hiện và tránh chướng ngại vật, đảm bảo an toàn khi hoạt động trong môi trường bệnh viện.",
        ),
    ]

    with ui.card().classes("mt-8 w-full rounded-3xl border-0 bg-slate-950 p-7 text-white shadow-2xl shadow-cyan-100"):
        with ui.row().classes("items-start gap-5 max-[800px]:flex-col"):
            with ui.column().classes("w-[260px] shrink-0 gap-3 max-[800px]:w-full"):
                ui.image("/images/robotdatnguoi.webp?v=3").classes(
                    "h-[220px] w-[260px] rounded-3xl object-cover max-[800px]:w-full"
                )
                with ui.card().classes("rounded-3xl border border-cyan-400/20 bg-slate-900/80 p-3 shadow-none"):
                    ui.label("Trạng thái mặt robot").classes("text-sm font-black uppercase tracking-[0.24em] text-cyan-200")
                    robot_face_status = ui.label(ROBOT_FACE_STATES[0]["label"]).classes("mt-2 text-sm font-bold text-cyan-100")
                    robot_face_image = ui.image(ROBOT_FACE_STATES[0]["source"]).classes(
                        "mt-3 h-[180px] w-full rounded-2xl bg-slate-950 p-2 object-contain"
                    )
                    attach_robot_face_rotation(robot_face_image, robot_face_status)
            with ui.column().classes("min-w-0 flex-1"):
                ui.label("🤖 Hệ thống Robot Hỗ Trợ Thông Minh").classes("text-3xl font-black leading-tight")
                ui.label(
                    "Nhằm nâng cao dịch vụ và trải nghiệm người bệnh, bệnh viện triển khai hệ thống robot hỗ trợ "
                    "thông minh tích hợp công nghệ trí tuệ nhân tạo (AI)."
                ).classes("mt-3 text-base leading-7 text-slate-300")

                with ui.grid(columns=2).classes("mt-5 w-full gap-4 max-[900px]:grid-cols-1"):
                    for title, description in robot_features:
                        with ui.card().classes("rounded-2xl border border-cyan-400/20 bg-white/8 p-4 shadow-none"):
                            ui.label(title).classes("text-base font-black text-cyan-200")
                            ui.label(description).classes("mt-2 text-sm leading-6 text-slate-300")

                ui.label(
                    "Hệ thống robot góp phần giảm tải cho nhân viên y tế, đồng thời mang đến trải nghiệm khám chữa "
                    "bệnh hiện đại, tiện lợi và thân thiện hơn cho mọi bệnh nhân."
                ).classes("mt-5 text-base font-semibold leading-7 text-cyan-100")

    with ui.card().classes("mt-6 w-full rounded-3xl border-0 bg-white/95 p-7 shadow-xl shadow-cyan-100"):
        ui.label("🧭 Hướng dẫn đi khám với Robot hỗ trợ").classes("text-3xl font-black text-slate-900")
        ui.label(
            "Khi đến bệnh viện, vui lòng di chuyển đến khu vực Robot hướng dẫn. "
            "Đọc số thứ tự khám của bạn cho robot."
        ).classes("mt-3 text-lg leading-8 text-slate-700")
        ui.label("Robot sẽ:").classes("mt-5 text-xl font-black text-cyan-700")
        with ui.column().classes("mt-3 gap-3"):
            for item in [
                "Xác nhận thông tin lượt khám",
                "Hướng dẫn bạn đến đúng phòng khám",
                "Hỗ trợ chỉ đường nhanh chóng và chính xác",
            ]:
                with ui.row().classes("items-center gap-3"):
                    ui.icon("check_circle").classes("text-2xl text-emerald-500")
                    ui.label(item).classes("text-base font-semibold text-slate-700")
        ui.label(
            "Việc sử dụng robot giúp tiết kiệm thời gian và đảm bảo bạn đến đúng nơi cần khám "
            "một cách thuận tiện nhất."
        ).classes("mt-5 text-base leading-7 text-slate-600")


def build_doctor_team() -> None:
    doctors = [
        {
            "image": "/images/bacsi1.jpg?v=1",
            "name": "TS.BS Dương Minh Hoàng",
            "title": "Trưởng khoa Ngoại tổng hợp",
        },
        {
            "image": "/images/bacsi2.jpg?v=1",
            "name": "TS.BS Nguyễn Vũ Trung Hiếu",
            "title": "Trưởng khoa Tim mạch",
        },
        {
            "image": "/images/bacsi3.jpg?v=1",
            "name": "TS.BS Lê Minh Yến",
            "title": "Trưởng khoa Hô hấp",
        },
    ]

    with ui.card().classes("mt-8 w-full rounded-3xl border-0 bg-white/95 p-7 shadow-xl shadow-cyan-100"):
        ui.label("ĐỘI NGŨ CHÚNG TÔI").classes("text-center text-sm font-black uppercase tracking-[0.24em] text-cyan-700")
        ui.label("Đội ngũ bác sĩ chất lượng").classes("mt-3 text-center text-4xl font-light leading-tight text-slate-900")
        ui.label("chuyên môn cao").classes("text-center text-4xl font-black leading-tight text-slate-900")

        with ui.grid(columns=3).classes("mt-8 w-full gap-8 max-[1100px]:grid-cols-2 max-[900px]:grid-cols-1"):
            for doctor in doctors:
                with ui.card().classes(
                    "min-w-0 overflow-hidden rounded-[32px] border-0 bg-slate-50 p-6 text-center shadow-lg shadow-slate-200"
                ):
                    ui.image(doctor["image"]).classes(
                        "aspect-square w-full rounded-[28px] bg-slate-200 object-contain object-center"
                    )
                    ui.label(doctor["name"]).classes(
                        "mt-5 text-[clamp(1.2rem,1.5vw,1.9rem)] font-black leading-tight text-slate-900"
                    )
                    ui.label(doctor["title"]).classes(
                        "mt-3 text-[clamp(1rem,1.05vw,1.2rem)] font-semibold text-cyan-700"
                    )


def build_form_card() -> None:
    with ui.card().classes(
        "booking-form w-full flex-1 border-0 bg-slate-950 p-8 text-white shadow-2xl shadow-slate-300"
    ):
        ui.label("Form bệnh nhân").classes("text-2xl font-bold")
        ui.label("Điền thông tin để đăng ký lịch khám.").classes("mt-2 text-sm text-slate-300")

        field_classes = "w-full"

        name_input = (
            ui.input("Họ và tên")
            .props("outlined dense dark color=cyan-4")
            .classes("mt-6 " + field_classes)
        )
        phone_input = ui.input("Số điện thoại").props("outlined dense dark color=cyan-4").classes(field_classes)
        date_input = (
            ui.input("Ngày khám", value=str(date.today()))
            .props("outlined dense type=date dark color=cyan-4")
            .classes(field_classes)
        )
        time_input = (
            ui.input("Giờ khám", placeholder="HH:MM", value="08:00")
            .props("outlined dense dark color=cyan-4 maxlength=5")
            .classes(field_classes)
        )
        symptoms_input = (
            ui.textarea("Triệu chứng ban đầu")
            .props("outlined dark color=cyan-4")
            .classes(field_classes)
        )
        response_label = ui.label("").classes("min-h-[28px] text-sm text-emerald-300")

        def submit_appointment() -> None:
            if not patient_has_account(phone_input.value or ""):
                response_label.set_text("Bạn cần tạo tài khoản bằng số điện thoại này trước khi đặt lịch khám.")
                response_label.classes(replace="min-h-[28px] text-sm text-rose-300")
                ui.notify("Bạn cần tạo tài khoản trước khi đặt lịch khám.", color="negative")
                return

            try:
                normalized_time = normalize_appointment_time(time_input.value or "")
                department_value, room_label, _matched_phrases = infer_department_and_room_from_symptoms(
                    symptoms_input.value or ""
                )
                appointment = store.create_appointment(
                    patient_name=name_input.value or "",
                    phone=phone_input.value or "",
                    department=department_value,
                    appointment_date=date_input.value or "",
                    appointment_time=normalized_time,
                    symptoms=symptoms_input.value or "",
                )
            except ValueError as error:
                response_label.set_text(str(error))
                response_label.classes(replace="min-h-[28px] text-sm text-rose-300")
                ui.notify(str(error), color="negative")
                return

            sync_robot_patient_profile(
                name_input.value or "",
                phone_input.value or "",
                appointment=appointment,
                room_label=room_label,
                matched_phrases=_matched_phrases,
            )

            response_label.set_text(
                f"Đã đặt lịch cho {appointment.patient_name} lúc "
                f"{appointment.appointment_time} ngày {appointment.appointment_date}. "
                f"Hệ thống xếp vào {department_value} - phòng {room_label}."
            )
            response_label.classes(replace="min-h-[28px] text-sm text-emerald-300")
            show_booking_success(appointment, room_label=room_label)

            name_input.set_value("")
            phone_input.set_value("")
            date_input.set_value(str(date.today()))
            time_input.set_value("")
            symptoms_input.set_value("")
            appointments_table.rows = format_appointments(store.list_appointments())
            appointments_table.update()

        ui.button("Xác nhận đặt lịch", on_click=submit_appointment).props("unelevated").classes(
            "mt-2 w-full bg-cyan-500 px-6 py-3 text-sm font-bold text-slate-950"
        )


@ui.page("/")
def index() -> None:
    build_dashboard()

@ui.page("/account")
def account_page() -> None:
    ui.add_head_html(
        """
        <style>
            body {
                margin: 0;
                background:
                    radial-gradient(circle at top left, rgba(2, 132, 199, 0.20), transparent 28%),
                    linear-gradient(135deg, #eff6ff 0%, #f8fafc 48%, #ecfeff 100%);
            }
        </style>
        """
    )
    with ui.column().classes("min-h-screen w-full items-center px-6 py-10"):
        with ui.row().classes("w-full max-w-[1120px] items-start gap-6 max-[980px]:flex-col"):
            build_account_registration_form(
                "w-[460px] max-w-full rounded-3xl bg-white p-7 shadow-2xl",
                redirect_to_home=True,
            )
            build_account_history_card("min-h-[320px] flex-1 rounded-3xl bg-white p-7 shadow-2xl")
        # Đã bỏ bước/nút đăng ký khuôn mặt khi tạo tài khoản.
        # Người dùng chỉ cần tạo tài khoản bằng họ tên, số điện thoại và mật khẩu.



@ui.page("/booking")
def booking_page() -> None:
    """Trang đặt lịch hoạt động bằng HTML + fetch, không phụ thuộc NiceGUI WebSocket."""
    ui.add_head_html(
        """
        <style>
            body { margin:0; background:linear-gradient(135deg,#eff6ff 0%,#f8fafc 48%,#ecfeff 100%); }
            .native-booking-shell { width:min(760px,94vw); margin:34px auto; }
            .native-booking-card { background:#071426; color:#f8fafc; border-radius:30px; padding:30px; box-shadow:0 24px 60px rgba(15,23,42,.20); }
            .native-booking-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
            .native-field { display:grid; gap:7px; }
            .native-field.full { grid-column:1/-1; }
            .native-field label { font-size:14px; font-weight:800; color:#bae6fd; }
            .native-field input,.native-field textarea { width:100%; box-sizing:border-box; border:1px solid #475569; border-radius:13px; background:#0f2138; color:#fff; padding:12px 13px; font-size:15px; outline:none; }
            .native-field textarea { min-height:120px; resize:vertical; }
            .native-field input:focus,.native-field textarea:focus { border-color:#22d3ee; box-shadow:0 0 0 2px rgba(34,211,238,.2); }
            .native-actions { display:flex; gap:12px; margin-top:20px; }
            .native-primary { flex:1; border:0; border-radius:999px; background:#22c3ee; color:#fff; font-weight:900; padding:14px; cursor:pointer; font-size:16px; }
            .native-secondary { flex:1; border:1px solid #64748b; border-radius:999px; color:#e2e8f0; text-decoration:none; text-align:center; font-weight:800; padding:13px; }
            .native-status { min-height:28px; margin-top:16px; font-weight:700; line-height:1.6; }
            .native-result { display:none; margin-top:20px; border-radius:20px; background:#ecfdf5; color:#14532d; padding:20px; line-height:1.7; }
            .native-camera { margin-top:20px; border:1px solid rgba(34,211,238,.22); border-radius:22px; background:rgba(15,33,56,.72); padding:16px; }
            .native-camera video,.native-camera img { width:100%; max-height:330px; object-fit:cover; border-radius:16px; background:#020617; }
            .native-camera img { display:none; }
            .native-camera-actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
            .native-small-btn { border:0; border-radius:999px; padding:11px 15px; font-weight:800; cursor:pointer; }
            @media(max-width:680px){ .native-booking-grid{grid-template-columns:1fr;} .native-field.full{grid-column:auto;} .native-actions{flex-direction:column;} }
        </style>
        """
    )

    today_value = date.today().isoformat()
    ui.html(
        f"""
        <div class="native-booking-shell">
            <div class="native-booking-card">
                <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;">
                    <div>
                        <div style="font-size:28px;font-weight:950;">Đặt khám ngay</div>
                        <div style="margin-top:7px;color:#cbd5e1;">Điền thông tin; hệ thống sẽ tự xác định khoa và phòng từ bảng triệu chứng trên web admin.</div>
                    </div>
                    <a id="native_booking_account_link" href="/account?return=%2Fbooking" style="color:#67e8f9;font-weight:800;text-decoration:none;">Tài khoản</a>
                </div>

                <form id="native_booking_form" style="margin-top:24px;">
                    <div class="native-booking-grid">
                        <div class="native-field"><label>Họ và tên</label><input id="native_booking_name" required autocomplete="name"></div>
                        <div class="native-field"><label>Số điện thoại đã tạo tài khoản</label><input id="native_booking_phone" required inputmode="numeric" autocomplete="tel"></div>
                        <div class="native-field"><label>Ngày khám</label><input id="native_booking_date" type="date" min="{today_value}" value="{today_value}" required></div>
                        <div class="native-field"><label>Giờ khám (HH:MM)</label><input id="native_booking_time" value="08:00" pattern="([01]?[0-9]|2[0-3]):[0-5][0-9]" required></div>
                        <div class="native-field full"><label>Triệu chứng ban đầu</label><textarea id="native_booking_symptoms" placeholder="Ví dụ: đau đầu, sốt, đau ngực..." required></textarea></div>
                    </div>

                    <div class="native-camera">
                        <div style="font-size:17px;font-weight:900;color:#a5f3fc;">Ảnh khuôn mặt (không bắt buộc)</div>
                        <div style="margin:6px 0 12px;color:#cbd5e1;font-size:13px;">Có thể bỏ qua và vẫn đặt lịch bình thường.</div>
                        <video id="native_booking_video" autoplay playsinline muted></video>
                        <img id="native_booking_preview" alt="Ảnh khuôn mặt đã chụp">
                        <canvas id="native_booking_canvas" style="display:none"></canvas>
                        <div class="native-camera-actions">
                            <button type="button" class="native-small-btn" style="background:#22c3ee;color:#fff" onclick="window.nativeStartBookingCamera()">Bật camera</button>
                            <button type="button" class="native-small-btn" style="background:#22c55e;color:#fff" onclick="window.nativeCaptureBookingFace()">Chụp và lưu ảnh</button>
                            <button type="button" class="native-small-btn" style="background:#334155;color:#fff" onclick="window.nativeStopBookingCamera()">Tắt camera</button>
                        </div>
                        <div id="native_booking_camera_status" style="margin-top:10px;color:#cbd5e1;font-size:13px;">Camera đang tắt.</div>
                    </div>

                    <div id="native_booking_status" class="native-status"></div>
                    <div class="native-actions">
                        <a href="/" class="native-secondary">Về trang chủ</a>
                        <button id="native_booking_submit" type="submit" class="native-primary">Xác nhận đặt lịch</button>
                    </div>
                </form>
                <div id="native_booking_result" class="native-result"></div>
            </div>
        </div>
        """,
        sanitize=False,
    ).classes("w-full")

    ui.add_body_html(
        r"""
        <script>
        (() => {
            if (window.__nativeBookingInstalled) return;
            window.__nativeBookingInstalled = true;
            window.nativeBookingStream = null;

            const el = (id) => document.getElementById(id);
            const escapeHtml = (value) => String(value ?? '')
                .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
                .replaceAll('"','&quot;').replaceAll("'",'&#039;');


            const BOOKING_DRAFT_KEY = 'aurora_booking_draft_v2';
            const ACCOUNT_KEY = 'aurora_account_v1';
            let bookingCompleted = false;

            const bookingFieldIds = [
                'native_booking_name',
                'native_booking_phone',
                'native_booking_date',
                'native_booking_time',
                'native_booking_symptoms',
            ];

            const saveBookingDraft = () => {
                if (bookingCompleted || !el('native_booking_form')) return;
                const draft = {
                    patient_name: el('native_booking_name')?.value || '',
                    phone: el('native_booking_phone')?.value || '',
                    appointment_date: el('native_booking_date')?.value || '',
                    appointment_time: el('native_booking_time')?.value || '',
                    symptoms: el('native_booking_symptoms')?.value || '',
                };
                localStorage.setItem(BOOKING_DRAFT_KEY, JSON.stringify(draft));
            };

            const restoreBookingDraft = () => {
                if (!el('native_booking_form')) return false;
                let draft = {};
                let account = {};
                try { draft = JSON.parse(localStorage.getItem(BOOKING_DRAFT_KEY) || '{}'); } catch (_) {}
                try { account = JSON.parse(localStorage.getItem(ACCOUNT_KEY) || '{}'); } catch (_) {}

                const nameInput = el('native_booking_name');
                const phoneInput = el('native_booking_phone');
                const dateInput = el('native_booking_date');
                const timeInput = el('native_booking_time');
                const symptomsInput = el('native_booking_symptoms');

                if (nameInput) nameInput.value = draft.patient_name || account.name || nameInput.value || '';
                if (phoneInput) phoneInput.value = draft.phone || account.phone || phoneInput.value || '';
                if (dateInput && draft.appointment_date) dateInput.value = draft.appointment_date;
                if (timeInput && draft.appointment_time) timeInput.value = draft.appointment_time;
                if (symptomsInput && draft.symptoms) symptomsInput.value = draft.symptoms;

                bookingFieldIds.forEach((id) => {
                    const field = el(id);
                    if (!field || field.dataset.draftBound === '1') return;
                    field.dataset.draftBound = '1';
                    field.addEventListener('input', saveBookingDraft);
                    field.addEventListener('change', saveBookingDraft);
                });

                const accountLink = el('native_booking_account_link');
                if (accountLink && accountLink.dataset.draftBound !== '1') {
                    accountLink.dataset.draftBound = '1';
                    accountLink.addEventListener('click', saveBookingDraft);
                }
                return true;
            };

            const scheduleBookingRestore = (attempt = 0) => {
                if (restoreBookingDraft()) return;
                if (attempt < 50) setTimeout(() => scheduleBookingRestore(attempt + 1), 100);
            };
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => scheduleBookingRestore(), {once:true});
            } else {
                setTimeout(() => scheduleBookingRestore(), 0);
            }
            window.addEventListener('beforeunload', saveBookingDraft);

            window.nativeStartBookingCamera = async () => {
                const status = el('native_booking_camera_status');
                const video = el('native_booking_video');
                const preview = el('native_booking_preview');
                try {
                    if (window.nativeBookingStream) window.nativeBookingStream.getTracks().forEach(t => t.stop());
                    const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});
                    window.nativeBookingStream = stream;
                    video.srcObject = stream;
                    video.style.display = 'block';
                    preview.style.display = 'none';
                    status.textContent = 'Camera đã bật.';
                } catch (error) {
                    status.textContent = 'Không thể mở camera. Hãy dùng localhost hoặc HTTPS và cấp quyền camera.';
                }
            };

            window.nativeStopBookingCamera = () => {
                const video = el('native_booking_video');
                const status = el('native_booking_camera_status');
                if (window.nativeBookingStream) window.nativeBookingStream.getTracks().forEach(t => t.stop());
                window.nativeBookingStream = null;
                if (video) video.srcObject = null;
                if (status) status.textContent = 'Camera đã tắt.';
            };

            window.nativeCaptureBookingFace = async () => {
                const name = el('native_booking_name')?.value.trim() || '';
                const phone = el('native_booking_phone')?.value.trim() || '';
                const status = el('native_booking_camera_status');
                const video = el('native_booking_video');
                const preview = el('native_booking_preview');
                const canvas = el('native_booking_canvas');
                if (!name || !phone) { status.textContent = 'Nhập họ tên và số điện thoại trước khi chụp.'; return; }
                if (!window.nativeBookingStream || !video.videoWidth) { status.textContent = 'Hãy bật camera trước.'; return; }
                canvas.width = video.videoWidth; canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
                const imageData = canvas.toDataURL('image/jpeg',0.92);
                status.textContent = 'Đang lưu ảnh...';
                try {
                    const response = await fetch('/api/face-registration', {
                        method:'POST', headers:{'Content-Type':'application/json'},
                        body:JSON.stringify({patient_name:name,phone:phone,image_data:imageData})
                    });
                    const data = await response.json();
                    if (!response.ok || !data.ok) throw new Error(data.message || 'Không thể lưu ảnh.');
                    preview.src = imageData; preview.style.display = 'block'; video.style.display = 'none';
                    status.textContent = `Đã lưu ảnh cho ${data.patient_name}.`;
                } catch (error) { status.textContent = error.message || 'Không thể lưu ảnh.'; }
            };

            document.addEventListener('submit', async (event) => {
                if (!event.target || event.target.id !== 'native_booking_form') return;
                event.preventDefault();
                const status = el('native_booking_status');
                const submit = el('native_booking_submit');
                const resultBox = el('native_booking_result');
                const payload = {
                    patient_name: el('native_booking_name').value.trim(),
                    phone: el('native_booking_phone').value.trim(),
                    appointment_date: el('native_booking_date').value,
                    appointment_time: el('native_booking_time').value.trim(),
                    symptoms: el('native_booking_symptoms').value.trim(),
                };
                saveBookingDraft();
                status.style.color = '#cbd5e1'; status.textContent = 'Đang xác nhận lịch khám...';
                submit.disabled = true; submit.style.opacity = '.65'; resultBox.style.display = 'none';
                try {
                    const response = await fetch('/api/create-booking', {
                        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
                    });
                    const data = await response.json();
                    if (!response.ok || !data.ok) {
                        if (data.need_account) throw new Error(data.message + ' Mở trang Tài khoản để đăng ký.');
                        throw new Error(data.message || 'Không thể đặt lịch.');
                    }
                    const appointment = data.appointment || {};
                    bookingCompleted = true;
                    localStorage.removeItem(BOOKING_DRAFT_KEY);
                    localStorage.setItem(ACCOUNT_KEY, JSON.stringify({
                        name: payload.patient_name,
                        phone: data.appointment?.phone || payload.phone,
                    }));
                    status.style.color = '#4ade80'; status.textContent = data.message || 'Đặt khám thành công.';
                    resultBox.innerHTML = `
                        <div style="font-size:24px;font-weight:950;">✓ Đặt khám thành công</div>
                        <div style="margin-top:8px;font-size:20px;font-weight:900;">Số thứ tự của bạn: ${escapeHtml(appointment.id)}</div>
                        <div style="margin-top:10px;">
                            Khoa khám: <b>${escapeHtml(appointment.department)}</b><br>
                            Phòng khám: <b>${escapeHtml(data.room_label)}</b><br>
                            Ngày: ${escapeHtml(appointment.appointment_date)} — Giờ: ${escapeHtml(appointment.appointment_time)}
                        </div>
                        <div style="margin-top:12px;font-weight:900;">Hãy gặp robot AURORA ở trước cổng bệnh viện và báo số thứ tự cho robot.</div>`;
                    resultBox.style.display = 'block';
                    resultBox.scrollIntoView({behavior:'smooth',block:'center'});
                } catch (error) {
                    status.style.color = '#f87171'; status.textContent = error.message || 'Không thể đặt lịch.';
                } finally {
                    submit.disabled = false; submit.style.opacity = '1';
                }
            }, true);
        })();
        </script>
        """
    )


@ui.page("/face-register")
def face_register_page() -> None:
    ui.add_head_html(
        """
        <style>
            body {
                margin: 0;
                background:
                    radial-gradient(circle at top left, rgba(14, 165, 233, 0.18), transparent 28%),
                    linear-gradient(135deg, #eff6ff 0%, #f8fafc 52%, #ecfeff 100%);
            }
            .face-register-shell {
                width: 100%;
                display: grid;
                gap: 18px;
            }
            .face-register-grid {
                display: grid;
                grid-template-columns: minmax(0, 320px) minmax(0, 1fr);
                gap: 24px;
                align-items: start;
            }
            .face-register-field {
                display: grid;
                gap: 8px;
            }
            .face-register-field span {
                color: #0f172a;
                font-size: 14px;
                font-weight: 800;
            }
            .face-register-field input {
                width: 100%;
                border: 1px solid rgba(148, 163, 184, 0.55);
                border-radius: 18px;
                background: rgba(255, 255, 255, 0.95);
                color: #0f172a;
                font-size: 16px;
                padding: 14px 16px;
                box-sizing: border-box;
            }
            .face-register-video-shell {
                position: relative;
                overflow: hidden;
                border-radius: 28px;
                background: linear-gradient(135deg, #020617, #0f172a);
                min-height: 360px;
                box-shadow: inset 0 0 0 1px rgba(34, 211, 238, 0.18);
            }
            .face-register-video,
            .face-register-preview {
                width: 100%;
                height: 100%;
                min-height: 360px;
                display: block;
                object-fit: cover;
            }
            .face-register-preview {
                display: none;
            }
            .face-register-status {
                border-radius: 20px;
                background: rgba(8, 145, 178, 0.10);
                color: #0f4c81;
                font-size: 15px;
                font-weight: 700;
                line-height: 1.6;
                min-height: 56px;
                padding: 14px 16px;
            }
            .face-register-hint {
                color: #475569;
                font-size: 14px;
                line-height: 1.7;
            }
            @media (max-width: 900px) {
                .face-register-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        <script>
            window.faceRegisterState = window.faceRegisterState || {stream: null};

            window.startFaceRegisterCamera = async function () {
                const status = document.getElementById('face_register_status');
                const video = document.getElementById('face_camera_preview');
                const preview = document.getElementById('face_capture_preview');
                if (!video || !status) return;
                try {
                    if (window.faceRegisterState.stream) {
                        window.faceRegisterState.stream.getTracks().forEach(track => track.stop());
                    }
                    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
                    window.faceRegisterState.stream = stream;
                    video.srcObject = stream;
                    preview.style.display = 'none';
                    video.style.display = 'block';
                    status.textContent = 'Camera đã bật. Vui lòng nhìn thẳng vào màn hình rồi bấm chụp ảnh.';
                } catch (error) {
                    status.textContent = 'Không thể mở camera. Hãy dùng localhost hoặc HTTPS và cho phép trình duyệt truy cập camera.';
                }
            };

            window.stopFaceRegisterCamera = function () {
                const status = document.getElementById('face_register_status');
                const video = document.getElementById('face_camera_preview');
                if (window.faceRegisterState.stream) {
                    window.faceRegisterState.stream.getTracks().forEach(track => track.stop());
                    window.faceRegisterState.stream = null;
                }
                if (video) {
                    video.srcObject = null;
                }
                if (status) {
                    status.textContent = 'Camera đã tắt. Bạn có thể bật lại để chụp ảnh khác.';
                }
            };

            window.captureFaceRegisterImage = async function () {
                const patientName = document.getElementById('face_patient_name');
                const phone = document.getElementById('face_patient_phone');
                const status = document.getElementById('face_register_status');
                const video = document.getElementById('face_camera_preview');
                const canvas = document.getElementById('face_camera_canvas');
                const preview = document.getElementById('face_capture_preview');
                if (!patientName || !phone || !status || !video || !canvas || !preview) return;

                if (!patientName.value.trim() || !phone.value.trim()) {
                    status.textContent = 'Vui lòng nhập họ tên và số điện thoại trước khi chụp ảnh khuôn mặt.';
                    return;
                }
                if (!window.faceRegisterState.stream || !video.videoWidth) {
                    status.textContent = 'Bạn cần bật camera trước khi chụp ảnh.';
                    return;
                }

                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const context = canvas.getContext('2d');
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const imageData = canvas.toDataURL('image/jpeg', 0.92);
                preview.src = imageData;
                preview.style.display = 'block';
                video.style.display = 'none';
                status.textContent = 'Đang lưu ảnh khuôn mặt...';

                try {
                    const response = await fetch('/api/face-registration', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            patient_name: patientName.value,
                            phone: phone.value,
                            image_data: imageData,
                        }),
                    });
                    const result = await response.json();
                    if (!response.ok || !result.ok) {
                        throw new Error(result.message || 'Không thể lưu ảnh khuôn mặt.');
                    }
                    status.textContent = `Đã lưu ảnh khuôn mặt cho ${result.patient_name}. Tổng số ảnh đã lưu: ${result.capture_count}.`;
                } catch (error) {
                    preview.style.display = 'none';
                    video.style.display = 'block';
                    status.textContent = error.message || 'Không thể lưu ảnh khuôn mặt.';
                }
            };
        </script>
        """
    )

    with ui.column().classes("min-h-screen w-full items-center px-6 py-10"):
        with ui.card().classes("w-[980px] max-w-[96vw] rounded-[32px] border-0 bg-white/95 p-8 shadow-2xl"):
            ui.label("Đăng ký khuôn mặt bệnh nhân").classes("text-3xl font-black text-slate-900")
            ui.label(
                "Bệnh nhân nhập thông tin, bật camera rồi chụp ảnh ngay trên web. Ảnh này sẽ là dữ liệu đầu vào cho phần xử lý khuôn mặt sau này."
            ).classes("mt-2 text-base leading-7 text-slate-600")

            ui.html(
                """
                <div class="face-register-shell">
                    <div class="face-register-grid">
                        <div class="face-register-field">
                            <span>Họ và tên</span>
                            <input id="face_patient_name" placeholder="Nhập họ tên bệnh nhân" />
                        </div>
                        <div class="face-register-field">
                            <span>Số điện thoại</span>
                            <input id="face_patient_phone" placeholder="Nhập số điện thoại đã đăng ký" />
                        </div>
                    </div>

                    <div class="face-register-video-shell">
                        <video id="face_camera_preview" class="face-register-video" autoplay playsinline muted></video>
                        <img id="face_capture_preview" class="face-register-preview" alt="Ảnh khuôn mặt đã chụp" />
                        <canvas id="face_camera_canvas" style="display:none;"></canvas>
                    </div>

                    <div id="face_register_status" class="face-register-status">
                        Hãy dùng máy có camera, cho phép trình duyệt truy cập camera, rồi bấm "Bật camera" để bắt đầu.
                    </div>

                    <div class="face-register-hint">
                        Gợi ý: chụp ảnh chính diện, đủ sáng, không bị ngược sáng và nên bỏ khẩu trang để ảnh dùng được cho bước xác minh sau này.
                    </div>
                </div>
                """
            ).classes("mt-6 w-full")

            ui.html(
                """
                <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:20px;">
                    <button type="button" onclick="window.startFaceRegisterCamera && window.startFaceRegisterCamera()"
                        style="border:0;border-radius:999px;background:#22c3ee;color:white;padding:12px 20px;font-weight:800;cursor:pointer;">Bật camera</button>
                    <button type="button" onclick="window.captureFaceRegisterImage && window.captureFaceRegisterImage()"
                        style="border:0;border-radius:999px;background:#22c55e;color:white;padding:12px 20px;font-weight:800;cursor:pointer;">Chụp và lưu ảnh</button>
                    <button type="button" onclick="window.stopFaceRegisterCamera && window.stopFaceRegisterCamera()"
                        style="border:1px solid #cbd5e1;border-radius:999px;background:white;color:#334155;padding:12px 20px;font-weight:800;cursor:pointer;">Tắt camera</button>
                </div>
                <div style="display:flex;justify-content:space-between;gap:12px;margin-top:24px;flex-wrap:wrap;">
                    <a href="/" style="color:#475569;text-decoration:none;font-weight:700;padding:12px;">Về trang chủ</a>
                    <a href="/account" style="border:1px solid #22c3ee;border-radius:999px;color:#0891b2;text-decoration:none;font-weight:800;padding:12px 20px;">Trang tài khoản</a>
                </div>
                """,
                sanitize=False,
            ).classes("w-full")

HEADER_NAV_LINKS = [
    ("Giới thiệu", "/gioi-thieu-benh-vien"),
    ("Chuyên khoa", "/chuyen-khoa"),
    ("Bảng giá", "/bang-gia"),
    ("Hướng dẫn", "/huong-dan"),
]


def build_navigation() -> None:
    with ui.row().classes(
        "main-nav min-w-0 flex-1 flex-nowrap items-center justify-start gap-3 overflow-x-auto"
    ):
        for title, target in HEADER_NAV_LINKS:
            ui.button(title, on_click=lambda path=target: ui.navigate.to(path)).props("flat no-caps").classes(
                "shrink-0 rounded-full px-3"
            )


def _build_demo_page(title: str, intro: str, cards: list[tuple[str, str]]) -> None:
    ui.add_head_html(
        """
        <style>
            body {
                margin: 0;
                background:
                    radial-gradient(circle at top left, rgba(14, 165, 233, 0.18), transparent 28%),
                    linear-gradient(135deg, #eff6ff 0%, #f8fafc 52%, #ecfeff 100%);
            }
        </style>
        """
    )
    with ui.column().classes("min-h-screen w-full items-center px-6 py-10"):
        with ui.card().classes("w-[1180px] max-w-[96vw] rounded-[32px] border-0 bg-white/95 p-8 shadow-2xl"):
            with ui.row().classes("w-full items-center justify-between gap-3 max-[700px]:flex-col"):
                ui.button("Về trang chủ", on_click=lambda: ui.navigate.to("/")).props("flat no-caps icon=arrow_back").classes(
                    "text-cyan-700"
                )
                ui.button("Trang tài khoản", on_click=lambda: ui.navigate.to("/account")).props(
                    "outline no-caps icon=person"
                ).classes("rounded-full border-cyan-500 px-5 py-3 font-bold text-cyan-600")
            ui.label(title).classes("mt-6 text-4xl font-black text-slate-900")
            ui.label(intro).classes("mt-3 max-w-3xl text-lg leading-8 text-slate-600")
            with ui.grid(columns=3).classes("mt-8 w-full gap-6 max-[1100px]:grid-cols-2 max-[800px]:grid-cols-1"):
                for heading, body in cards:
                    with ui.card().classes("rounded-3xl border-0 bg-slate-50 p-6 shadow-lg shadow-slate-200"):
                        ui.label(heading).classes("text-xl font-black text-slate-900")
                        ui.label(body).classes("mt-3 text-base leading-7 text-slate-600")


@ui.page("/gioi-thieu")
def intro_demo_page() -> None:
    _build_demo_page(
        "Giới thiệu",
        "Đây là trang demo cho mục giới thiệu. Bạn có thể thay phần này bằng thông tin bệnh viện, robot và đội ngũ nghiên cứu sau.",
        [
            ("Tầm nhìn", "Xây dựng hệ thống bệnh viện thông minh có robot hỗ trợ dẫn đường và tiếp nhận bệnh nhân."),
            ("Robot AURORA", "Robot nhận số thứ tự, hỗ trợ giao tiếp và dẫn bệnh nhân đến đúng phòng khám."),
            ("Nền tảng web", "Web phục vụ đặt lịch, quản lý dữ liệu bệnh nhân và kết nối với web admin."),
        ],
    )


@ui.page("/chuyen-khoa")
def specialty_demo_page() -> None:
    _build_demo_page(
        "Chuyên khoa",
        "Đây là trang demo cho danh sách chuyên khoa. Sau này bạn có thể nối trực tiếp với dữ liệu thật từ admin.",
        [
            ("Khoa Nội tổng quát", "Khám sốt, đau đầu, mệt mỏi, mất ngủ và các triệu chứng nội khoa thường gặp."),
            ("Khoa Tim mạch", "Hỗ trợ các ca đau ngực, khó thở khi gắng sức, hồi hộp và tăng huyết áp."),
            ("Khoa Hô hấp", "Khám ho, đau họng, khó thở và các bệnh lý liên quan đường hô hấp."),
        ],
    )


@ui.page("/bang-gia")
def pricing_demo_page() -> None:
    _build_demo_page(
        "Bảng giá",
        "Đây là trang demo bảng giá để bạn trình bày giao diện trước khi có dữ liệu chính thức.",
        [
            ("Khám tổng quát", "250.000 VND cho một lượt khám ban đầu."),
            ("Khám chuyên khoa", "350.000 VND tùy khoa và bác sĩ phụ trách."),
            ("Hỗ trợ robot dẫn đường", "Miễn phí cho bệnh nhân đã có lịch khám trong hệ thống."),
        ],
    )


@ui.page("/huong-dan")
def guide_demo_page() -> None:
    _build_demo_page(
        "Hướng dẫn",
        "Đây là trang demo hướng dẫn sử dụng hệ thống đặt lịch và robot tại bệnh viện.",
        [
            ("Bước 1", "Bệnh nhân đặt lịch trên web, nhập triệu chứng và nhận số thứ tự."),
            ("Bước 2", "Khi đến bệnh viện, bệnh nhân đọc số thứ tự cho robot hoặc xác minh khuôn mặt."),
            ("Bước 3", "Robot tra cứu dữ liệu và dẫn bệnh nhân đến đúng phòng khám."),
        ],
    )


@ui.page("/gioi-thieu-benh-vien")
def hospital_intro_page() -> None:
    ui.add_head_html(
        """
        <style>
            body {
                margin: 0;
                background:
                    radial-gradient(circle at top left, rgba(14, 165, 233, 0.18), transparent 28%),
                    linear-gradient(135deg, #eff6ff 0%, #f8fafc 52%, #ecfeff 100%);
            }
        </style>
        """
    )
    with ui.column().classes("min-h-screen w-full items-center px-6 py-10"):
        with ui.card().classes("w-[1240px] max-w-[96vw] rounded-[34px] border-0 bg-white/95 p-8 shadow-2xl"):
            with ui.row().classes("w-full items-center justify-between gap-3 max-[700px]:flex-col"):
                ui.button("Về trang chủ", on_click=lambda: ui.navigate.to("/")).props("flat no-caps icon=arrow_back").classes(
                    "text-cyan-700"
                )
                ui.button("Trang tài khoản", on_click=lambda: ui.navigate.to("/account")).props(
                    "outline no-caps icon=person"
                ).classes("rounded-full border-cyan-500 px-5 py-3 font-bold text-cyan-600")

            ui.label("Giới thiệu bệnh viện và hệ thống robot AURORA").classes("mt-6 text-4xl font-black text-slate-900")
            ui.label(
                "AURORA là mô hình bệnh viện thông minh hướng tới việc hỗ trợ người bệnh từ bước đăng ký, tiếp nhận, xác minh thông tin cho đến hướng dẫn di chuyển đến đúng phòng khám."
            ).classes("mt-3 max-w-4xl text-lg leading-8 text-slate-600")

            with ui.row().classes("mt-8 w-full gap-6 max-[1000px]:flex-col"):
                with ui.card().classes("min-w-0 flex-[1.2] rounded-[30px] border-0 bg-slate-50 p-7 shadow-lg shadow-slate-200"):
                    ui.label("Tổng quan").classes("text-sm font-black uppercase tracking-[0.22em] text-cyan-700")
                    ui.label("Mô hình bệnh viện hiện đại, lấy bệnh nhân làm trung tâm").classes(
                        "mt-3 text-3xl font-black leading-tight text-slate-900"
                    )
                    ui.label(
                        "Hệ thống được xây dựng nhằm giảm thời gian chờ, chuẩn hóa quy trình check-in và nâng cao trải nghiệm của bệnh nhân ngay từ khi đặt lịch trên web. "
                        "Thông tin bệnh nhân, triệu chứng ban đầu, số thứ tự và phòng khám được liên kết xuyên suốt giữa web, trang admin và robot hỗ trợ."
                    ).classes("mt-4 text-base leading-8 text-slate-600")
                    with ui.column().classes("mt-5 gap-3"):
                        for item in [
                            "Đăng ký khám bệnh trực tuyến trước khi đến bệnh viện",
                            "Tự động gợi ý khoa khám và phòng khám dựa trên triệu chứng",
                            "Đồng bộ số thứ tự để hỗ trợ robot dẫn đường bằng giọng nói",
                            "Hỗ trợ mở rộng sang xác minh khuôn mặt và tích hợp ROS2",
                        ]:
                            with ui.row().classes("items-start gap-3"):
                                ui.icon("check_circle").classes("mt-1 text-xl text-emerald-500")
                                ui.label(item).classes("text-base font-semibold leading-7 text-slate-700")

                with ui.card().classes("min-w-0 flex-1 rounded-[30px] border-0 bg-slate-950 p-7 text-white shadow-2xl shadow-cyan-100"):
                    ui.label("Robot AURORA").classes("text-sm font-black uppercase tracking-[0.22em] text-cyan-200")
                    ui.label("Trợ lý tiếp đón và dẫn đường trong bệnh viện").classes(
                        "mt-3 text-3xl font-black leading-tight text-white"
                    )
                    ui.label(
                        "Robot AURORA được thiết kế để tương tác với bệnh nhân ngay tại khu vực đón tiếp. "
                        "Robot có thể nhận số thứ tự, hiển thị biểu cảm khuôn mặt, hỗ trợ giao tiếp trực quan và hướng dẫn bệnh nhân đến đúng phòng khám theo dữ liệu đã được web cấp phát."
                    ).classes("mt-4 text-base leading-8 text-slate-300")
                    with ui.column().classes("mt-5 gap-3"):
                        for item in [
                            "Tiếp nhận số thứ tự bệnh nhân bằng giọng nói",
                            "Tra cứu dữ liệu phòng khám từ hệ thống đã đăng ký trước",
                            "Xác minh bệnh nhân bằng khuôn mặt ở các bước nâng cấp tiếp theo",
                            "Dẫn đường và hỗ trợ giải thích quy trình đi khám tại bệnh viện",
                        ]:
                            with ui.row().classes("items-start gap-3"):
                                ui.icon("smart_toy").classes("mt-1 text-xl text-cyan-300")
                                ui.label(item).classes("text-base font-semibold leading-7 text-slate-200")

            with ui.grid(columns=3).classes("mt-8 w-full gap-6 max-[1100px]:grid-cols-2 max-[800px]:grid-cols-1"):
                with ui.card().classes("rounded-3xl border-0 bg-cyan-50 p-6 shadow-lg shadow-cyan-100"):
                    ui.label("Sứ mệnh").classes("text-xl font-black text-slate-900")
                    ui.label(
                        "Ứng dụng công nghệ để giúp người bệnh tiếp cận dịch vụ y tế thuận tiện hơn, đặc biệt trong khâu đăng ký, tiếp đón và tìm đường trong bệnh viện."
                    ).classes("mt-3 text-base leading-7 text-slate-600")
                with ui.card().classes("rounded-3xl border-0 bg-slate-50 p-6 shadow-lg shadow-slate-200"):
                    ui.label("Định hướng phát triển").classes("text-xl font-black text-slate-900")
                    ui.label(
                        "Mở rộng sang nhận diện giọng nói, nhận diện khuôn mặt, điều phối robot tự hành và kết nối dữ liệu thời gian thực với hệ thống quản lý bệnh viện."
                    ).classes("mt-3 text-base leading-7 text-slate-600")
                with ui.card().classes("rounded-3xl border-0 bg-emerald-50 p-6 shadow-lg shadow-emerald-100"):
                    ui.label("Đối tượng phục vụ").classes("text-xl font-black text-slate-900")
                    ui.label(
                        "Bệnh nhân, người nhà bệnh nhân, nhân viên y tế và bộ phận điều hành có nhu cầu theo dõi, hỗ trợ và chuẩn hóa luồng khám bệnh."
                    ).classes("mt-3 text-base leading-7 text-slate-600")

            with ui.card().classes("mt-8 w-full rounded-[30px] border-0 bg-white p-7 shadow-lg shadow-slate-200"):
                ui.label("Quy trình hoạt động của hệ thống").classes("text-2xl font-black text-slate-900")
                with ui.grid(columns=4).classes("mt-6 w-full gap-5 max-[1100px]:grid-cols-2 max-[700px]:grid-cols-1"):
                    for title, body in [
                        ("1. Đăng ký", "Bệnh nhân tạo tài khoản, nhập thông tin cá nhân và đặt lịch khám trên web."),
                        ("2. Phân luồng", "Hệ thống đối chiếu triệu chứng với bảng quản trị để xác định khoa và phòng khám phù hợp."),
                        ("3. Check-in với robot", "Khi đến bệnh viện, bệnh nhân đọc số thứ tự hoặc xác minh khuôn mặt với robot AURORA."),
                        ("4. Dẫn đường", "Robot sử dụng dữ liệu phòng khám và tọa độ để hướng dẫn bệnh nhân đến đúng vị trí."),
                    ]:
                        with ui.card().classes("rounded-3xl border-0 bg-slate-50 p-5 shadow-none"):
                            ui.label(title).classes("text-lg font-black text-cyan-700")
                            ui.label(body).classes("mt-3 text-base leading-7 text-slate-600")



if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=os.getenv("NICEGUI_HOST", "0.0.0.0"),
        port=int(os.getenv("NICEGUI_PORT", "8080")),
        title="Robot Hospital Booking",
        reload=False,
    )