# emoconnect_utils.py
import asyncio
import struct


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
        IEEE-754 16비트 부동소수점 값을 32비트 부동소수점 값으로 변환하는 함수.
        """
        # 16비트 float 값을 부호, 지수, 가수로 나누어 처리
        sign = (value >> 15) & 0x1  # 부호 비트 (1비트)
        exponent = (value >> 10) & 0x1F  # 지수 비트 (5비트)
        fraction = value & 0x3FF  # 가수 비트 (10비트)

        # 지수가 0인 경우 (서브노멀 숫자 처리)
        if exponent == 0:
            # 서브노멀 숫자 처리를 위한 지수 조정
            exponent = 0x1F
            fraction = fraction * 8192  # 2^23 / 2^10 = 8192로 가수 값 조정
        else:
            # 지수가 0이 아니면, 지수 조정
            exponent -= 15
            exponent += 127  # 32비트 float의 지수 오프셋

        # 32비트 float 형식으로 변환
        # 1비트 부호, 8비트 지수, 23비트 가수로 구성
        result = (sign << 31) | (exponent << 23) | (fraction << 13)

        # struct를 이용하여 32비트 float 값으로 변환
        float_value = struct.unpack('f', struct.pack('I', result))[0]

        return float_value



