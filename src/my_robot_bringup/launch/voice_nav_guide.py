import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from google.cloud import speech, texttospeech
import os
import time

# --- CẤU HÌNH TỌA ĐỘ BỆNH VIỆN ---
# Bạn hãy thay x, y bằng tọa độ thực tế lấy từ Rviz2
DESTINATIONS = {
    "nhà thuốc": {"x": 1.2, "y": 0.5, "w": 1.0},
    "phòng khám": {"x": 3.5, "y": -1.2, "w": 1.0},
    "cổng chính": {"x": 0.0, "y": 0.0, "w": 1.0}
}

class BlindRobotVoiceNode(Node):
    def __init__(self):
        super().__init__('blind_robot_voice_node')
        
        # 1. Action Client gửi mục tiêu đến Nav2
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # 2. Khởi tạo Google Clients
        self.stt_client = speech.SpeechClient()
        self.tts_client = texttospeech.TextToSpeechClient()
        
        self.get_logger().info("Robot sẵn sàng! Đang chờ lệnh giọng nói...")
        self.speak("Chào bạn, tôi là robot dẫn đường. Bạn muốn đi đến đâu?")
        
        # Chạy vòng lặp lắng nghe
        self.main_loop()

    def speak(self, text):
        """Hàm chuyển văn bản thành tiếng Việt và phát ra loa"""
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="vi-VN", name="vi-VN-Wavenet-D" # Giọng nữ/nam tự nhiên
        )
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        
        response = self.tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        
        with open("speech.mp3", "wb") as out:
            out.write(response.audio_content)
        
        # Phát file mp3 bằng mpg123 (nhẹ và nhanh trên Ubuntu)
        os.system("mpg123 -q speech.mp3")

    def listen_from_mic(self):
        """Ghi âm từ Mic và gửi lên Google Cloud STT"""
        # Lưu ý: Đây là phiên bản ghi âm đơn giản dùng lệnh hệ thống
        # Để chuyên nghiệp hơn bạn có thể dùng thư viện 'sounddevice'
        print("Mời bạn nói...")
        os.system("arecord -d 4 -f cd -r 16000 test.wav") # Ghi âm 4 giây
        
        with open("test.wav", "rb") as f:
            content = f.read()
            
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="vi-VN"
        )
        
        try:
            response = self.stt_client.recognize(config=config, audio=audio)
            if response.results:
                return response.results[0].alternatives[0].transcript.lower()
        except Exception as e:
            print(f"Lỗi nhận diện: {e}")
        return ""

    def send_nav_goal(self, coords):
        """Gửi tọa độ mục tiêu tới Nav2 (MPPI + Thestar sẽ tự xử lý né vật cản)"""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        
        goal_msg.pose.pose.position.x = coords['x']
        goal_msg.pose.pose.position.y = coords['y']
        goal_msg.pose.pose.orientation.w = coords['w']

        self.get_logger().info(f"Đang gửi mục tiêu tới tọa độ: x={coords['x']}, y={coords['y']}")
        
        self._nav_client.wait_for_server()
        self._send_goal_future = self._nav_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.speak("Lệnh di chuyển bị từ chối.")
            return
        
        self.get_logger().info("Robot bắt đầu di chuyển...")
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        self.speak("Chúng ta đã đến nơi rồi. Chúc bạn một ngày tốt lành.")

    def main_loop(self):
        while rclpy.ok():
            command = self.listen_from_mic()
            if command:
                print(f"Bạn nói: {command}")
                found = False
                for place, coords in DESTINATIONS.items():
                    if place in command:
                        self.speak(f"Đã rõ, đang đưa bạn đến {place}.")
                        self.send_nav_goal(coords)
                        found = True
                        break
                if not found:
                    self.speak("Tôi chưa hiểu địa điểm này, bạn có thể nói lại không?")
            time.sleep(1)

def main(args=None):
    rclpy.init(args=args)
    node = BlindRobotVoiceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()