import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false"
    )

    slam_config_arg = DeclareLaunchArgument(
        "slam_config",
        default_value=os.path.join(
            get_package_share_directory("my_robot_bringup"),
            "config",
            "slam_config.yaml"
        )
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    slam_config = LaunchConfiguration("slam_config")

    # Lifecycle node
    lifecycle_node = ["map_saver_server"]

    # Giao tiếp UART với Arduino
    uart_node = Node(
        package="my_robot_bringup",
        executable="serial_bridge_node.py",
        name="robot_controller_uart",
        output="screen",
    )

    # RPLidar
    lidar_node = Node(
        package="rplidar_ros",
        executable="rplidar_composition",
        name="rplidar",
        parameters=[{
            "serial_port": "/dev/ttyUSB0",
            "serial_baudrate": 115200,
            "scan_mode": "Sensitivity",
            "max_distance": 12.0,
            "angle_compensate": True
        }]
    )

    # SLAM Toolbox
    slam_toolbox = Node(
        package="slam_toolbox",
        executable="sync_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        parameters=[
            slam_config,
            {"use_sim_time": use_sim_time}
        ],
        remappings=[
            ("/scan", "/scan"),
            ("/odom", "/odom")
        ]
    )

    # Map Saver Server
    nav2_save_map = Node(
        package="nav2_map_server",
        executable="map_saver_server",
        name="map_saver_server",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time},
            {"save_map_timeout": 5},
            {"free_thresh_default": 0.196},
            {"occupied_thresh_default": 0.65}
        ],
    )

    # Lifecycle Manager
    nav2_lifecycle_node = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager_slam",
        output="screen",
        parameters=[
            {"node_names": lifecycle_node},
            {"use_sim_time": use_sim_time},
            {"autostart": True}
        ]
    )

    # RViz2
    rviz2_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        parameters=[{"use_sim_time": use_sim_time}],
        output="screen"
    )

    # Static TF: base_link -> laser_frame
    # Thứ tự: x y z yaw pitch roll parent child
    # Xoay quanh trục Y 180 độ: pitch = 3.14159265
    static_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        arguments=[
            "0.18", "0", "0.23",
            "0", "0", "0",
            "base_footprint_link", "laser_frame"
        ]
    )

    return LaunchDescription([
        use_sim_time_arg,
        slam_config_arg,

        uart_node,
        lidar_node,
        static_tf,
        slam_toolbox,

        # nav2_save_map,
        nav2_lifecycle_node,
        # rviz2_node,
    ])