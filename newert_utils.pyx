# ble_utils.pyx

# UUID 관리 클래스
cdef class UUIDs:
    cdef str UART_SERVICE
    cdef str READ_UART_CHAR
    cdef str WRITE_UART_CHAR
    cdef str PPG_SERVICE
    cdef str READ_PPG_CHAR
    cdef str BATT_SERVICE
    cdef str READ_BATT_CHAR

    def __cinit__(self):
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

# newert_utils.pyx

cdef class DataParser:
    cpdef list parse_data(self, bytes data):  # self 인수 포함, bytes로 데이터 수신
        parsed_data = []
        if data[0:4] == b"BATT":
            battery_level = min(max(data[6], 0), 100)
            count = (data[9] << 8) | data[8]
            parsed_data.append({'battery': battery_level, 'count': count})
        else:
            chunk_size = 20
            for i in range(len(data) // chunk_size):
                ppg = ((data[20 * i + 1] << 8) | data[20 * i + 0])
                acc_x = self.float16_to_float32((data[20 * i + 3] << 8) | data[20 * i + 2])
                acc_y = self.float16_to_float32((data[20 * i + 5] << 8) | data[20 * i + 4])
                acc_z = self.float16_to_float32((data[20 * i + 7] << 8) | data[20 * i + 6])
                gyro_x = self.float16_to_float32((data[20 * i + 9] << 8) | data[20 * i + 8])
                gyro_y = self.float16_to_float32((data[20 * i + 11] << 8) | data[20 * i + 10])
                gyro_z = self.float16_to_float32((data[20 * i + 13] << 8) | data[20 * i + 12])
                mag_x = self.float16_to_float32((data[20 * i + 15] << 8) | data[20 * i + 14])
                mag_y = self.float16_to_float32((data[20 * i + 17] << 8) | data[20 * i + 16])
                mag_z = self.float16_to_float32((data[20 * i + 19] << 8) | data[20 * i + 18])

                parsed_data.append({
                    'ppg': ppg,
                    'acc': [acc_x, acc_y, acc_z],
                    'gyro': [gyro_x, gyro_y, gyro_z],
                    'mag': [mag_x, mag_y, mag_z]
                })
        return parsed_data

    cdef float16_to_float32(self, value):
        return float(value)  # 실제 변환 알고리즘으로 대체 필요
