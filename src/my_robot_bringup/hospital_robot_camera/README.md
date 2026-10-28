# hospital_robot_camera

Thu muc nay da duoc gom rieng de copy sang may Ubuntu.

## File chinh

- `camera.py`: detect khuon mat bang Haar Cascade va publish event ROS2 sau khi thay 1 khuon mat lien tuc trong 3 giay.
- `face_prompt_listener.py`: node mau de subscribe topic va xu ly phan hoi o node khac.
- `requirements.txt`: danh sach thu vien can co.

## Topic ROS2

- Publisher: `/hospital_robot/face_detection`

## Message duoc gui tu `camera.py`

```json
{
  "event": "face_detected_hold",
  "source": "hospital_robot_camera",
  "held_seconds": 3.01,
  "detected_at": 1747770000.0
}
```

## Cach copy sang Ubuntu

Copy nguyen folder `hospital_robot_camera/` sang may Ubuntu.

## Chay `camera.py`

```bash
python3 camera.py
```

Neu chay trong moi truong ROS2, can source ROS2 truoc khi chay:

```bash
source /opt/ros/<distro>/setup.bash
python3 camera.py
```

## Goi y cai dat tren Ubuntu

`rclpy` va `std_msgs` thuong duoc cai cung ROS2, khong cai bang `pip`.

`opencv-python` co the cai bang:

```bash
pip3 install opencv-python
```

Hoac:

```bash
sudo apt install python3-opencv
```
