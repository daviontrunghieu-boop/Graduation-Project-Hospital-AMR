from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    map_file = LaunchConfiguration("maps")
    params_file = LaunchConfiguration("params_file")

    enable_home_listener = LaunchConfiguration("enable_home_listener")
    command_file = LaunchConfiguration("command_file")
    goal_topic = LaunchConfiguration("goal_topic")
    frame_id = LaunchConfiguration("frame_id")

    enable_rosbridge = LaunchConfiguration("enable_rosbridge")
    rosbridge_port = LaunchConfiguration("rosbridge_port")
    rosbridge_address = LaunchConfiguration("rosbridge_address")
    
    # Thêm biến cấu hình cho Voice Nav Node
    enable_voice_nav = LaunchConfiguration("enable_voice_nav")

    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use simulation clock",
    )

    declare_map_file = DeclareLaunchArgument(
        "maps",
        default_value="/home/hieu/ros2_ws/src/my_robot_bringup/maps/my_map.yaml",
        description="Full path to map params file",
    )

    declare_params_file = DeclareLaunchArgument(
        "params_file",
        default_value="/home/hieu/ros2_ws/src/my_robot_bringup/config/nav2_params_goc.yaml",
        description="Full path to Nav2 params file",
    )

    declare_enable_home_listener = DeclareLaunchArgument(
        "enable_home_listener",
        default_value="true",
        description="Start HOME listener node with Nav2",
    )

    declare_enable_rosbridge = DeclareLaunchArgument(
        "enable_rosbridge",
        default_value="true",
        description="Start rosbridge WebSocket server for the web admin",
    )

    declare_rosbridge_port = DeclareLaunchArgument(
        "rosbridge_port",
        default_value="9090",
        description="Rosbridge WebSocket port",
    )

    declare_rosbridge_address = DeclareLaunchArgument(
        "rosbridge_address",
        default_value="0.0.0.0",
        description="Rosbridge bind address",
    )

    # Khai báo argument cho Voice Nav Node
    declare_enable_voice_nav = DeclareLaunchArgument(
        "enable_voice_nav",
        default_value="true",
        description="Start Voice Navigation node (test_connection.py)",
    )

    declare_command_file = DeclareLaunchArgument(
        "command_file",
        default_value="/home/hieu/ros2_ws/src/my_robot_web_config/robot_command.json",
        description="Path to robot_command.json written by web admin",
    )

    declare_goal_topic = DeclareLaunchArgument(
        "goal_topic",
        default_value="/goal_pose",
        description="Nav2 goal topic",
    )

    declare_frame_id = DeclareLaunchArgument(
        "frame_id",
        default_value="map",
        description="Goal frame id",
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                PathJoinSubstitution(
                    [
                        FindPackageShare("turtlebot3_navigation2"),
                        "launch",
                        "navigation2.launch.py",
                    ]
                )
            ]
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "map": map_file,
            "param_file": params_file,
            "params_file": params_file,
        }.items(),
    )

    rosbridge_node = Node(
        condition=IfCondition(enable_rosbridge),
        package="rosbridge_server",
        executable="rosbridge_websocket",
        name="rosbridge_websocket",
        output="screen",
        parameters=[
            {
                "port": ParameterValue(rosbridge_port, value_type=int),
                "address": rosbridge_address,
            }
        ],
    )

    home_listener_node = Node(
        condition=IfCondition(enable_home_listener),
        package="my_robot_bringup",
        executable="home_listener.py",
        name="home_listener",
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
                "command_file": command_file,
                "goal_topic": goal_topic,
                "frame_id": frame_id,
            }
        ],
    )

    # Thêm Node Voice Navigation (gọi file test_connection.py)
    voice_nav_node = Node(
        condition=IfCondition(enable_voice_nav),
        package="my_robot_bringup",
        executable="test_connection.py",
        name="voice_nav_node",
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
            }
        ],
    )

    return LaunchDescription(
        [
            declare_use_sim_time,
            declare_map_file,
            declare_params_file,
            declare_enable_home_listener,
            declare_enable_rosbridge,
            declare_rosbridge_port,
            declare_rosbridge_address,
            declare_enable_voice_nav,  # Khai báo argument mới
            declare_command_file,
            declare_goal_topic,
            declare_frame_id,
            nav2_launch,
            rosbridge_node,
            home_listener_node,
            voice_nav_node,            # Thêm node mới vào đây
        ]
    )