# 🏥 Hospital Autonomous Service Robot - Bringup & Integration System

![ROS 2](https://img.shields.io/badge/ROS2-Humble%2FFoxy-blue)
![Python](https://img.shields.io/badge/Python-3.10-green)
![OpenCV](https://img.shields.io/badge/AI-OpenCV%20%7C%20Face%20Recog-orange)
![Hardware](https://img.shields.io/badge/Hardware-Arduino%20%7C%20Serial-red)

Dự án phát triển **Hệ thống trung tâm điều khiển & Vận hành (Bringup Package)** cho Robot Phục vụ Bệnh viện Tự hành (Hospital AMR). Hệ thống đóng vai trò tích hợp toàn diện từ **điều khiển động cơ phần cứng**, **định vị dẫn đường (SLAM/Nav2)** đến các **tương tác thông minh bằng giọng nói và trí tuệ nhân tạo (AI Vision & Voice HRI)**.

---

## 💡 Kỹ Năng Kỹ Thuật Đã Triển Khai (Skills & Technologies)

* **Khung làm việc Robot (Robot Framework):** ROS 2 (Nodes, Launch files, Parameters, Topics/Services, Serial Bridge).
* **Điều khiển phần cứng & Nhúng (Embedded & Hardware):** Lập trình Arduino/Microcontroller, Truyền thông Serial (`serial_bridge_node`), Điều khiển động cơ.
* **Tự hành & Lập bản đồ (Autonomous Navigation):** ROS 2 Nav2, SLAM (Occupancy Grid Maps), Costmaps, Path Planning, AMCL.
* **Thị giác máy tính & AI (Vision & AI):** OpenCV, Nhận diện khuôn mặt (Face Detection/Recognition), Xử lý luồng Camera.
* **Tương tác Người - Robot (HRI):** Điều khiển & Dẫn đường bằng Giọng nói (Voice-guided Navigation), Xử lý kịch bản giao tiếp bệnh nhân.

---

## 🏛 Kiến Trúc Hệ Thống (System Architecture)

```
                       ┌──────────────────────────────┐
                       │    Tương Tác Giọng Nói & AI  │
                       │ (voice_nav_guide, Face AI)   │
                       └──────────────┬───────────────┘
                                      │ (Commands / Navigation Goals)
                                      ▼
┌──────────────────────┐    ┌─────────────────────────┐    ┌──────────────────────┐
│  Bản Đồ Môi Trường   │───►│  Nav2 Navigation Stack  │───►│  Toạ Độ & Vận Tốc   │
│ (my_map.pgm / yaml)  │    │  (Costmap / Planner)    │    │      (/cmd_vel)      │
└──────────────────────┘    └─────────────────────────┘    └──────────┬───────────┘
                                                                      │
                                                                      ▼
                                                           ┌──────────────────────┐
                                                           │ Serial Bridge Node   │
                                                           └──────────┬───────────┘
                                                                      │ (UART / USB)
                                                                      ▼
                                                           ┌──────────────────────┐
                                                           │ Arduino / Motor Driver│
                                                           └──────────────────────┘
```

---

## 📁 Cấu Trúc Thư Mục Package (`my_robot_bringup`)

```
my_robot_bringup/
├── config/                     # Tham số cấu hình thuật toán Nav2 & SLAM
│   ├── nav2_params.yaml        # Cấu hình Planner, Controller, Costmap cho Nav2
│   └── slam_config.yaml        # Cấu hình quét bản đồ SLAM
├── hospital_robot_camera/      # Module tích hợp phần cứng Camera bệnh viện
├── launch/                     # Các kịch bản khởi động hệ thống (System Launch Scripts)
│   ├── Slam_launch.py          # Kích hoạt chế độ quét bản đồ SLAM
│   ├── nav2.launch.py          # Kích hoạt hệ thống điều hướng tự hành Nav2
│   ├── Aurora.launch.py        # Master launch khởi động toàn bộ robot
│   └── voice_nav_guide.py      # Launch kịch bản hướng dẫn giọng nói
├── maps/                       # Bản đồ không gian 2D bệnh viện đã dựng
│   ├── my_map.pgm / .yaml      # Bản đồ mặt bằng thực tế
│   └── my_map1.pgm / .yaml     # Bản đồ thử nghiệm mở rộng
├── my_robot_bringup/           # Mã nguồn Python điều khiển & tương tác (Core Nodes)
│   ├── Driver_Andruino/        # Firmware nạp cho vi điều khiển Arduino
│   ├── serial_bridge_node.py   # Node cầu nối dữ liệu ROS 2 ◄► Arduino
│   ├── camera.py               # Node xử lý Camera stream
│   ├── Voice_Camera.py         # Node kết hợp xử lý Giọng nói & Hình ảnh
│   ├── face_prompt_listener.py # Node nhận diện khuôn mặt người dùng/bệnh nhân
│   ├── home_listener.py        # Kịch bản tự di chuyển về Trạm sạc (Home Base)
│   └── test_connection.py      # Diagnostic Tool kiểm tra kết nối phần cứng
└── worlds/                     # Môi trường mô phỏng không gian bệnh viện (Gazebo)
```

---

## ⭐ Các Tính Năng Nổi Bật (Key Features)

### 1. Cầu Nối Phần Cứng Linh Hoạt (Hardware Integration)
* Node `serial_bridge_node.py` chịu trách nhiệm đóng gói/giải mã dữ liệu giữa ROS 2 và vi điều khiển Arduino.
* Chuyển đổi lệnh vận tốc `/cmd_vel` thành xung PWM điều khiển động cơ và đọc phản hồi từ Encoder để tính Odometry thực tế.

### 2. Dẫn Đường Tự Hành Né Vật Cản (Autonomous Navigation)
* Tích hợp khung Nav2 giúp robot tự di chuyển từ vị trí A sang vị trí B trong bệnh viện.
* Tự động phát hiện vật cản động (người di chuyển, băng ca, thiết bị y tế) để tính toán lại lộ trình an toàn.

### 3. Tương Tác Giọng Nói & Trí Tuệ Nhân Tạo (AI Vision & Voice HRI)
* **Nhận diện khuôn mặt (`face_prompt_listener.py`):** Robot phát hiện sự có mặt của người thăm/bệnh nhân để chủ động chào hỏi.
* **Dẫn đường bằng giọng nói (`voice_nav_guide.py`):** Tiếp nhận câu lệnh thoại (ví dụ: *"Dẫn tôi đến phòng bác sĩ"*) và kích hoạt Goal trong Nav2 để đưa người dùng tới đích.

---

## 🚀 Hướng Dẫn Vận Hành Hệ Thống

### 1. Khởi chạy cầu nối Phần cứng & Vi điều khiển
```bash
ros2 run my_robot_bringup serial_bridge_node.py
```

### 2. Khởi chạy chế độ Quét Bản Đồ (SLAM)
```bash
ros2 launch my_robot_bringup Slam_launch.py
```

### 3. Khởi chạy Robot Tự Hành với Bản Đồ Bệnh Viện
```bash
ros2 launch my_robot_bringup nav2.launch.py map:=src/my_robot_bringup/maps/my_map.yaml
```

### 4. Khởi chạy Hệ Thống AI Vision & Hướng Dẫn Giọng Nói
```bash
ros2 launch my_robot_bringup voice_nav_guide.py
```

---

## 👨‍💻 Tác Giả & Liên Hệ (Author)

* **Họ và tên:** [Tên của bạn]
* **Vị trí ứng tuyển:** Embedded Software Engineer / ROS 2 Robotics Engineer / Autonomous System Developer
* **LinkedIn:** [Đường dẫn LinkedIn của bạn]
* **Email:** [Email liên hệ của bạn]