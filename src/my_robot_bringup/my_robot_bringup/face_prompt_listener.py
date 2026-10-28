from __future__ import annotations

import json
import platform

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
except ImportError:
    rclpy = None
    Node = object
    String = None


PROMPT_TOPIC = "/hospital_robot/face_prompt"


def robot_speak(text: str) -> None:
    print(f"Robot: {text}")
    system_name = platform.system()

    if system_name == "Windows":
        import pyttsx3

        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    elif system_name == "Linux":
        import os

        os.system(f'espeak "{text}"')


class FacePromptListener(Node):
    def __init__(self) -> None:
        super().__init__("face_prompt_listener")
        self.subscription = self.create_subscription(
            String,
            PROMPT_TOPIC,
            self.handle_prompt,
            10,
        )
        self.get_logger().info(f"Listening for face prompts on {PROMPT_TOPIC}")

    def handle_prompt(self, msg: String) -> None:
        text = msg.data
        try:
            payload = json.loads(msg.data)
            if isinstance(payload, dict):
                text = str(payload.get("text", text))
        except json.JSONDecodeError:
            pass

        robot_speak(text)
        self.get_logger().info(f"Spoke prompt: {text}")


def main(args: list[str] | None = None) -> None:
    if rclpy is None or String is None:
        raise SystemExit("rclpy va std_msgs la bat buoc de chay face_prompt_listener.py")

    rclpy.init(args=args)
    node = FacePromptListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
