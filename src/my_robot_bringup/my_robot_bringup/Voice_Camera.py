#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String  # Thêm thư viện để nhận dữ liệu từ Camera
from nav2_msgs.action import NavigateToPose

import asyncio
import json
import websockets
import pyaudio
import requests
from vieneu import Vieneu
import re
import os
import subprocess
import threading
import time

# 🔑 API KEY CỦA BẠN (DEEPGRAM)
DEEPGRAM_API_KEY = "a6fea495d7536bac430294dc1fb71e10c710cab9"

class VoiceNavNode(Node):
    def __init__(self):
        super().__init__('voice_nav_node')
        
        # 1. Action Client để điều hướng Nav2
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # 2. Bộ đăng ký (Subscriber) lắng nghe dữ liệu từ Node Camera của bạn
        self.face_sub = self.create_subscription(
            String,
            '/hospital_robot/face_detection',
            self.face_callback,
            10
        )
        
        # 3. Khởi tạo VieNeu TTS
        self.tts = Vieneu(mode="turbo")
        
        # 4. Đường dẫn file dữ liệu triệu chứng Admin
        self.symptom_file_path = "/home/hieu/ros2_ws/src/my_robot_web_config/symptom_room_rules.json"
        
        # 5. Bảng tọa độ phòng khám
        self.room_poses = {
            "101": {"x": 1.2, "y": 0.5, "z": 0.0, "w": 1.0},
            "102": {"x": 2.5, "y": -1.0, "z": 0.0, "w": 1.0},
            "phòng khám tai mũi họng": {"x": 3.0, "y": 1.5, "z": 0.0, "w": 1.0},
            "phòng răng hàm mặt": {"x": -1.5, "y": 2.0, "z": 0.0, "w": 1.0}
        }
        
        # 6. Quản lý trạng thái cuộc hội thoại (Đã thêm trạng thái WAITING_FACE)
        # Các trạng thái tiến trình: IDLE -> WAITING_SYMPTOM -> WAITING_FACE -> WAITING_READY -> NAVIGATING
        self.state = "IDLE"             
        self.is_listening = True        
        self.target_pose = None         
        
        self.get_logger().info("🤖 Node Giọng nói + Camera tích hợp đã sẵn sàng...")
        threading.Thread(target=self.start_conversation, daemon=True).start()

    def start_conversation(self):
        """Khởi động hoặc thiết lập lại cuộc trò chuyện"""
        self.is_listening = False
        self.state = "IDLE"
        self.speak("Tôi là au rô ra, tôi có thể giúp gì cho bạn.")
        self.is_listening = True

    def speak(self, text):
        """Hàm phát giọng nói đồng bộ chặn luồng"""
        self.get_logger().info(f"Robot nói (TTS): {text}")
        try:
            audio_data = self.tts.infer(text=text)
            temp_file = "/tmp/robot_speech.wav"
            self.tts.save(audio_data, temp_file)
            subprocess.run(["aplay", "-q", temp_file])
        except Exception as e:
            self.get_logger().error(f"❌ Lỗi VieNeu-TTS: {e}")

    def load_symptom_rules(self):
        """Đọc file cấu hình triệu chứng của Admin"""
        if not os.path.exists(self.symptom_file_path):
            return []
        try:
            with open(self.symptom_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def face_callback(self, msg):
        """Hàm xử lý dữ liệu truyền về từ Node Camera của bạn"""
        # CHỈ XỬ LÝ khi robot đang ở trạng thái chờ xác nhận khuôn mặt bệnh nhân
        if self.state != "WAITING_FACE":
            return
            
        try:
            data = json.loads(msg.data)
            if data.get("event") == "face_detected_hold":
                self.get_logger().info("📸 Camera xác nhận: Đã giữ khuôn mặt thành công 3 giây!")
                
                # Chuyển trạng thái trong một Thread riêng để không làm nghẽn luồng callback của ROS2
                threading.Thread(target=self.transition_to_ready, daemon=True).start()
        except Exception as e:
            self.get_logger().error(f"Lỗi phân tích JSON từ Camera: {e}")

    def transition_to_ready(self):
        """Hàm chuyển giao từ nhận diện khuôn mặt sang hỏi sẵn sàng"""
        self.is_listening = False
        self.state = "WAITING_READY"
        self.speak("Hệ thống đã xác nhận thông tin khuôn mặt. Bạn đã sẵn sàng di chuyển chưa?")
        self.is_listening = True

    def process_command(self, transcript):
        """Bộ điều phối Cỗ máy trạng thái qua giọng nói (STT)"""
        if not self.is_listening or self.state == "NAVIGATING":
            return
            
        text = transcript.lower().strip()
        if not text:
            return

        self.get_logger().info(f"🎤 Nghe thấy: {text} | [Trạng thái: {self.state}]")
        self.is_listening = False 

        # BƯỚC 1: Chờ câu lệnh mở đầu
        if self.state == "IDLE":
            if "khám bệnh" in text or "khám" in text:
                self.speak("Bạn hãy nói triệu chứng của bạn.")
                self.state = "WAITING_SYMPTOM"
            else:
                self.speak("Nếu bạn muốn đi khám bệnh, hãy nói: tôi đi khám bệnh.")

        # BƯỚC 2: Kiểm tra triệu chứng và hướng dẫn đứng trước camera
        elif self.state == "WAITING_SYMPTOM":
            rules = self.load_symptom_rules()
            found_rule = None
            
            for rule in rules:
                keyword = rule.get("symptom_keywords", "").lower().strip()
                if keyword and keyword in text:
                    found_rule = rule
                    break
                    
            if found_rule:
                department = found_rule.get("department", "Khoa chuyên môn")
                room_label = found_rule.get("room_label", "").lower().strip()
                
                if room_label in self.room_poses:
                    self.target_pose = self.room_poses[room_label]
                    
                    # Thông báo phân khoa và yêu cầu bệnh nhân đứng yên nhìn vào camera
                    self.speak(f"Tôi sẽ dẫn bạn đến khoa {department}, phòng {found_rule.get('room_label')}. Vui lòng bạn đứng yên nhìn vào màn hình camera và đặt hai tay lên tay nắm.")
                    
                    # CHUYỂN SANG BƯỚC CHỜ CAMERA: Lúc này STT sẽ không làm gì cả, đợi camera gửi tín hiệu topic
                    self.state = "WAITING_FACE"
                    self.get_logger().info("⏳ Đang chuyển giao quyền điều khiển, chờ tín hiệu từ Camera...")
                else:
                    self.speak(f"Tôi tìm thấy khoa {department} phòng {found_rule.get('room_label')}, nhưng phòng này chưa được nạp tọa độ di chuyển.")
                    self.state = "IDLE"
            else:
                self.speak("Tôi chưa rõ triệu chứng này, bạn có thể nói rõ hơn được không?")

        # BƯỚC 3: Nhắc nhở nếu đang trong tiến trình nhận diện mặt mà bệnh nhân nói leo vào
        elif self.state == "WAITING_FACE":
            self.get_logger().info("🤖 Robot đang đợi camera quét khuôn mặt, tạm thời bỏ qua giọng nói.")

        # BƯỚC 4: Chờ xác nhận di chuyển sau khi camera đã quét xong
        elif self.state == "WAITING_READY":
            ready_keywords = ["rồi", "sẵn sàng", "ok", "đi thôi", "vâng", "được", "đi"]
            if any(kw in text for kw in ready_keywords):
                self.speak("Xác nhận. Chúng ta bắt đầu đi.")
                self.state = "NAVIGATING"
                self.send_navigation_goal(self.target_pose)
            else:
                self.speak("Nếu bạn đã sẵn sàng đi, hãy trả lời: đã sẵn sàng.")

        if self.state != "NAVIGATING" and self.state != "WAITING_FACE":
            self.is_listening = True

    def send_navigation_goal(self, pose_dict):
        """Gửi tọa độ mục tiêu xuống Nav2 (Giữ nguyên thuật toán gốc của bạn)"""
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 Action Server không phản hồi!")
            self.speak("Hệ thống di chuyển định vị đang gặp sự cố.")
            threading.Thread(target=self.start_conversation, daemon=True).start()
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(pose_dict.get("x", 0.0))
        goal_msg.pose.pose.position.y = float(pose_dict.get("y", 0.0))
        goal_msg.pose.pose.orientation.w = float(pose_dict.get("w", 1.0))

        self._send_goal_future = self._nav_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.speak("Điểm đến này không hợp lệ.")
            threading.Thread(target=self.start_conversation, daemon=True).start()
            return
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        self.speak("Chúng ta đã đến nơi rồi. Chúc bạn khám bệnh thuận lợi.")
        threading.Thread(target=self.start_conversation, daemon=True).start()

    async def start_listening(self):
        """Khởi động luồng lắng nghe Deepgram WebSocket"""
        URL = "wss://api.deepgram.com/v1/listen?language=vi&model=nova-2&smart_format=true&interim_results=false&endpointing=300&keepalive=true&encoding=linear16&sample_rate=16000&channels=1"
        try:
            async with websockets.connect(URL, extra_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"}) as ws:
                audio = pyaudio.PyAudio()
                stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
                
                async def send_audio():
                    while True:
                        try:
                            data = stream.read(4000, exception_on_overflow=False)
                            await ws.send(data)
                            await asyncio.sleep(0.01)
                        except Exception:
                            break

                async def receive_text():
                    async for message in ws:
                        data = json.loads(message)
                        if data.get("type") == "Results":
                            alternatives = data.get("channel", {}).get("alternatives", [])
                            if alternatives and alternatives[0].get("transcript", "").strip():
                                transcript = alternatives[0].get("transcript", "")
                                threading.Thread(target=self.process_command, args=(transcript,), daemon=True).start()

                await asyncio.gather(send_audio(), receive_text())
        except Exception as e:
            self.get_logger().error(f"Lỗi Deepgram: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = VoiceNavNode()
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(node.start_listening())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()