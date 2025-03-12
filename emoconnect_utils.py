# emoconnect_utils.py
import asyncio


class UUIDs:
    """
    UUID 관리 클래스
    BLE 통신에 필요한 서비스와 특성(UUID)을 제공합니다.
    """
    def __init__(self):
        self.UART_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
        self.READ_UART_CHAR = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
        self.WRITE_UART_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
        self.PPG_SERVICE = "00001000-0000-1000-8000-00805f9b34fb"
        self.READ_PPG_CHAR = "00001100-0000-1000-8000-00805f9b34fb"
        self.BATT_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
        self.READ_BATT_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"

    def get_UART_SERVICE(self):
        return self.UART_SERVICE

    def get_READ_UART_CHAR(self):
        return self.READ_UART_CHAR

    def get_WRITE_UART_CHAR(self):
        return self.WRITE_UART_CHAR

    def get_PPG_SERVICE(self):
        return self.PPG_SERVICE

    def get_READ_PPG_CHAR(self):
        return self.READ_PPG_CHAR

    def get_BATT_SERVICE(self):
        return self.BATT_SERVICE

    def get_READ_BATT_CHAR(self):
        return self.READ_BATT_CHAR


class DataParser:
    """
    데이터 파서 클래스
    BLE 등에서 수신된 raw bytes 데이터를 파싱하여,
    배터리 정보 또는 ppg, 가속도, 자이로, 자기장 데이터를 추출합니다.
    """
    def parse_data(self, data: bytes) -> list:
        parsed_data = []
        if data[0:4] == b"BATT":
            # 배터리 데이터 처리: 배터리 레벨과 카운트를 추출
            battery_level = min(max(data[6], 0), 100)
            count = (data[9] << 8) | data[8]
            parsed_data.append({'battery': battery_level, 'count': count})
        else:
            chunk_size = 20
            num_chunks = len(data) // chunk_size
            for i in range(num_chunks):
                base = 20 * i
                ppg = ((data[base + 1] << 8) | data[base + 0])
                acc_x = self.float16_to_float32((data[base + 3] << 8) | data[base + 2])
                acc_y = self.float16_to_float32((data[base + 5] << 8) | data[base + 4])
                acc_z = self.float16_to_float32((data[base + 7] << 8) | data[base + 6])
                gyro_x = self.float16_to_float32((data[base + 9] << 8) | data[base + 8])
                gyro_y = self.float16_to_float32((data[base + 11] << 8) | data[base + 10])
                gyro_z = self.float16_to_float32((data[base + 13] << 8) | data[base + 12])
                mag_x = self.float16_to_float32((data[base + 15] << 8) | data[base + 14])
                mag_y = self.float16_to_float32((data[base + 17] << 8) | data[base + 16])
                mag_z = self.float16_to_float32((data[base + 19] << 8) | data[base + 18])
                parsed_data.append({
                    'ppg': ppg,
                    'acc': [acc_x, acc_y, acc_z],
                    'gyro': [gyro_x, gyro_y, gyro_z],
                    'mag': [mag_x, mag_y, mag_z]
                })
        return parsed_data

    def float16_to_float32(self, value):
        """
        임시 변환 함수: 실제 변환 알고리즘으로 대체 필요.
        현재는 단순히 입력 값을 float으로 변환합니다.
        """
        return float(value)


