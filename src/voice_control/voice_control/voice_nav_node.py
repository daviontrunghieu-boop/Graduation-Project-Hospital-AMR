import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose

import asyncio
import json
import websockets
import pyaudio
import pyttsx3
import re
import os
import threading

# 🔑 API KEY CỦA BẠN (DEEPGRAM)
DEEPGRAM_API_KEY = "a6fea495d7536bac430294dc1fb71e10c710cab9"

class VoiceNavNode(Node):
    def __init__(self):
        super().__init__('voice_nav_node')
        
        # 1. Action Client để điều hướng Nav2
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # 2. Khởi tạo Loa (TTS)
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150) # Tốc độ nói, bạn có thể chỉnh nhanh chậm ở đây
        
        # 3. Đường dẫn file dữ liệu chính xác (Đã cập nhật theo yêu cầu)
        self.data_path = "/home/hieu/ros2_ws/src/my_robot_web_config/robot_web_interface/user_information/patient_information.json"
        
        self.get_logger().info("🤖 Robot Hospital Voice đã sẵn sàng (Deepgram + Nav2)...")
        self.speak("Hệ thống đã sẵn sàng. Vui lòng đọc số thứ tự để tôi dẫn đường.")

    def speak(self, text):
        """Hàm giúp Robot phát ra tiếng nói"""
        self.get_logger().info(f"Robot nói: {text}")
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()

    def load_patient_data(self):
        """Đọc file JSON mỗi khi có lệnh để đảm bảo dữ liệu mới nhất được đồng bộ từ Web"""
        if not os.path.exists(self.data_path):
            self.get_logger().error(f"Lỗi: Không tìm thấy file tại {self.data_path}")
            return None
        
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.get_logger().error(f"Lỗi đọc JSON: {e}")
            return None

    def process_command(self, transcript):
        """Xử lý văn bản từ Deepgram"""
        text = transcript.lower()
        self.get_logger().info(f"🎤 Robot nghe thấy: {text}")

        # Tìm TẤT CẢ các số trong câu nói
        numbers = re.findall(r'\d+', text)
        if not numbers:
            # Bỏ qua nếu không có số nào
            return

        # Tra cứu dữ liệu từ file JSON
        data = self.load_patient_data()
        if not data:
            self.speak("Xin lỗi, hệ thống chưa kết nối được với dữ liệu bệnh nhân.")
            return

        # Lấy danh sách hàng đợi (queue_index)
        queue_index = data.get("queue_index", {})
        
        found_patient = None
        
        # Kiểm tra xem có số nào trong câu nói trùng với Số thứ tự (STT) trong hàng đợi không
        for num in numbers:
            if num in queue_index:
                found_patient = queue_index[num]
                break # Tìm thấy STT hợp lệ là dừng vòng lặp luôn
                
        if found_patient:
            name = found_patient.get("patient_name", "bạn")
            room = found_patient.get("room_label", "")
            pose_dict = found_patient.get("destination_pose", {})
            
            # Kiểm tra xem phòng đó có cấu hình tọa độ chưa
            if pose_dict.get("configured", False):
                self.speak(f"Xác nhận số thứ tự của {name}. Mời bạn đi theo tôi đến {room}")
                self.send_navigation_goal(pose_dict)
            else:
                self.speak(f"Xin lỗi {name}, tọa độ của {room} chưa được lưu trên hệ thống.")
        else:
            self.speak("Tôi không tìm thấy số thứ tự này, vui lòng đọc lại.")

    def send_navigation_goal(self, pose_dict):
        """Gửi tọa độ mục tiêu xuống Nav2 để Robot tự chạy"""
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 Action Server không phản hồi! Hãy chắc chắn bạn đã bật Nav2.")
            self.speak("Hệ thống dẫn đường đang gặp lỗi.")
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        
        # Lấy X, Y, Z, W từ JSON truyền vào
        goal_msg.pose.pose.position.x = float(pose_dict.get("x", 0.0))
        goal_msg.pose.pose.position.y = float(pose_dict.get("y", 0.0))
        goal_msg.pose.pose.position.z = float(pose_dict.get("z", 0.0))
        
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = 0.0
        goal_msg.pose.pose.orientation.w = float(pose_dict.get("w", 1.0))

        self.get_logger().info(f"🚀 Đang di chuyển đến mục tiêu: X={goal_msg.pose.pose.position.x}, Y={goal_msg.pose.pose.position.y}")
        self._nav_client.send_goal_async(goal_msg)

    async def start_listening(self):
        """Khởi động luồng lắng nghe liên tục qua Deepgram WebSocket"""
        URL = "wss://api.deepgram.com/v1/listen?language=vi&model=nova-2&smart_format=true&interim_results=false&keepalive=true&encoding=linear16&sample_rate=16000&channels=1"
        
        try:
            async with websockets.connect(URL, extra_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"}) as ws:
                
                # Cấu hình Micro
                audio = pyaudio.PyAudio()
                stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
                
                async def send_audio():
                    while True:
                        try:
                            data = stream.read(4000, exception_on_overflow=False)
                            await ws.send(data)
                            await asyncio.sleep(0.01)
                        except Exception as e:
                            self.get_logger().error(f"Lỗi gửi audio: {e}")
                            break

                async def receive_text():
                    async for message in ws:
                        data = json.loads(message)
                        if data.get("type") == "Results":
                            alternatives = data.get("channel", {}).get("alternatives", [])
                            if alternatives:
                                transcript = alternatives[0].get("transcript", "")
                                if transcript.strip():
                                    self.process_command(transcript)

                self.get_logger().info("👂 Đang lắng nghe âm thanh từ môi trường...")
                await asyncio.gather(send_audio(), receive_text())
                
        except Exception as e:
            self.get_logger().error(f"Lỗi kết nối Deepgram: {e}")
            self.speak("Không thể kết nối với hệ thống nhận diện giọng nói.")

def main(args=None):
    rclpy.init(args=args)
    node = VoiceNavNode()
    
    # --- THÊM ĐOẠN NÀY ---
    # Chạy ROS 2 spin trong một luồng riêng biệt để Action Client đẩy dữ liệu đi
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()
    # ---------------------
    
    # Chạy vòng lặp asyncio cho WebSockets (Deepgram)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(node.start_listening())
    except KeyboardInterrupt:
        node.get_logger().info("🛑 Đã dừng tiến trình voice_nav_node.")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()