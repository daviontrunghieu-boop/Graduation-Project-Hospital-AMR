from launch import LaunchDescription
from launch.actions import (
    IncludeLaunchDescription,
    DeclareLaunchArgument,
    ExecuteProcess,
    RegisterEventHandler,
    TimerAction
)
from launch.event_handlers import OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PathJoinSubstitution,
    FindExecutable
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # -----------------------------
    # Package paths
    # -----------------------------
    pkg_robot = FindPackageShare("my_robot_description")
    pkg_bringup = FindPackageShare("my_robot_bringup")
    pkg_gazebo = FindPackageShare("gazebo_ros")
    pkg_nav2 = FindPackageShare("nav2_bringup")

    # -----------------------------
    # File paths
    # -----------------------------
    urdf_path = PathJoinSubstitution([pkg_robot, "urdf", "test3.urdf.xacro"])
    rviz_config_path = PathJoinSubstitution([pkg_robot, "rviz", "default.rviz"])
    world_path = PathJoinSubstitution([pkg_bringup, "worlds", "map.world"])
    map_file = PathJoinSubstitution([pkg_bringup, "maps", "test_map.yaml"])
    nav2_params_file = PathJoinSubstitution([pkg_bringup, "config", "nav2_params.yaml"])

    # -----------------------------
    # Launch arguments
    # -----------------------------
    use_sim_time = LaunchConfiguration("use_sim_time")

    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use simulation (Gazebo) clock time"
    )

    # -----------------------------
    # Gazebo cleanup on shutdown
    # -----------------------------
    gz_cleanup = RegisterEventHandler(
        OnShutdown(
            on_shutdown=[
                ExecuteProcess(
                    cmd=["bash", "-c", "pkill -9 gzserver; pkill -9 gzclient"],
                    shell=False
                )
            ]
        )
    )

    # -----------------------------
    # Robot State Publisher
    # -----------------------------
    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[{
            "use_sim_time": use_sim_time,
            "robot_description": Command([
                FindExecutable(name="xacro"),
                " ",
                urdf_path
            ])
        }],
        output="screen"
    )

    # -----------------------------
    # Joint State Publisher
    # -----------------------------
    joint_state_publisher_node = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        parameters=[{"use_sim_time": use_sim_time}],
        output="screen"
    )

    # -----------------------------
    # RViz2
    # -----------------------------
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", rviz_config_path],
        parameters=[{"use_sim_time": use_sim_time}],
        output="screen"
    )

    # -----------------------------
    # Gazebo
    # -----------------------------
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_gazebo, "launch", "gazebo.launch.py"])
        ),
        launch_arguments={
            "world": world_path
        }.items(),
    )

    # -----------------------------
    # Spawn robot
    # -----------------------------
    spawn_entity = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        arguments=[
            "-topic", "/robot_description",
            "-entity", "aurora",
            "-x", "0",
            "-y", "0",
            "-z", "0.2",
            "-Y", "0"
        ],
        output="screen"
    )

    spawn_entity_delayed = TimerAction(
        period=3.0,
        actions=[spawn_entity]
    )

    # -----------------------------
    # Nav2 bringup
    # -----------------------------
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_nav2, "launch", "bringup_launch.py"])
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "map": map_file,
            "params_file": nav2_params_file
        }.items(),
    )

    nav2_launch_delayed = TimerAction(
        period=6.0,
        actions=[nav2_launch]
    )

    # -----------------------------
    # Launch description
    # -----------------------------
    return LaunchDescription([
        declare_use_sim_time,
        gazebo_launch,
        robot_state_publisher_node,
        joint_state_publisher_node,
        spawn_entity_delayed,
        rviz_node,
        nav2_launch_delayed,
        gz_cleanup
    ])