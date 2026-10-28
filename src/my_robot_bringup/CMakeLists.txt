cmake_minimum_required(VERSION 3.8)
project(my_robot_bringup)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)

# 1. Cài đặt các thư mục tài nguyên (launch, config,...)
install(
  DIRECTORY launch config worlds maps my_robot_bringup hospital_robot_camera
  DESTINATION share/${PROJECT_NAME}/
)

install(PROGRAMS
  my_robot_bringup/test_connection.py
  my_robot_bringup/serial_bridge_node.py
  my_robot_bringup/camera.py
  my_robot_bringup/face_prompt_listener.py
  my_robot_bringup/Voice_Camera.py
  my_robot_bringup/home_listener.py

  DESTINATION lib/${PROJECT_NAME}
)
ament_package()
