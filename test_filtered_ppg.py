import numpy as np

# 초기화 변수 (필요에 따라 정의)
total_data = []  # 전체 데이터를 저장하는 리스트
interpolated_ppg = []  # 새로 보간된 PPG 데이터를 저장하는 리스트
prev_data = []  # 이전 데이터를 저장하는 리스트


class PolynomialDetrendProcessor:
    def __init__(self, ppg_array, window_size, window_interval, order):
        self.ppg_array = ppg_array
        self.window_size = window_size
        self.window_interval = window_interval
        self.order = order
        self.ppg_array_without_dc = []

    def process(self):
        x_values = [i + 1 for i in range(self.window_size)]
        y_values = self.ppg_array[:self.window_size]

        # Vandermonde matrix 생성
        vandermonde_matrix = [
            [x ** j for j in range(self.order + 1)] for x in x_values
        ]

        # Normal equation: (X^T * X) * a = X^T * y
        x_transposed = self._transpose(vandermonde_matrix)
        x_transposed_x = self._matrix_multiply(x_transposed, vandermonde_matrix)
        x_transposed_y = self._matrix_vector_multiply(x_transposed, y_values)

        # Gaussian elimination
        coefficients = self._gaussian_elimination(x_transposed_x, x_transposed_y)

        # 추세를 제거한 데이터 계산
        for i in range(self.window_size):
            trend = sum(
                coefficients[j] * (x_values[i] ** j) for j in range(self.order + 1)
            )
            detrended_value = y_values[i] - trend
            self.ppg_array_without_dc.append(round(detrended_value, 4))

        return self.ppg_array_without_dc

    def _transpose(self, matrix):
        return list(map(list, zip(*matrix)))

    def _matrix_multiply(self, a, b):
        return [
            [sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))
        ]

    def _matrix_vector_multiply(self, matrix, vector):
        return [sum(row[i] * vector[i] for i in range(len(vector))) for row in matrix]

    def _gaussian_elimination(self, a, b):
        n = len(a)
        for i in range(n):
            # Pivot
            max_index = max(range(i, n), key=lambda x: abs(a[x][i]))
            a[i], a[max_index] = a[max_index], a[i]
            b[i], b[max_index] = b[max_index], b[i]

            # Eliminate
            for j in range(i + 1, n):
                factor = a[j][i] / a[i][i]
                b[j] -= factor * b[i]
                for k in range(i, n):
                    a[j][k] -= factor * a[i][k]

        # Back substitution
        x = [0] * n
        for i in range(n - 1, -1, -1):
            x[i] = (b[i] - sum(a[i][j] * x[j] for j in range(i + 1, n))) / a[i][i]
        return x


class MovingAverageFilter:
    def __init__(self, window_size):
        self.window_size = window_size
        self._values = []

    def filter(self, new_value):
        """새로운 값을 추가하고 이동 평균 계산"""
        self._values.append(new_value)

        # 윈도우 크기를 초과하면 오래된 값 제거
        if len(self._values) > self.window_size:
            self._values.pop(0)

        # 이동 평균 계산
        average = sum(self._values) / len(self._values)
        return average

    def clear(self):
        """내부 값 초기화"""
        self._values.clear()


class WeightedMovingAverageFilter:
    def __init__(self, window_size):
        self.window_size = window_size
        self._values = []
        self._weights = [i + 1000 for i in range(window_size)]

    def filter(self, new_value):
        """새로운 값을 추가하고 가중 이동 평균 계산"""
        self._values.append(new_value)

        # 윈도우 크기를 초과하면 오래된 값 제거
        if len(self._values) > self.window_size:
            self._values.pop(0)

        # 가중 이동 평균 계산
        current_size = len(self._values)
        total_weight = sum(self._weights[:current_size])
        weighted_sum = sum(self._values[i] * self._weights[i] for i in range(current_size))

        return weighted_sum / total_weight

    def clear(self):
        """내부 값 초기화"""
        self._values.clear()


wfilter = WeightedMovingAverageFilter(13)
filter = MovingAverageFilter(13)

# 입력 변수
global_noise_threshold = 5.0
threshold1 = 3.0
threshold2 = 6.0
threshold3 = 10.0
result_hr = {'value': 150}  # 예제용 HR 값
fs = 50  # 샘플링 주파수 (50Hz)

# 1. totalData 관리
if len(total_data) > 50:
    total_data = total_data[50:]  # 앞 50개의 데이터를 제거

total_data.extend(interpolated_ppg)  # interpolated_ppg 데이터를 추가

# 2. Noise Threshold 조건 확인
tr = 2
if threshold1 < global_noise_threshold <= threshold2:
    tr = 5
elif global_noise_threshold > threshold2:
    tr = 7
    if global_noise_threshold > threshold3 and result_hr['value'] > 140:
        tr = 25


processor_raw = PolynomialDetrendProcessor(total_data, 2 * fs, 10, tr)
interpolated_detrend_ppg = processor_raw.process()

# 4. 이전 데이터 저장
prev_data = interpolated_detrend_ppg.copy()

# 5. WFilter와 Filter를 적용하여 데이터 필터링
wfiltered_data = [wfilter.filter(value) for value in interpolated_detrend_ppg[:50]]
filtered_data = [filter.filter(value) for value in wfiltered_data[:50]]
