cmake_minimum_required(VERSION 3.8)
project(my_robot_web_config)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)

install(
  DIRECTORY robot_web_interface config assets/images
  DESTINATION share/${PROJECT_NAME}/
)
install(PROGRAMS
  robot_web_interface/admin.py  # Thay đổi đường dẫn này cho đúng với thực tế
  robot_web_interface/app.py 
  robot_web_interface/appointments.py
  robot_web_interface/face_states.py
  robot_web_interface/demo_driver.py
  robot_web_interface/app1.py
  robot_web_interface/face_renderer.py
  robot_web_interface/input_controller.py
  robot_web_interface/layout.py
  robot_web_interface/map_runtime.py
  robot_web_interface/panel_tabs.py
  robot_web_interface/payloads.py
  robot_web_interface/runtime_contract.py
  robot_web_interface/state_model.py
  robot_web_interface/visual_tokens.py
  DESTINATION lib/${PROJECT_NAME}
)
ament_package()
