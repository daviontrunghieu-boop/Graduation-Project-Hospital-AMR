# Xin chào mọi người. Đây là đồ án em làm cho môn Vi Xử lý
# Hệ Thống So Sánh Điện Áp Tương Tự Kép Sử Dụng PIC16F628A
 + Các kĩ năng nhúng được áp dụng trong đồ án này là : 
1. Thao tác trên thanh ghi trực tiếp : Cấu hình thủ công các thanh ghi chức năng đặc biệt (SFR)
như là CMCON, VRCON và TRIS.
2. Cầu hình an toàn và tiết kiệm năng lượng: Thiết lập các bit cấu hình phần cứng (pragma, config)
cho thạch anh ngoài (HS), Watchdog Timer, ...
3. Trừ tượng hóa phần cứng : Cấu trúc mã nguồn sạch sẽ, dễ bào trì bằng cách sử dụng macro và
phân chia hàm chức năng

 + Bảng cấu hình chân vi điều khiển
Chân MCU              Chức năng               Output/Input
RA0 (PIN17)            C1IN-                      INPUT
RA1 (PIN18)            C1IN+                      INPUT
RA2 (PIN1)             C2IN-                      INPUT
RA3 (PIN2)             C2IN+                      INPUT
RB4 (PIN10)            LED1                       OUTPUT
RB5 (PIN11)            LED2                       OUTPUT

 + Cách biên dịch và nạp code
* Yêu Cầu Phần Mềm & Phần Cứng
1. IDE: MPLAB X IDE (v5.00 trở lên)
2. Trình biên dịch: Microchip XC8 Compiler (v2.00 trở lên)
3. Mạch nạp: PICkit 3 / PICkit 4 / ICD 3
4. Phần mềm mô phỏng (Tùy chọn): Proteus VSM / MPLAB X Simulator

* Các Bước Thực Hiện
1. Clone repository về máy
2. Mở MPLAB X IDE và open project từ thư mục vừa clone
3. Chọn thiết bị mục tiêu là PIC16F628A và chọn trình biên dịch XC8
4. Tiến hành biên dịch dự án (Clean and Build)
5. Nạp file .hex được tạo ra vào chip PIC16F628A thông qua mạch nạp


