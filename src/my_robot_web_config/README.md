# 🌐 Hospital Robot Web Interface, Smart Triage & HRI Display System

Dự án phát triển **Giao diện Web Tương tác Người - Robot (Human-Robot Interaction - HRI)**, **Hệ thống Phân loại Bệnh tự động (Smart Triage)** và **Dashboard Quản lý Y tế** cho Robot Phục vụ Bệnh viện. Module này đóng vai trò là điểm tiếp xúc trực tiếp giữa Robot với Bệnh nhân, Bác sĩ và Quản trị viên hệ thống.

---

## 💡 Kỹ Năng & Công Nghệ Triển Khai (Skills & Technologies)

* **Thiết kế Giao diện Tương tác (HRI & UI/UX):** Xây dựng bộ hiển thị cảm xúc khuôn mặt linh hoạt (Animated Emotional Face Display), tối ưu hóa trải nghiệm tương tác với bệnh nhân.
* **Cơ sở Dữ liệu & Quản lý Thông tin (Database Management):** Tích hợp SQLite database (`patient_booking.db`) lưu trữ lịch khám và quản lý tài khoản người bệnh (`patient_accounts.json`).
* **Hệ thống Gợi ý & Phân loại Bệnh (Rule-Based Triage Engine):** Tự động phân tích triệu chứng lâm sàng (`symptom_room_rules.json`) để điều hướng bệnh nhân đến đúng phòng khám.
* **Lập trình Web Backend & API:** Python Web Framework (Flask / Dash / FastAPI), REST API & WebSockets.
* **Giao tiếp & Đồng bộ Trạng thái Robot (IPC & Protocol):** Chuẩn hóa gói tin JSON truyền nhận lệnh và trạng thái thời gian thực (`robot_command.json`, `robot_state.json`).

---

## 🏛 Kiến Trúc Tương Tác (System Architecture)

```
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                        GIAO DIỆN MÀN HÌNH ROBOT / KIOSK                         │
  │                                                                                 │
  │  ┌──────────────────────────────┐        ┌──────────────────────────────────┐   │
  │  │  Robot Emotional Face UI     │        │    Hospital Kiosk & Medical UI   │   │
  │  │ (face_renderer / states)     │        │ (Appointments, Symptom Checker)  │   │
  │  └──────────────┬───────────────┘        └────────────────┬─────────────────┘   │
  └─────────────────┼─────────────────────────────────────────┼─────────────────────┘
                    │                                         │
                    ▼                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                         WEB BACKEND & CORE SERVICES                             │
  │                                                                                 │
  │   • State & UI Controller  : app.py, layout.py, state_model.py, visual_tokens.py │
  │   • Rule-Based Triage Engine: symptom_room_rules.json                           │
  │   • Database Persistence   : patient_booking.db, patient_accounts.json          │
  │   • IPC Command/State Bus  : robot_command.json, robot_state.json              │
  └─────────────────────────────────┬───────────────────────────────────────────────┘
                                    │ (ROS Bridge / Serial / API)
                                    ▼
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                         ROS 2 NAVIGATION & HARDWARE                             │
  │                         (my_robot_bringup package)                              │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu Trúc Thư Mục Package (`robot_web_interface`)

```
robot_web_interface/
├── user_information/         # Module quản lý hồ sơ & thông tin bệnh nhân
├── admin.py                  # Trang quản trị dành cho Quản lý / Kỹ thuật viên
├── app.py / app1.py          # Server chính khởi chạy ứng dụng Web
├── appointments.py           # Module tra cứu & đăng ký lịch hẹn khám bệnh
├── demo_driver.py            # Tool mô phỏng dữ liệu test UI & Render mặt robot
├── face_renderer.py          # Render đồ họa các trạng thái biểu cảm khuôn mặt
├── face_states.py            # Định nghĩa các trạng thái cảm xúc (Vui, Chờ, Nói, Lắng nghe...)
├── input_controller.py       # Bộ điều khiển hướng di chuyển & nhập liệu từ xa (Teleop)
├── layout.py                 # Định nghĩa cấu trúc khung giao diện người dùng
├── map_runtime.py            # Hiển thị vị trí Robot thời gian thực trên bản đồ
├── panel_tabs.py             # Quản lý các tab chức năng điều hướng trên màn hình
├── patient_accounts.json     # Dữ liệu tài khoản & thông tin bệnh nhân
├── patient_booking.db        # Cơ sở dữ liệu SQLite lưu trữ thông tin đặt lịch khám
├── payloads.py               # Chuẩn hóa cấu trúc gói tin dữ liệu gửi/nhận
├── requirements-web.txt      # Các thư viện Python phụ thuộc cho Web App
├── robot_command.json        # File giao tiếp lệnh điều khiển tới Robot (IPC)
├── robot_state.json          # File cập nhật trạng thái vận hành thời gian thực của Robot
├── runtime_contract.py       # Quy chuẩn kết nối giữa Web App và hệ thống ROS 2
├── state_model.py            # Quản lý trạng thái vận hành toàn hệ thống
├── symptom_room_rules.json   # Bộ quy tắc phân loại triệu chứng & gợi ý phòng khám
├── visual_tokens.py          # Định nghĩa Design Tokens (bảng màu, typo, giao diện)
├── CMakeLists.txt            # File cấu hình build package ROS 2
└── package.xml               # File khai báo phụ thuộc package ROS 2
```

---

## ⭐ Các Tính Năng Điển Hình (Key Features)

### 1. Phân Loại Triệu Chứng & Điều Hướng Phòng Khám (Smart Triage)
* Hệ thống tự động đọc bộ quy tắc từ `symptom_room_rules.json` để đưa ra câu hỏi phân loại cho bệnh nhân, sau đó tự động chỉ dẫn bệnh nhân đến đúng chuyên khoa/phòng khám tương ứng.

### 2. Quản Lý Đặt Lịch & Lưu Trữ Bệnh Án (Database Integration)
* Tích hợp **SQLite** (`patient_booking.db`) cùng file dữ liệu bệnh nhân (`patient_accounts.json`), hỗ trợ lưu trữ lịch hẹn khám, số thứ tự và tra cứu hồ sơ nhanh chóng ngay tại Kiosk.

### 3. Biểu Cảm Khuôn Mặt Robot Linh Hoạt (HRI Emotion UI)
* `face_renderer.py` & `face_states.py` giúp robot biểu đạt cảm xúc theo ngữ cảnh (chớp mắt, lắng nghe khi bệnh nhân nói, vui vẻ khi chào hỏi), tăng tính tương tác thân thiện trong môi trường y tế.

### 4. Đồng Bộ Trạng Thái & Điều Khẩu Thời Gian Thực
* Quản lý trạng thái Robot bằng cơ chế JSON state bus (`robot_state.json`, `robot_command.json`) giúp giao diện Web dễ dàng tương tác với các node ROS 2 bên dưới.

---

## 🚀 Hướng Dẫn Khởi Chạy Web Interface

### 1. Cài đặt các thư viện phụ thuộc

```bash
pip install -r requirements-web.txt
```

### 2. Khởi chạy Web Server Tương tác

```bash
python app.py
```

### 3. Chạy giao diện thử nghiệm Render Biểu cảm (Demo Mode)

```bash
python demo_driver.py
```

---

## 👨‍💻 Tác Giả & Liên Hệ (Author)

* **Họ và tên:** [Tên của bạn]
* **Vị trí ứng tuyển:** Embedded / ROS 2 Software Engineer / HRI Developer
* **LinkedIn:** [Đường dẫn LinkedIn của bạn]
* **Email:** [Email liên hệ của bạn]