import asyncio
from PySide6.QtCore import QTimer
from bleak import BleakScanner, BleakClient
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QListWidget, QVBoxLayout, QHBoxLayout, \
    QWidget, QMessageBox
from qasync import QEventLoop, asyncSlot
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
        parsed_data = parser.parse_data(bytes(data))  # bytearray를 bytes로 변환하여 전달
        for item in parsed_data:
            print(item)
            self.update_data_display(str(item))

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
