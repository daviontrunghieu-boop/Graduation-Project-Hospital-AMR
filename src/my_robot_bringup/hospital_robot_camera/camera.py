#!/usr/bin/env python3
from __future__ import annotations

import json
import time

import cv2

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
except ImportError:
    rclpy = None
    Node = object
    String = None


FACE_HOLD_SECONDS = 3.0
FACE_EVENT_TOPIC = "/hospital_robot/face_detection"


class FaceDetectionPublisher(Node):
    def __init__(self, topic_name: str) -> None:
        super().__init__("face_detection_publisher")
        self.publisher = self.create_publisher(String, topic_name, 10)
        self.get_logger().info(f"Face detection publisher ready on {topic_name}")

    def publish_face_detected(self, held_seconds: float) -> None:
        message = String()
        message.data = json.dumps(
            {
                "event": "face_detected_hold",
                "source": "hospital_robot_camera",
                "held_seconds": round(held_seconds, 2),
                "detected_at": time.time(),
            },
            ensure_ascii=True,
        )
        self.publisher.publish(message)
        self.get_logger().info(
            f"Published face_detected_hold after {held_seconds:.2f}s"
        )


def create_face_detector() -> cv2.CascadeClassifier:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        raise SystemExit("Khong load duoc Haar Cascade file")
    return detector


def open_camera() -> cv2.VideoCapture:
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise SystemExit("Khong mo duoc camera")
    return camera


def create_ros_publisher(topic_name: str) -> FaceDetectionPublisher | None:
    if rclpy is None or String is None:
        print("ROS2 chua san sang, khong the publish topic.")
        return None
    rclpy.init(args=None)
    return FaceDetectionPublisher(topic_name)


def publish_face_event(node: FaceDetectionPublisher | None, held_seconds: float) -> None:
    if node is None:
        print(f"Face detected for {held_seconds:.2f}s but ROS2 is unavailable.")
        return
    node.publish_face_detected(held_seconds)
    rclpy.spin_once(node, timeout_sec=0.0)


def main() -> None:
    camera = open_camera()
    face_detector = create_face_detector()
    publisher_node = create_ros_publisher(FACE_EVENT_TOPIC)

    face_start_time: float | None = None
    event_sent = False

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("Khong doc duoc camera")
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_detector.detectMultiScale(
                gray,
                scaleFactor=1.2,
                minNeighbors=5,
                minSize=(80, 80),
            )

            if len(faces) == 1:
                x, y, w, h = faces[0]

                if face_start_time is None:
                    face_start_time = time.time()

                held_seconds = time.time() - face_start_time

                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    f"Detected: {held_seconds:.1f}s",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

                if held_seconds >= FACE_HOLD_SECONDS and not event_sent:
                    publish_face_event(publisher_node, held_seconds)
                    event_sent = True

            elif len(faces) > 1:
                face_start_time = None
                event_sent = False

                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)

                cv2.putText(
                    frame,
                    "Multiple faces detected",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2,
                )

            else:
                face_start_time = None
                event_sent = False

                cv2.putText(
                    frame,
                    "Waiting for face",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

            cv2.imshow("Robot Camera - Haar Cascade", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        if publisher_node is not None:
            publisher_node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
