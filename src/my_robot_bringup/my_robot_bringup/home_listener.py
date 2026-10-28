#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped


class HomeListener(Node):
    def __init__(self):
        super().__init__("home_listener")

        # Khai báo các tham số hệ thống
        self.declare_parameter(
            "command_file",
            "/home/hieu/ros2_ws/src/my_robot_web_config/robot_command.json",
        )
        self.declare_parameter("goal_topic", "/goal_pose")
        self.declare_parameter("frame_id", "map")  # Đồng bộ hoàn toàn với global_frame của Nav2
        self.declare_parameter("check_period", 0.5)

        # Lấy giá trị từ tham số
        self.command_file = Path(
            self.get_parameter("command_file").get_parameter_value().string_value
        )
        self.goal_topic = self.get_parameter("goal_topic").get_parameter_value().string_value
        self.frame_id = self.get_parameter("frame_id").get_parameter_value().string_value
        self.check_period = self.get_parameter("check_period").get_parameter_value().double_value

        # Khởi tạo Publisher
        self.publisher = self.create_publisher(PoseStamped, self.goal_topic, 10)

        # Lưu trạng thái lệnh lúc node vừa mở để tránh robot tự chạy ngay khi launch
        self.last_signature = self.read_current_signature()

        # Khởi tạo Timer kiểm tra file JSON liên tục
        self.timer = self.create_timer(self.check_period, self.check_command_file)

        self.get_logger().info("=========================================")
        self.get_logger().info("HOME listener started successfully!")
        self.get_logger().info(f"Reading command file: {self.command_file}")
        self.get_logger().info(f"Publishing HOME goal to topic: {self.goal_topic}")
        self.get_logger().info(f"Synchronized Frame ID: {self.frame_id}")
        self.get_logger().info(f"Initial command signature ignored: {self.last_signature}")
        self.get_logger().info("=========================================")

    def read_current_signature(self) -> str:
        if not self.command_file.exists():
            return ""

        try:
            data = json.loads(self.command_file.read_text(encoding="utf-8"))
        except Exception:
            return ""

        command = str(data.get("command", ""))
        status = str(data.get("status", ""))
        created_at = str(data.get("created_at", ""))
        return f"{command}|{status}|{created_at}"

    def check_command_file(self):
        if not self.command_file.exists():
            return

        try:
            data = json.loads(self.command_file.read_text(encoding="utf-8"))
        except Exception as error:
            self.get_logger().warning(f"Cannot read command file: {error}")
            return

        command = str(data.get("command", ""))
        status = str(data.get("status", ""))
        created_at = str(data.get("created_at", ""))

        signature = f"{command}|{status}|{created_at}"

        # Không xử lý lại lệnh cũ nếu signature không thay đổi
        if signature == self.last_signature:
            return

        self.get_logger().info(
            f"Command changed: command={command}, status={status}, created_at={created_at}"
        )

        self.last_signature = signature

        # Chỉ xử lý nếu lệnh là go_home và trạng thái là pending
        if command != "go_home":
            return

        if status != "pending":
            return

        pose = data.get("pose", {})
        if not isinstance(pose, dict):
            self.get_logger().warning("Invalid pose data in command file")
            return

        try:
            x = float(pose.get("x", 0.0))
            y = float(pose.get("y", 0.0))
            z = float(pose.get("z", 0.0))
            w = float(pose.get("w", 1.0))
        except Exception as error:
            self.get_logger().warning(f"Invalid pose values: {error}")
            return

        # Tạo và đồng bộ hóa thông tin PoseStamped gửi sang Nav2
        goal = PoseStamped()
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.header.frame_id = self.frame_id  # Đảm bảo sử dụng "map" frame đồng bộ hệ thống

        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.position.z = 0.0

        # Quaternion định hướng robot
        goal.pose.orientation.x = 0.0
        goal.pose.orientation.y = 0.0
        goal.pose.orientation.z = z
        goal.pose.orientation.w = w

        # Gửi tọa độ đi
        self.publisher.publish(goal)

        self.get_logger().info(
            f"PUBLISHED HOME GOAL: x={x}, y={y}, z={z}, w={w} -> To Frame: {self.frame_id} -> Topic: {self.goal_topic}"
        )

        # Chuyển trạng thái từ "pending" sang "sent" để kết thúc chu kỳ lệnh
        data["status"] = "sent"
        try:
            self.command_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.last_signature = f"{command}|sent|{created_at}"
        except Exception as error:
            self.get_logger().warning(f"Cannot update command status to JSON file: {error}")


def main(args=None):
    rclpy.init(args=args)
    node = HomeListener()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()