import asyncio
from PySide6.QtCore import QTimer
from bleak import BleakScanner, BleakClient
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QListWidget, QVBoxLayout, QHBoxLayout, \
    QWidget, QMessageBox
from qasync import QEventLoop, asyncSlot
from scipy.interpolate import interp1d
import numpy as np
import time
from newert_pro import HeartRateAnalyzer

from newert_utils import UUIDs, DataParser

class BleController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE 연결")
        self.resize(1250, 500)

        # Material 스타일 적용
        with open("design.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        self.data_queue = []
        self.address = ''
        self.device_id = ''
        self.client = None

        # Buffers for data and timing
        self.ppg_buffer = []
        self.acc_buffer = []
        self.gyro_buffer = []
        self.mag_buffer = []
        self.last_timestamp = time.time()

        # Timer 설정
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
        self.hr_analyzer = HeartRateAnalyzer(cal_hr_time=5)

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
                self.device_list.addItem(f"{device.name} - {device.address}")

    @asyncSlot()
    async def connect_to_device(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            self.device_id, self.address = selected_item.text().split(" - ")
            try:
                await self.connect_and_receive_data(self.address)
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
            await self.client.start_notify(UUIDs().get_READ_PPG_CHAR(), self.notification_handler)
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
        parser = DataParser()
        try:
            parsed_data = parser.parse_data(bytes(data))  # Parse the incoming data
        except Exception as e:
            print(f"Error parsing data: {e}")
            return

        # Log parsed data to inspect its structure if 'ppg' key is missing
        for item in parsed_data:
            if not all(key in item for key in ['ppg', 'acc', 'gyro', 'mag']):
                # print(f"Unexpected data format: {item}")
                continue  # Skip items that don't have all required keys

            # Buffer data if all keys are present
            self.ppg_buffer.append(item['ppg'])
            self.acc_buffer.append(item['acc'])
            self.gyro_buffer.append(item['gyro'])
            self.mag_buffer.append(item['mag'])
            # self.update_data_display(str(item))

        # Check if one second has passed
        current_timestamp = time.time()
        if current_timestamp - self.last_timestamp >= 1.0:
            # self.process_and_print_data()
            self.process_and_print_data()
            self.last_timestamp = current_timestamp

    import numpy as np
    from scipy.interpolate import interp1d

    def process_and_print_data(self):
        # Interpolate each buffer to 50 points, with support for 3D data
        def interpolate_data(buffer, num_points=50):
            buffer = np.array(buffer)  # Ensure buffer is a NumPy array
            if len(buffer) < 2:
                # Handle 1D and 3D data by matching the shape of buffer
                shape = (num_points,) + buffer.shape[1:] if buffer.ndim > 1 else (num_points,)
                result = np.tile(buffer[0], shape) if len(buffer) > 0 else np.zeros(shape)
                return np.round(result, decimals=3)  # Round to 3 decimal places

            # Interpolation
            x = np.linspace(0, len(buffer) - 1, num=len(buffer))
            f = interp1d(x, buffer, kind='linear', axis=0, fill_value="extrapolate")
            x_new = np.linspace(0, len(buffer) - 1, num=num_points)
            result = f(x_new)
            return np.round(result, decimals=3)  # Round to 3 decimal places

        # Interpolate each sensor data to 50 points, or use a default value if it fails
        try:
            ppg_interp = interpolate_data(self.ppg_buffer, 50).tolist()
        except Exception as e:
            print(f"PPG interpolation error: {e}")
            ppg_interp = [0] * 50  # Default to zeros if interpolation fails

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

        # Structure the result
        result = {
            "ppg": ppg_interp,
            "acc": acc_interp,
            "gyro": gyro_interp,
            "mag": mag_interp
        }

        # Print the structured result
        # print("Result:", result)

        hr_value, filter_list = self.hr_analyzer.update_hr(ppg_interp, acc_interp)
        print(f"Heart Rate: {hr_value}")
        print(f"Filter List: {filter_list}")


        self.update_data_display("1 second data has been collected. Check your terminal.")

        # Clear buffers after processing
        self.ppg_buffer.clear()
        self.acc_buffer.clear()
        self.gyro_buffer.clear()
        self.mag_buffer.clear()

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
                await self.client.write_gatt_char(UUIDs().get_WRITE_UART_CHAR(), b"\nset POWER_1V8 1\n")
                await asyncio.sleep(0.1)
                await self.client.write_gatt_char(UUIDs().get_WRITE_UART_CHAR(), b"\nset ppg_enable 1\n")
                await asyncio.sleep(0.1)
                await self.client.write_gatt_char(UUIDs().get_WRITE_UART_CHAR(), b"\nsetup ppg\n")
                await asyncio.sleep(0.1)
                print("Message sent to device.")
            except Exception as e:
                print(f"Failed to send message: {e}")
        else:
            print("Connect device first.")

    @asyncSlot()
    async def stop_measure(self):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(UUIDs().get_WRITE_UART_CHAR(), b"\nset ppg_enable 0\n")
            await asyncio.sleep(0.1)
            await self.client.write_gatt_char(UUIDs().get_WRITE_UART_CHAR(), b"\nsetup ppg\n")
            self.timer.stop()
        else:
            print('Connect device first.')

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
