import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.conditions import IfCondition  


def generate_launch_description():

    # Package share directory của bạn
    robot_share = get_package_share_directory("my_robot_bringup")
    nav2_bringup_share = get_package_share_directory("nav2_bringup")

    # ---------------- Launch Arguments ----------------
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Use simulation time"
    )

    map_arg = DeclareLaunchArgument(
        "map",
        default_value=os.path.join(robot_share, "maps", "my_map1.yaml"),
        description="Full path to map file"
    )

    params_arg = DeclareLaunchArgument(
        "params",
        default_value=os.path.join(robot_share, "config", "nav2_params2.yaml"),
        description="Full path to params file"
    )

    use_rviz_arg = DeclareLaunchArgument(
        "use_rviz",
        default_value="true",
        description="Whether to start RViz"
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    map_file = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params")
    use_rviz = LaunchConfiguration("use_rviz")

    rviz_config_file = os.path.join(nav2_bringup_share, "rviz", "nav2_default_view.rviz")

    # ---------------- Nav2 Launch ----------------
    nav2_launch_file_dir = os.path.join(nav2_bringup_share, "launch")

    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_launch_file_dir, "bringup_launch.py")
        ),
        launch_arguments={
            "map": map_file,
            "use_sim_time": use_sim_time,
            "params_file": params_file
        }.items()
    )

    # ---------------- LIDAR ----------------
    lidar_node = Node(
        package='rplidar_ros',
        executable='rplidar_composition',
        name='rplidar',
        output='screen',
        parameters=[{
            'serial_port': '/dev/ttyUSB0',
            'serial_baudrate': 115200,
            'scan_mode': 'Sensitivity',
            'max_distance': 12.0,
            'angle_compensate': True
        }]
    )
  
    # ---------------- UART ----------------
    uart_node = Node(
        package="my_robot_bringup",            
        executable="serial_bridge_node.py",    
        name="robot_controller_uart",
        output="screen",
    )

    # ---------------- RViz2 Node ----------------
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config_file],
        condition=IfCondition(use_rviz), 
        output='screen'
    )

    # 🛠️ ĐÃ SỬA: Bật lại và đổi frame từ base_link sang base_footprint_link
    static_tf_lidar = Node(                         
        package="tf2_ros",
        executable="static_transform_publisher",
        name="static_tf_base_to_lidar",
        output="screen",
        arguments=[
            "--x", "0.28025698887101",
            "--y", "-0.000461491826200144",
            "--z", "0.213",
            "--roll", "0.0",
            "--pitch", "0.0",
            "--yaw", "0.0",
            "--frame-id", "base_footprint_link", 
            "--child-frame-id", "laser_frame"
        ]
    )

    # ---------------- CAMERA ----------------
    camera_node = Node(
        package="my_robot_bringup",
        executable="camera.py",
        name="camera_node",
        output="screen"
    )

    # ---------------- VOICE (Test Connection) ----------------
    voice_node = Node(
        package="my_robot_bringup",
        executable="test_connection.py",
        name="voice_test_connection",
        output="screen"
    )

    # ---------------- HOME BUTTON LISTENER ----------------
    # Lưu ý: Thay đổi tên 'package' và 'executable' nếu bạn lưu file python ở nơi khác
    home_listener_node = Node(
        package="my_robot_bringup", # Thay bằng tên package của bạn
        executable="home_listener.py", # Tên file hoặc tên đăng ký trong setup.py
        name="home_listener",
        output="screen"
        # parameters=[{'command_file': 'đường/dẫn/khác.json'}] # Có thể đè tham số ở đây nếu cần
    )

    return LaunchDescription([
        use_sim_time_arg,
        map_arg,
        params_arg,
        use_rviz_arg,
        nav2_bringup,
        lidar_node,
        static_tf_lidar, 
        uart_node,
        rviz_node, 
        camera_node,
        voice_node,
        home_listener_node  # 🟢 Đã thêm Home node vào quy trình Launch
    ])