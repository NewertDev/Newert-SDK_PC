import asyncio
import random
from PySide6.QtCore import QTimer
from bleak import BleakScanner, BleakClient
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QListWidget, QVBoxLayout, QHBoxLayout, \
    QWidget, QMessageBox
from qasync import QEventLoop, asyncSlot
import datetime
import struct


# BLE 연결 및 데이터 수신을 관리하는 메인 클래스
class BleController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE 연결")
        self.resize(1250, 500)

        # Material 스타일 적용
        with open("design.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        # 데이터를 저장하기 위한 큐 초기화
        self.data_queue = []

        # 장비 주소값 저장용 변수
        self.address = ''
        self.device_id = ''

        # 테스트용 타이머
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.generate_test_data)

        # BLE 서비스와 특성(characteristic) UUID 정의
        self.uart_service_uuid = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
        self.read_uart_characteristic_uuid = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
        self.write_uart_characteristic_uuid = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
        self.ppg_service_uuid = "00001000-0000-1000-8000-00805f9b34fb"
        self.read_ppg_characteristic_uuid = "00001100-0000-1000-8000-00805f9b34fb"
        self.batt_service_uuid = "0000180f-0000-1000-8000-00805f9b34fb"
        self.read_batt_characteristic_uuid = "00002a19-0000-1000-8000-00805f9b34fb"

        # BLE 연결과 데이터를 위한 변수 초기화
        self.client = None

        self.device_list = QListWidget()
        self.scan_button = QPushButton("BLE 장치 검색")
        self.scan_button.setFixedHeight(50)
        self.connect_button = QPushButton("연결")
        self.connect_button.setFixedHeight(50)
        self.disconnect_button = QPushButton("연결 해제")  # 연결 해제 버튼 추가
        self.disconnect_button.setFixedHeight(50)

        self.device_label = QLabel(f'연결된 장비: {self.address}')
        self.button_row = QHBoxLayout()
        self.start_button = QPushButton("측정 시작")
        self.start_button.setFixedHeight(50)
        self.stop_button = QPushButton("측정 종료")
        self.stop_button.setFixedHeight(50)
        self.button_row.addWidget(self.start_button)
        self.button_row.addWidget(self.stop_button)
        self.result_list = QListWidget()

        # UI 레이아웃 설정
        main_frame = QHBoxLayout()

        ble_layout = QVBoxLayout()
        ble_layout.addWidget(QLabel('블루투스 목록'))
        ble_layout.addWidget(self.scan_button)
        ble_layout.addWidget(self.device_list)
        ble_layout.addWidget(self.connect_button)
        ble_layout.addWidget(self.disconnect_button)  # 연결 해제 버튼 추가

        measure_layout = QVBoxLayout()
        measure_layout.addWidget(self.device_label)
        measure_layout.addWidget(self.result_list)
        measure_layout.addLayout(self.button_row)

        main_frame.addLayout(ble_layout, 2)
        main_frame.addSpacing(20)
        main_frame.addLayout(measure_layout, 3)

        container = QWidget()
        container.setLayout(main_frame)
        self.setCentralWidget(container)

        # 버튼 클릭 시 실행할 함수 연결
        self.scan_button.clicked.connect(self.start_scan)
        self.connect_button.clicked.connect(self.connect_to_device)
        self.disconnect_button.clicked.connect(self.disconnect_from_device)  # 연결 해제 함수 연결
        self.start_button.clicked.connect(self.start_measure)
        self.stop_button.clicked.connect(self.stop_measure)

        self.disable_button_state(True)

    # BLE 장치 검색 시작 함수
    @asyncSlot()
    async def start_scan(self):
        self.device_list.clear()
        try:
            await self.scan_devices()
        except Exception as e:
            print(f"Error starting scan: {e}")
            QMessageBox.critical(self, "스캔 오류", "장치 스캔 중 오류가 발생했습니다.")

    # 실제 BLE 장치를 검색하는 비동기 함수
    async def scan_devices(self):
        devices = await BleakScanner.discover()
        for device in devices:
            # 이름이 "VitalTrack" 또는 "EmoConnect"로 시작하는 장치만 목록에 추가
            if device.name and (device.name.startswith("VitalTrack") or device.name.startswith("EmoConnect")):
                self.device_list.addItem(f"{device.name} - {device.address}")

    # 선택한 BLE 장치에 연결하는 함수
    @asyncSlot()
    async def connect_to_device(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            self.device_id = selected_item.text().split(" - ")[0]
            self.address = selected_item.text().split(" - ")[1]
            try:
                await self.connect_and_receive_data(self.address)
            except Exception as e:
                print(f"Error connecting to device: {e}")
                QMessageBox.critical(self, "연결 오류", "장치 연결 중 오류가 발생했습니다.")
        else:
            QMessageBox.warning(self, "선택 필요", "연결할 장치를 선택해주세요.")

    # BLE 장치에 연결하고 데이터를 수신하는 비동기 함수
    async def connect_and_receive_data(self, address):
        try:
            self.client = BleakClient(address)
            await self.client.connect()
            QMessageBox.information(self, "연결 성공", f"{address}에 성공적으로 연결되었습니다.")

            # 측정 시작 및 종료버튼 활성화
            self.disable_button_state(False)
            self.device_label.setText(f'연결된 장비: {self.device_id} {self.address}')

            # 데이터 수신을 위한 알림 활성화
            await self.client.start_notify(self.read_ppg_characteristic_uuid, self.notification_handler)
        except Exception as e:
            print(f"Error connecting to {address}: {e}")

    # 연결 해제 함수
    @asyncSlot()
    async def disconnect_from_device(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            self.device_label.setText('연결된 장비: 없음')
            self.disable_button_state(True)

            # 텍스트 박스의 모든 텍스트 지우기
            self.result_list.clear()

            QMessageBox.information(self, "연결 해제", "장치와의 연결이 해제되었습니다.")
            print("Disconnected from device.")
        else:
            QMessageBox.warning(self, "연결 해제 오류", "현재 연결된 장치가 없습니다.")

    # 데이터 수신 시 호출되는 핸들러 함수
    def notification_handler(self, sender, data):
        # print(f"Data received from {sender}: {data}")
        self.process_received_data(data)

    # 수신된 데이터를 변환하여 큐에 추가하는 함수
    def process_received_data(self, data):
        # BATT 메시지 확인
        if data[0] == 66 and data[1] == 65 and data[2] == 84 and data[3] == 84:  # "BATT" 검사
            batt = (data[5] << 8) | data[4]  # 배터리 값 계산
            new_batt = data[6]
            if new_batt > 100:
                new_batt = 100
            elif new_batt < 0:
                new_batt = 0
            self.data_queue.append({'battery': new_batt})

            count = (data[9] << 8) | data[8]  # 샘플 카운트
            self.data_queue.append({'count': count})

            # 데이터 출력 또는 업데이트
            print(f"Battery Level: {new_batt}%, Sample Count: {count}")
            self.update_data_display(new_batt)
        else:
            # PPG 및 IMU 데이터 처리
            chunk_size = 20  # 데이터 청크 크기
            for i in range(len(data) // chunk_size):
                # PPG 데이터
                ppg = ((data[20 * i + 1] << 8) | data[20 * i + 0])
                self.data_queue.append({'ppg': ppg})

                # IMU 데이터 변환
                acc_x = self.float16_to_float32((data[20 * i + 3] << 8) | data[20 * i + 2])
                acc_y = self.float16_to_float32((data[20 * i + 5] << 8) | data[20 * i + 4])
                acc_z = self.float16_to_float32((data[20 * i + 7] << 8) | data[20 * i + 6])

                gyro_x = self.float16_to_float32((data[20 * i + 9] << 8) | data[20 * i + 8])
                gyro_y = self.float16_to_float32((data[20 * i + 11] << 8) | data[20 * i + 10])
                gyro_z = self.float16_to_float32((data[20 * i + 13] << 8) | data[20 * i + 12])

                mag_x = self.float16_to_float32((data[20 * i + 15] << 8) | data[20 * i + 14])
                mag_y = self.float16_to_float32((data[20 * i + 17] << 8) | data[20 * i + 16])
                mag_z = self.float16_to_float32((data[20 * i + 19] << 8) | data[20 * i + 18])

                # 큐에 데이터 추가
                self.data_queue.append({
                    'acc': [acc_x, acc_y, acc_z],
                    'gyro': [gyro_x, gyro_y, gyro_z],
                    'mag': [mag_x, mag_y, mag_z]
                })

                result = f"PPG: {ppg}, ACC: {[acc_x, acc_y, acc_z]}, GYRO: {[gyro_x, gyro_y, gyro_z]}, MAG: {[mag_x, mag_y, mag_z]}"
                # 출력 또는 업데이트
                print(result)
                self.update_data_display(result)

    # float16 값을 float32로 변환하는 함수 예시
    def float16_to_float32(self, value):
        # 변환 함수 (사용자 정의 float16 to float32 변환 필요)
        return float(value)  # 실제 변환 알고리즘으로 대체 필요

    # 버튼 상태 스위치
    def disable_button_state(self, trigger):
        self.start_button.setDisabled(trigger)
        self.stop_button.setDisabled(trigger)

    # 결과값 디스플레이 업데이트
    def update_data_display(self, ppg_value):
        self.result_list.addItem(f"{ppg_value}")
        if self.result_list.count() > 40:
            self.result_list.takeItem(0)

    # 임의의 데이터 생성하는 함수
    def generate_test_data(self):
        random_float = random.uniform(0.0, 100.0)
        packed_data = struct.pack('f', random_float)
        self.process_received_data(packed_data)

    # 측정 시작
    @asyncSlot()
    async def start_measure(self):
        if self.client and self.client.is_connected:
            try:
                # BLE 장치에 메시지 전송
                message = "\nset POWER_1V8 1\n"
                await self.client.write_gatt_char(self.write_uart_characteristic_uuid, message.encode())
                await asyncio.sleep(0.1)
                message = "\nset ppg_enable 1\n"
                await self.client.write_gatt_char(self.write_uart_characteristic_uuid, message.encode())
                await asyncio.sleep(0.1)
                message = "\nsetup ppg\n"
                await self.client.write_gatt_char(self.write_uart_characteristic_uuid, message.encode())
                await asyncio.sleep(0.1)

                print("Message sent to device.")
                # self.timer.start(500)  # 데이터 생성 시작
            except Exception as e:
                print(f"Failed to send message: {e}")
        else:
            print("Connect device first.")

    # 측정 종료
    @asyncSlot()
    async def stop_measure(self):
        if self.client and self.client.is_connected:
            print('measure stopped')
            message = "\nset ppg_enable 0\n"
            await self.client.write_gatt_char(self.write_uart_characteristic_uuid, message.encode())
            await asyncio.sleep(0.1)
            message = "\nsetup ppg\n"
            await self.client.write_gatt_char(self.write_uart_characteristic_uuid, message.encode())
            await asyncio.sleep(0.1)
            self.timer.stop()
        else:
            print('Connect device first.')

    # 창이 닫힐 때 실행되는 함수
    def closeEvent(self, event):
        if self.client and self.client.is_connected:
            asyncio.run(self.client.disconnect())
        event.accept()


# 애플리케이션 실행 코드
if __name__ == "__main__":
    app = QApplication([])  # Qt 애플리케이션 생성
    loop = QEventLoop(app)  # 이벤트 루프 생성
    asyncio.set_event_loop(loop)  # asyncio의 기본 이벤트 루프로 설정

    controller = BleController()
    controller.show()

    with loop:
        loop.run_forever()
