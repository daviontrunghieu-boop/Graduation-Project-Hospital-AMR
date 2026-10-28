#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String

import asyncio
import json
import websockets
import pyaudio
from vieneu import Vieneu
import os
import threading
import time
import subprocess
import re

# Bạn nhớ điền lại API key của bạn vào đây nhé
DEEPGRAM_API_KEY = "a6fea495d7536bac430294dc1fb71e10c710cab9"  

class VoiceNavNode(Node):
    def __init__(self):
        super().__init__('voice_nav_node')
        
        self.cb_group = ReentrantCallbackGroup()
        
        self._nav_client = ActionClient(
            self, NavigateToPose, 'navigate_to_pose', 
            callback_group=self.cb_group
        )
        
        self.tts = Vieneu(mode="turbo")
        self.tts_lock = threading.Lock() 
        
        self.face_sub = self.create_subscription(
            String,
            '/hospital_robot/face_detection',
            self.face_detection_callback,
            10,
            callback_group=self.cb_group
        )
        
        # --- ĐƯỜNG DẪN TỚI FILE JSON ---
        self.data_path = "/home/hieu/ros2_ws/src/my_robot_web_config/robot_web_interface/user_information/patient_information.json"
        
        # --- NẠP SẴN DỮ LIỆU JSON VÀO RAM KHI KHỞI ĐỘNG ---
        self.patient_data = self.load_patient_data()
        
        # --- CÁC TRẠNG THÁI GIAO TIẾP (STATE MACHINE) ---
        self.bot_state = "IDLE" 
        self.last_greet_time = 0 
        self.cooldown_seconds = 20.0
        self.target_pose = None 
        
        # --- CỜ HIỆU CHẶN MIC KHI ĐANG NÓI ---
        self.is_speaking = False 
        
        # --- CÁC FILE ÂM THANH CỐ ĐỊNH ---
        self.ask_help_file = "/tmp/robot_ask_help.wav"
        self.ask_symptoms_file = "/tmp/robot_ask_symptoms.wav"
        self.ask_ready_file = "/tmp/robot_ask_ready.wav"
        self.ready_file = "/tmp/robot_system_ready.wav"
        self.arrived_file = "/tmp/robot_arrived.wav"
        self.err_file = "/tmp/robot_error.wav"
        self.not_found_file = "/tmp/robot_not_found.wav" 
        
        self.get_logger().info("🤖 Robot Hospital Voice đang khởi động...")
        threading.Thread(target=self.prepare_audio_cache, daemon=True).start()

    def prepare_audio_cache(self):
        audio_tasks = [
            (self.ask_help_file, "Chào bạn, bạn cần giúp gì?"),
            (self.ask_symptoms_file, "Bạn hãy đọc số thứ tự hoặc nói triệu chứng của bạn."),
            (self.ask_ready_file, "Bạn đã sẵn sàng chưa?"),
            (self.ready_file, "Hệ thống đã sẵn sàng hoạt động."),
            (self.arrived_file, "Đã đến nơi. Chúc bạn khám bệnh thuận lợi."),
            (self.err_file, "Xin lỗi, tôi chưa hiểu rõ, bạn có thể nói lại được không?"),
            (self.not_found_file, "Tôi không tìm thấy thông tin phù hợp. Bạn hãy nói lại nhé.")
        ]
        
        self.get_logger().info("⏳ Đang tạo bộ nhớ đệm các câu nói...")
        
        for file_path, text in audio_tasks:
            if not os.path.exists(file_path):
                try:
                    with self.tts_lock:
                        audio_data = self.tts.infer(text=text)
                        self.tts.save(audio_data, file_path)
                except Exception as e:
                    self.get_logger().error(f"❌ Lỗi khi chuẩn bị file '{text}': {e}")
        
        self.get_logger().info("✅ Đã chuẩn bị xong âm thanh!")
        self.play_cached_audio(self.ready_file, "Hệ thống đã sẵn sàng hoạt động.")

    def play_cached_audio(self, file_path, fallback_text):
        if os.path.exists(file_path):
            def run_cached():
                self.is_speaking = True
                time.sleep(0.3)
                subprocess.run(["paplay", file_path])
                time.sleep(0.5)
                self.is_speaking = False
            threading.Thread(target=run_cached, daemon=True).start()
        else:
            self.speak(fallback_text)

    def speak(self, text):
        self.get_logger().info(f"Robot nói: {text}")
        def run_speak():
            with self.tts_lock:
                try:
                    self.is_speaking = True
                    time.sleep(0.3)
                    audio_data = self.tts.infer(text=text)
                    temp_file = f"/tmp/robot_speech_{int(time.time()*1000)}.wav"
                    self.tts.save(audio_data, temp_file)
                    subprocess.run(["paplay", temp_file])
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    self.get_logger().error(f"❌ Lỗi khi xử lý giọng nói: {e}")
                finally:
                    time.sleep(0.5)
                    self.is_speaking = False
        threading.Thread(target=run_speak, daemon=True).start()

    def load_patient_data(self):
        if not os.path.exists(self.data_path):
            self.get_logger().error(f"Lỗi: Không tìm thấy file JSON tại {self.data_path}")
            return None
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.get_logger().error(f"Lỗi đọc JSON: {e}")
            return None

    def face_detection_callback(self, msg):
        if self.bot_state != "IDLE":
            return 
        current_time = time.time()
        if current_time - self.last_greet_time > self.cooldown_seconds:
            self.get_logger().info("👀 Phát hiện bệnh nhân. Bắt đầu hỏi thăm...")
            self.bot_state = "ASKED_HELP"
            self.play_cached_audio(self.ask_help_file, "Chào bạn, bạn cần giúp gì?")
            self.last_greet_time = current_time

    def delayed_ask_ready(self):
        time.sleep(1.0)
        while self.is_speaking:
            time.sleep(0.5)
        time.sleep(1.0)
        if self.bot_state == "WAITING_GRASP":
            self.bot_state = "ASKED_READY"
            self.play_cached_audio(self.ask_ready_file, "Bạn đã sẵn sàng chưa?")

    def process_command(self, transcript):
        original_text = transcript.lower()
        if not original_text.strip():
            return

        self.get_logger().info(f"🎤 Bệnh nhân nói: {original_text} | Trạng thái hiện tại: {self.bot_state}")

        if self.bot_state == "ASKED_HELP":
            if any(word in original_text for word in ["khám", "đi khám", "giúp"]):
                self.bot_state = "ASKED_SYMPTOMS"
                self.play_cached_audio(self.ask_symptoms_file, "Bạn hãy đọc số thứ tự hoặc nói triệu chứng của bạn.")
            else:
                self.play_cached_audio(self.err_file, "Xin lỗi, tôi chưa hiểu.")

        elif self.bot_state == "ASKED_SYMPTOMS":
            self.patient_data = self.load_patient_data()
            if not self.patient_data:
                self.play_cached_audio(self.err_file, "Lỗi hệ thống dữ liệu.")
                return

            queue_index = self.patient_data.get("queue_index", {})
            patients = self.patient_data.get("patients", {})
            room_destinations = self.patient_data.get("room_destinations", {})
            
            found_department = None
            found_room_label = None

            # --- BƯỚC 1: TIỀN XỬ LÝ TEXT (DỊCH CHỮ SỐ TIẾNG VIỆT THÀNH CON SỐ) ---
            text_for_numbers = original_text
            vn_numbers = {
                "hai mươi": "20", "mười chín": "19", "mười tám": "18", "mười bảy": "17", 
                "mười sáu": "16", "mười lăm": "15", "mười bốn": "14", "mười ba": "13", 
                "mười hai": "12", "mười một": "11", "mười": "10",
                "chín": "9", "tám": "8", "bảy": "7", "sáu": "6", 
                "năm": "5", "bốn": "4", "ba": "3", "hai": "2", "một": "1"
            }
            for word, digit in vn_numbers.items():
                text_for_numbers = text_for_numbers.replace(word, digit)

            # Lấy toàn bộ các cụm số từ câu nói đã xử lý
            numbers_in_text = re.findall(r'\d+', text_for_numbers)

            # --- BƯỚC 2: QUÉT TRONG QUEUE_INDEX TRƯỚC ---
            for q_id, q_info in queue_index.items():
                q_id_str = str(q_id).strip()
                queue_num = str(q_info.get("queue_number", "")).strip()
                order_lbl = str(q_info.get("order_label", "")).lower().strip() # vd: "stt 12"

                if (order_lbl and order_lbl in original_text) or (q_id_str in numbers_in_text) or (queue_num in numbers_in_text):
                    found_department = q_info.get("department")
                    found_room_label = str(q_info.get("room_label", ""))
                    self.get_logger().info(f"🎯 Khớp STT: {q_id_str} -> Khoa: {found_department}, Phòng: {found_room_label}")
                    break

            # --- BƯỚC 3: NẾU KHÔNG THẤY STT, CHUYỂN SANG DUYỆT TRIỆU CHỨNG ---
            if not found_department:
                for p_id, p_info in patients.items():
                    db_symptoms_str = p_info.get("symptoms", "").lower()
                    symptom_list = [s.strip() for s in db_symptoms_str.split(',')]
                    for s in symptom_list:
                        if s and s in original_text:
                            found_department = p_info.get("department", "phòng khám")
                            found_room_label = str(p_info.get("room_label", ""))
                            self.get_logger().info(f"🎯 Khớp Triệu Chứng: '{s}' -> Khoa: {found_department}, Phòng: {found_room_label}")
                            break
                    if found_department:
                        break

            # --- BƯỚC 4: THỰC THI NẾU TÌM ĐƯỢC ---
            if found_department and found_room_label in room_destinations:
                self.target_pose = room_destinations[found_room_label]
                self.bot_state = "WAITING_GRASP"
                
                self.speak(f"Tôi đã tìm thấy thông tin. Tôi sẽ dẫn bạn đến {found_department}, vui lòng bạn đặt hai tay lên tay nắm.")
                threading.Thread(target=self.delayed_ask_ready, daemon=True).start()
            else:
                self.play_cached_audio(self.not_found_file, "Tôi không tìm thấy khoa phù hợp hoặc phòng này chưa được cấu hình tọa độ. Bạn hãy nói lại nhé.")

        elif self.bot_state == "ASKED_READY":
            confirm_keywords = ["rồi", "sẵn sàng", "ok", "đi", "được"]
            if any(word in original_text for word in confirm_keywords):
                self.bot_state = "NAVIGATING"
                self.speak("Chúng ta bắt đầu đi.")
                self.send_navigation_goal(self.target_pose)
            elif "chưa" in original_text or "từ từ" in original_text:
                self.speak("Vâng, bạn hãy bám chắc tay nắm, khi nào xong hãy nói 'Đã sẵn sàng'.")

    def send_navigation_goal(self, pose_dict):
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 Action Server không phản hồi!")
            self.speak("Hệ thống định vị đang gặp sự cố.")
            self.bot_state = "IDLE"
            return

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        
        goal_msg.pose.pose.position.x = float(pose_dict.get("x", 0.0))
        goal_msg.pose.pose.position.y = float(pose_dict.get("y", 0.0))
        goal_msg.pose.pose.position.z = float(pose_dict.get("z", 0.0))
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = 0.0
        goal_msg.pose.pose.orientation.w = float(pose_dict.get("w", 1.0))
        
        self.get_logger().info(f"🚀 Bắt đầu di chuyển tới điểm: X={goal_msg.pose.pose.position.x}, Y={goal_msg.pose.pose.position.y}")
        
        self._send_goal_future = self._nav_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.speak("Điểm đến có vẻ đang bị chặn đường.")
            self.bot_state = "IDLE"
            return
        
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        self.get_logger().info("🎉 Đã đến nơi!")
        self.play_cached_audio(self.arrived_file, "Đã đến nơi. Chúc bạn khám bệnh thuận lợi.")
        self.bot_state = "IDLE" 
        self.last_greet_time = time.time()

    async def start_listening(self):
        URL = "wss://api.deepgram.com/v1/listen?language=vi&model=nova-2&smart_format=true&encoding=linear16&sample_rate=16000&channels=1"
        
        while rclpy.ok():
            stream = None
            audio = None
            try:
                async with websockets.connect(URL, extra_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"}) as ws:
                    loop = asyncio.get_running_loop()
                    audio = pyaudio.PyAudio()
                    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
                    
                    async def send_audio():
                        while True:
                            try:
                                data = await loop.run_in_executor(None, stream.read, 4000, False)
                                if not self.is_speaking:
                                    await ws.send(data)
                                else:
                                    await ws.send(json.dumps({"type": "KeepAlive"}))
                                    await asyncio.sleep(0.25)
                            except websockets.exceptions.ConnectionClosed:
                                break
                            except Exception:
                                await asyncio.sleep(0.1)

                    async def receive_text():
                        try:
                            async for message in ws:
                                data = json.loads(message)
                                if data.get("type") == "Results":
                                    alternatives = data.get("channel", {}).get("alternatives", [])
                                    if alternatives:
                                        transcript = alternatives[0].get("transcript", "")
                                        if transcript.strip():
                                            threading.Thread(target=self.process_command, args=(transcript,), daemon=True).start()
                        except websockets.exceptions.ConnectionClosed:
                            pass

                    await asyncio.gather(send_audio(), receive_text())
                    
            except Exception as e:
                # --- ĐOẠN ĐÃ ĐƯỢC CẬP NHẬT ĐỂ IN RA LỖI CHI TIẾT ---
                self.get_logger().error(f"⚠️ Lỗi kết nối Deepgram chi tiết: {type(e).__name__} - {str(e)}")
                self.get_logger().error("Đang tự động thử lại sau 3s...")
                await asyncio.sleep(3.0)
            finally:
                if stream:
                    try: stream.stop_stream(); stream.close()
                    except: pass
                if audio:
                    try: audio.terminate()
                    except: pass

def main(args=None):
    rclpy.init(args=args)
    node = VoiceNavNode()
    
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(node.start_listening())
    except KeyboardInterrupt:
        node.get_logger().info("🛑 Đã dừng tiến trình voice_nav_node.")
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()

if __name__ == '__main__':
    main()