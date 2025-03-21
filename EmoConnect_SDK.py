import asyncio
import time
import requests
import re
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QListWidget, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox
from qasync import QEventLoop, asyncSlot
from bleak import BleakScanner, BleakClient
from scipy.interpolate import interp1d
import numpy as np
import emoconnect_pro as ep
import license_pro as lp
import emoconnect_utils as eu
import csv

class BleController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE 연결")
        self.setWindowIcon(QIcon("images/app_icon.ico"))
        self.resize(1250, 500)

        # Material 스타일 적용
        with open("design.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        self.data_queue = []
        self.address = ''
        self.device_id = ''
        self.client = None

        # 데이터 및 타이밍을 위한 버퍼
        self.ppg_buffer = []
        self.acc_buffer = []
        self.gyro_buffer = []
        self.mag_buffer = []
        self.last_timestamp = time.time()

        # 타이머 설정
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.generate_test_data)

        # UI 구성
        self.device_list = QListWidget()
        self.scan_button = QPushButton("BLE 장치 검색")
        self.connect_button = QPushButton("연결")
        self.disconnect_button = QPushButton("연결 해제")
        self.device_label = QLabel(f'연결된 장비: {self.address}')
        self.start_button = QPushButton("측정 시작")
        self.stop_button = QPushButton("측정 종료")
        self.result_list = QListWidget()

        self.setup_ui()
        self.scan_button.clicked.connect(self.start_scan)
        self.connect_button.clicked.connect(self.connect_to_device)
        self.disconnect_button.clicked.connect(self.disconnect_from_device)
        self.start_button.clicked.connect(self.start_measure)
        self.stop_button.clicked.connect(self.stop_measure)
        self.disable_button_state(True)

        # 라이선스는 선택사항입니다.
        self.user_license = input("Enter your license if available (press Enter to skip): ").strip()
        self.license_manager = lp.LicenseManager()  # subscribe_device() 메서드 포함
        self.hr_analyzer = None

    def setup_ui(self):
        main_frame = QHBoxLayout()
        ble_layout = QVBoxLayout()
        ble_layout.addWidget(QLabel('블루투스 목록'))
        ble_layout.addWidget(self.scan_button)
        ble_layout.addWidget(self.device_list)
        ble_layout.addWidget(self.connect_button)
        ble_layout.addWidget(self.disconnect_button)

        measure_layout = QVBoxLayout()
        measure_layout.addWidget(self.device_label)
        measure_layout.addWidget(self.result_list)
        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        measure_layout.addLayout(button_row)

        main_frame.addLayout(ble_layout, 2)
        main_frame.addSpacing(20)
        main_frame.addLayout(measure_layout, 3)

        container = QWidget()
        container.setLayout(main_frame)
        self.setCentralWidget(container)

    @asyncSlot()
    async def start_scan(self):
        self.device_list.clear()
        try:
            await self.scan_devices()
        except Exception as e:
            print(f"Error starting scan: {e}")
            QMessageBox.critical(self, "스캔 오류", "장치 스캔 중 오류가 발생했습니다.")

    async def scan_devices(self):
        devices = await BleakScanner.discover()
        for device in devices:
            if device.name and (device.name.startswith("VitalTrack") or device.name.startswith("EmoConnect")):
                # 예: "EmoConnect v1.0(A107) - AA:BB:CC:DD:EE:FF"
                self.device_list.addItem(f"{device.name} - {device.address}")

    @asyncSlot()
    async def connect_to_device(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            # 선택된 항목에서 device 문자열과 address 분리
            full_device_str, self.address = selected_item.text().split(" - ")
            # 정규식을 사용하여 괄호 안의 내용을 추출 (예: "A107")
            match = re.search(r'\((.*?)\)', full_device_str)
            if match:
                self.device_id = match.group(1)
            else:
                self.device_id = full_device_str

            try:
                await self.connect_and_receive_data(self.address)
                # BLE 연결 후, device_id와 (옵션) 라이선스를 서버로 전송하여 라이선스 검증 수행
                valid = self.license_manager.subscribe_device(self.user_license, self.device_id)
                print("valid", valid)
                if valid:
                    self.hr_analyzer = ep.HeartRateAnalyzer(cal_hr_time=5)
                    print("Pro 기능 활성화됨.")
                else:
                    self.hr_analyzer = None
                    print("Pro 기능 미활성화, 기본 기능만 사용됩니다.")
            except Exception as e:
                print(f"Error connecting to device: {e}")
                QMessageBox.critical(self, "연결 오류", "장치 연결 중 오류가 발생했습니다.")
        else:
            QMessageBox.warning(self, "선택 필요", "연결할 장치를 선택해주세요.")

    async def connect_and_receive_data(self, address):
        try:
            self.client = BleakClient(address)
            await self.client.connect()
            QMessageBox.information(self, "연결 성공", f"{address}에 성공적으로 연결되었습니다.")
            self.disable_button_state(False)
            self.device_label.setText(f'연결된 장비: {self.device_id} {self.address}')
            await self.client.start_notify(eu.UUIDs().get_READ_PPG_CHAR(), self.notification_handler)
        except Exception as e:
            print(f"Error connecting to {address}: {e}")

    @asyncSlot()
    async def disconnect_from_device(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            self.device_label.setText('연결된 장비: 없음')
            self.disable_button_state(True)
            self.result_list.clear()
            QMessageBox.information(self, "연결 해제", "장치와의 연결이 해제되었습니다.")
            print("Disconnected from device.")
        else:
            QMessageBox.warning(self, "연결 해제 오류", "현재 연결된 장치가 없습니다.")

    def notification_handler(self, sender, data):
        parser = eu.DataParser()
        try:
            parsed_data = parser.parse_data(bytes(data))
        except Exception as e:
            print(f"Error parsing data: {e}")
            return

        for item in parsed_data:
            if not all(key in item for key in ['ppg', 'acc', 'gyro', 'mag']):
                continue

            self.ppg_buffer.append(item['ppg'])
            self.acc_buffer.append(item['acc'])
            self.gyro_buffer.append(item['gyro'])
            self.mag_buffer.append(item['mag'])

        current_timestamp = time.time()
        if current_timestamp - self.last_timestamp >= 1.0:
            self.process_and_print_data()
            self.last_timestamp = current_timestamp

    def process_and_print_data(self):
        def interpolate_data(buffer, num_points=50):
            buffer = np.array(buffer)
            if len(buffer) < 2:
                shape = (num_points,) + buffer.shape[1:] if buffer.ndim > 1 else (num_points,)
                result = np.tile(buffer[0], shape) if len(buffer) > 0 else np.zeros(shape)
                return np.round(result, decimals=3)
            x = np.linspace(0, len(buffer) - 1, num=len(buffer))
            f = interp1d(x, buffer, kind='linear', axis=0, fill_value="extrapolate")
            x_new = np.linspace(0, len(buffer) - 1, num=num_points)
            result = f(x_new)
            return np.round(result, decimals=3)

        if len(self.ppg_buffer) >= 10:
            try:
                ppg_interp = interpolate_data(self.ppg_buffer, 50).tolist()
            except Exception as e:
                print(f"PPG interpolation error: {e}")
                ppg_interp = [0] * 50

            try:
                acc_interp = interpolate_data(self.acc_buffer, 50).tolist()
            except Exception as e:
                print(f"ACC interpolation error: {e}")
                acc_interp = [[0, 0, 0]] * 50

            try:
                gyro_interp = interpolate_data(self.gyro_buffer, 50).tolist()
            except Exception as e:
                print(f"Gyro interpolation error: {e}")
                gyro_interp = [[0, 0, 0]] * 50

            try:
                mag_interp = interpolate_data(self.mag_buffer, 50).tolist()
            except Exception as e:
                print(f"Mag interpolation error: {e}")
                mag_interp = [[0, 0, 0]] * 50
        else:
            ppg_interp = [0] * 50
            acc_interp = [[0, 0, 0]] * 50
            gyro_interp = [[0, 0, 0]] * 50
            mag_interp = [[0, 0, 0]] * 50

        result = {
            "ppg": ppg_interp,
            "acc": acc_interp,
            "gyro": gyro_interp,
            "mag": mag_interp
        }

        if self.hr_analyzer:
            # 심박수 값과 필터 리스트 업데이트
            hr_value, filter_list = self.hr_analyzer.update_hr(ppg_interp, acc_interp)
            print(f"Heart Rate: {hr_value:.2f}")
            print(f"Filter List: {filter_list}")
            self.update_data_display("데이터 수집 완료. 터미널을 확인해주세요. 현재 Pro기능이 활성화 되었습니다. ")


        else:
            self.update_data_display("데이터 수집 완료. 터미널을 확인해주세요.")

        self.ppg_buffer.clear()
        self.acc_buffer.clear()
        self.gyro_buffer.clear()
        self.mag_buffer.clear()

        print(result)

    def disable_button_state(self, trigger):
        self.start_button.setDisabled(trigger)
        self.stop_button.setDisabled(trigger)

    def update_data_display(self, value):
        self.result_list.addItem(value)
        if self.result_list.count() > 40:
            self.result_list.takeItem(0)

    def generate_test_data(self):
        import struct
        import random
        random_float = random.uniform(0.0, 100.0)
        packed_data = struct.pack('f', random_float)
        self.notification_handler(None, packed_data)

    @asyncSlot()
    async def start_measure(self):
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(eu.UUIDs().get_WRITE_UART_CHAR(), b"\nset POWER_1V8 1\n")
                await asyncio.sleep(0.1)
                await self.client.write_gatt_char(eu.UUIDs().get_WRITE_UART_CHAR(), b"\nset ppg_enable 1\n")
                await asyncio.sleep(0.1)
                await self.client.write_gatt_char(eu.UUIDs().get_WRITE_UART_CHAR(), b"\nsetup ppg\n")
                await asyncio.sleep(0.1)
                print("Message sent to device.")
            except Exception as e:
                print(f"Failed to send message: {e}")
        else:
            print("Connect device first.")

    @asyncSlot()
    async def stop_measure(self):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(eu.UUIDs().get_WRITE_UART_CHAR(), b"\nset ppg_enable 0\n")
            await asyncio.sleep(0.1)
            await self.client.write_gatt_char(eu.UUIDs().get_WRITE_UART_CHAR(), b"\nsetup ppg\n")
            self.timer.stop()
        else:
            print("Connect device first.")

    def closeEvent(self, event):
        if self.client and self.client.is_connected:
            asyncio.run(self.client.disconnect())
        event.accept()

if __name__ == "__main__":
    app = QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    controller = BleController()
    controller.show()
    with loop:
        loop.run_forever()


# 기존 라이센스
# 8d0eadd4-73f6-4368-94ad-3c81db176a67
# A107

# 61f95a5a-cf1c-47d0-a795-302666b85b27



# 안되는 라이센스
# 1c274fa5-127c-4f52-9a21-2252735b1382
# f4bc3d9f-49f7-4246-a476-ce21ca153e90