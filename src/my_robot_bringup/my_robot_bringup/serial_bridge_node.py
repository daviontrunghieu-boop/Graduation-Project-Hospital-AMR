#!/usr/bin/env python3

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import serial
import struct
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped


def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def quaternion_from_yaw(yaw):
    qz = math.sin(yaw * 0.5)
    qw = math.cos(yaw * 0.5)
    return 0.0, 0.0, qz, qw


class RobotController(Node):
    def __init__(self):
        super().__init__('robot_controller_uart')

        self.serial_port = None
        try:
            self.serial_port = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
            self.get_logger().info("👉 KẾT NỐI THÀNH CÔNG VỚI ARDUINO TẠI CỔNG /dev/ttyACM0")
        except serial.SerialException as e:
            self.get_logger().error(f"❌ KHÔNG THỂ MỞ CỔNG SERIAL /dev/ttyACM0! Lỗi: {str(e)}")
            self.get_logger().error("👉 Vui lòng chạy lệnh: sudo chmod a+rw /dev/ttyACM0")

        # Publisher
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        # Subscriber
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            'cmd_vel',
            self.cmd_vel_callback,
            10
        )

        self.linear_vel = 0.0
        self.angular_vel = 0.0

        # Timer đọc dữ liệu từ Serial (Chu kỳ 10ms ~ 100Hz)
        self.create_timer(0.01, self.read_serial)
        self.get_logger().info("Robot Controller Node Started")

    def cmd_vel_callback(self, msg):
        """Nhận dữ liệu điều khiển từ cmd_vel và gửi xuống Arduino"""
        self.linear_vel = msg.linear.x
        self.angular_vel = msg.angular.z
        if self.serial_port and self.serial_port.is_open:
            self.send_serial_data()

    def send_serial_data(self):
        """Gửi dữ liệu vận tốc xuống Arduino"""
        try:
            cmd_data = struct.pack(
                '<Bff',
                0xAA,
                self.linear_vel,
                self.angular_vel
            )
            checksum = 0
            for b in cmd_data:
                checksum ^= b

            self.serial_port.write(cmd_data + struct.pack('B', checksum))
        except Exception as e:
            self.get_logger().error(f"Lỗi khi gửi Serial: {str(e)}")

    def read_serial(self):
        """Đọc gói dữ liệu odometry từ Arduino"""
        if self.serial_port is None or not self.serial_port.is_open:
            return

        try:
            if self.serial_port.in_waiting < 23:
                return

            while self.serial_port.in_waiting >= 23:
                start_byte = self.serial_port.read(1)

                if start_byte != b'\xAA':
                    continue  

                payload = self.serial_port.read(20)
                if len(payload) != 20:
                    continue

                checksum_byte = self.serial_port.read(1)
                end_byte = self.serial_port.read(1)

                if end_byte != b'\x55':
                    self.get_logger().warn("Sai END_BYTE, bỏ qua gói dữ liệu.")
                    continue

                calculated_checksum = 0
                for b in payload:
                    calculated_checksum ^= b

                if checksum_byte[0] != calculated_checksum:
                    self.get_logger().warn("Checksum không khớp, gói dữ liệu bị nhiễu.")
                    continue

                # Giải mã dữ liệu (Unpack) từ chuỗi byte
                x, y, theta, linear, angular = struct.unpack('<fffff', payload)

                # ĐÃ SỬA: Quy đổi ngược đơn vị m/s và rad/s do Arduino nhân với 1000.0 trước khi gửi
                real_linear_vel = linear / 1000.0
                real_angular_vel = angular / 1000.0

                self.get_logger().info(
                    f"👉 ODOM OK -> x={x:.2f}, y={y:.2f}, theta={theta:.2f} | v={real_linear_vel:.2f} m/s"
                )

                # Phát hành TF và Odometry Topic với giá trị thực tế đã chia lại
                self.publish_odometry_and_tf(x, y, theta, real_linear_vel, real_angular_vel)

        except Exception as e:
            self.get_logger().error(f"Lỗi hệ thống khi đọc dữ liệu Serial: {str(e)}")

    def publish_odometry_and_tf(self, x, y, theta, linear, angular):
        """Publish odometry message và phát hành TF transform"""
        current_time = self.get_clock().now().to_msg()
        theta_corrected = normalize_angle(theta)

        # 1. Tạo và phát hành TF định vị từ odom -> base_footprint_link
        transform = TransformStamped()
        transform.header.stamp = current_time
        transform.header.frame_id = "odom"
        transform.child_frame_id = "base_footprint_link"

        transform.transform.translation.x = x
        transform.transform.translation.y = y
        transform.transform.translation.z = 0.0

        q = quaternion_from_yaw(theta_corrected)
        transform.transform.rotation.x = q[0]
        transform.transform.rotation.y = q[1]
        transform.transform.rotation.z = q[2]
        transform.transform.rotation.w = q[3]

        # 2. Tạo và phát hành Odometry message
        odom_msg = Odometry()
        odom_msg.header.stamp = current_time
        odom_msg.header.frame_id = "odom"
        odom_msg.child_frame_id = "base_footprint_link"

        odom_msg.pose.pose.position.x = x
        odom_msg.pose.pose.position.y = y
        odom_msg.pose.pose.position.z = 0.0
        odom_msg.pose.pose.orientation = transform.transform.rotation

        odom_msg.twist.twist.linear.x = linear
        odom_msg.twist.twist.linear.y = 0.0
        odom_msg.twist.twist.linear.z = 0.0
        odom_msg.twist.twist.angular.x = 0.0
        odom_msg.twist.twist.angular.y = 0.0
        odom_msg.twist.twist.angular.z = angular

        self.tf_broadcaster.sendTransform(transform)
        self.odom_pub.publish(odom_msg)


def main(args=None):
    rclpy.init(args=args)
    node = RobotController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.serial_port and node.serial_port.is_open:
            node.serial_port.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()