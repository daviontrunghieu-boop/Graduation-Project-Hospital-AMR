# 🏥 Hospital Autonomous Service Robot (AMR) - Master Repository

![ROS 2](https://img.shields.io/badge/ROS2-Humble%20%7C%20Iron-blue?style=for-the-badge&logo=ros)
![Python](https://img.shields.io/badge/Python-3.8+-yellow?style=for-the-badge&logo=python)
![C++](https://img.shields.io/badge/C++-17-00599C?style=for-the-badge&logo=c%2B%2B)
![SQLite](https://img.shields.io/badge/Database-SQLite3-003B57?style=for-the-badge&logo=sqlite)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

Dự án nghiên cứu và phát triển trọn gói **Hệ thống Robot Phục vụ & Dẫn đường Bệnh viện Tự hành (Hospital AMR)**. Hệ thống kết hợp giữa **Thiết kế Cơ điện tử (CAD/URDF)**, **Điều khiển & Định vị Tự hành (ROS 2 Nav2/SLAM)**, **Cầu nối Phần cứng (Embedded Serial Driver)** cùng **Giao diện Tương tác Người - Robot Thông minh (HRI & Smart Triage Web UI)**.

---

## 🌟 Tổng Quan Kiến Trúc Hệ Thống (System Architecture)

Hệ thống được thiết kế theo mô hình mô-đun hóa với 3 khối package chính:

```
                               ┌──────────────────────────────────────────────┐
                               │       MÀN HÌNH TƯƠNG TÁC & KIOSK Y TẾ        │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ 🌐 PACKAGE 1: robot_web_interface (Giao diện Người - Robot & HRI)                                      │
 │  • Biểu cảm khuôn mặt Robot (Animated Face UI)   • Hệ thống gợi ý phòng khám (Symptom Rule Engine)   │
 │  • Quản lý lịch hẹn & Bệnh nhân (SQLite DB)      • Đồng bộ trạng thái thời gian thực (JSON IPC Bus)     │
 └────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                      │ (JSON State / ROS Bridge)
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ 🧠 PACKAGE 2: my_robot_bringup (Bộ não Trung tâm & Tích hợp ROS 2)                                    │
 │  • Định vị & Né vật cản (Nav2, AMCL, Costmap)    • Quét lập bản đồ môi trường (SLAM Toolbox)           │
 │  • Xử lý ảnh khuôn mặt & Giọng nói (OpenCV/AI)   • Cầu nối vi điều khiển (Arduino Serial Bridge)        │
 └─────────────────────────┬──────────────────────────────────────────────────────────────────────────────┘
                           │                                  │
                           ▼                                  ▼
 ┌──────────────────────────────────────────────────┐ ┌───────────────────────────────────────────────────┐
 │ 📐 PACKAGE 3: my_robot_description               │ │ 🔌 HARDWARE / SIMULATION LAYER                    │
 │  • Mô hình 3D CAD (.STL) & URDF/Xacro            │ │  • Môi trường mô phỏng Gazebo / RViz2             │
 │  • Cấu hình khung xe, bánh xe, Lidar & IMU       │ │  • Vi điều khiển động cơ (Arduino Motor Driver)   │
 └──────────────────────────────────────────────────┘ └───────────────────────────────────────────────────┘
```

---

## 📦 Các Thành Phần Cốt Lõi (Package Breakdown)

### 1. 📐 `my_robot_description` — Mô Hình 3D & Vật Lý Robot
> **Vai trò:** Định nghĩa cấu trúc động học, hình dáng 3D và thuộc tính vật lý của Robot.
* **Mô hình 3D:** Thiết kế các bộ phận Robot (Khung xe, bánh xe chủ động `MWL/MWR`, bánh xoay tự do `CFL/CFR/CBL/CBR`, cảm biến Lidar, IMU).
* **Cấu hình URDF / Xacro:** Khai báo liên kết động học (Joints/Links), hệ tọa độ `base_footprint`, cùng các thuộc tính vật lý (khối lượng, mô-men quán tính) phục vụ mô phỏng **Gazebo**.

### 2. 🧠 `my_robot_bringup` — Bộ Bão Điều Khiển & Tự Hành ROS 2
> **Vai trò:** Trung tâm xử lý thuật toán di chuyển, giao tiếp phần cứng và tích hợp AI.
* **Định vị & Tự hành (Nav2 & SLAM):** Tích hợp thuật toán điều hướng tự do, né vật cản động/tĩnh, quản lý Costmap và lưu trữ bản đồ 2D (`my_map.pgm`).
* **Cầu nối Phần cứng (Serial Bridge):** Giao tiếp hai chiều nối tiếp (UART/Serial) giữa ROS 2 Node và vi điều khiển Arduino điều khiển động cơ.
* **AI Vision & Giọng nói:** Nhận diện khuôn mặt người bệnh (`Voice_Camera.py`) và phát âm thanh chỉ dẫn di chuyển.

### 3. 🌐 `robot_web_interface` — Giao Diện Web & Kiosk Bệnh Viện
> **Vai trò:** Điểm tiếp xúc tương tác trực tiếp với Bệnh nhân và Nhân viên Y tế.
* **Biểu cảm Khuôn mặt (HRI Face Engine):** Hiển thị màn hình cảm xúc hoạt hình (Vui, Lắng nghe, Chờ...) tương ứng với hành vi robot.
* **Phân loại Bệnh Thông minh (Smart Triage):** Hệ thống phân tích triệu chứng (`symptom_room_rules.json`) tự động đề xuất chuyên khoa và dẫn đường cho bệnh nhân.
* **Cơ sở Dữ liệu Y tế (Database Persistence):** Quản lý hồ sơ bệnh nhân và lịch hẹn qua cơ sở dữ liệu **SQLite** (`patient_booking.db`).

---

## 🛠 Công Nghệ & Kỹ Năng Đã Sử Dụng (Tech Stack)

| Hạng mục | Công nghệ / Thư viện áp dụng |
| :--- | :--- |
| **Nền tảng Robot** | ROS 2 (Humble/Iron), Nav2, SLAM Toolbox, RViz2, Gazebo |
| **Lập trình chính** | Python 3, C++, Embedded C (Microchip XC8 / Arduino) |
| **Giao diện & Web** | Flask / Python Web, HTML5/CSS3, JavaScript, SQLite3 |
| **Thị giác máy tính & AI** | OpenCV, Face Recognition, Speech Processing |
| **Thiết kế 3D & CAD** | SolidWorks / Fusion 360 (Xuất định dạng STL, URDF) |
| **Giao thức Kết nối** | UART/Serial Communication, JSON State Bus, REST API |

---

## 🚀 Hướng Dẫn Biên Dịch & Khởi Chạy (Quick Start)

### 1. Yêu cầu hệ thống
* **Hệ điều hành:** Ubuntu 22.04 LTS (khuyên dùng)
* **ROS 2 Version:** ROS 2 Humble / Iron
* **Cơ sở dữ liệu:** Python 3.8+ & SQLite3

### 2. Cài đặt workspace & Biên dịch
```bash
# 1. Tạo workspace và clone repository
mkdir -p ~/hospital_robot_ws/src
cd ~/hospital_robot_ws/src
git clone https://github.com/your-username/hospital-robot-system.git .

# 2. Cài đặt các thư viện Python phụ thuộc cho Web UI
cd ~/hospital_robot_ws/src/robot_web_interface
pip install -r requirements-web.txt

# 3. Build toàn bộ Workspace ROS 2
cd ~/hospital_robot_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

### 3. Khởi chạy các Module

* **Bước 1: Khởi chạy Mô hình & Simulation (Gazebo / RViz)**
  ```bash
  ros2 launch my_robot_bringup robot2ws.launch.py
  ```

* **Bước 2: Khởi chạy Hệ thống Điều hướng & Bản đồ (Nav2)**
  ```bash
  ros2 launch my_robot_bringup nav2.launch.py
  ```

* **Bước 3: Khởi chạy Giao diện Web & Kiosk Bệnh viện**
  ```bash
  cd ~/hospital_robot_ws/src/robot_web_interface
  python app.py
  ```
