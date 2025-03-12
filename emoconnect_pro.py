import math
import numpy as np


#########################################
# PeakDetector 클래스
#########################################
class PeakDetector:
    @staticmethod
    def find_peaks(data, height=50, distance=1, max_num=10):
        """
        data: 실수형 리스트
        height: 피크 최소 높이 기준
        distance: 피크 간 최소 인덱스 차이
        max_num: 반환할 최대 피크 개수

        반환: 오름차순 정렬된 피크 인덱스 리스트
        """
        candidate_indices = []
        # 모든 피크 후보 (양쪽 이웃보다 큰 값)
        for i in range(1, len(data) - 1):
            if data[i] > data[i - 1] and data[i] > data[i + 1]:
                candidate_indices.append(i)
        # height 기준 필터링
        candidate_indices = [idx for idx in candidate_indices if data[idx] > height]
        # 값이 큰 순으로 정렬 후, distance 기준 필터링
        candidate_indices.sort(key=lambda idx: data[idx], reverse=True)
        peak_indices = []
        for idx in candidate_indices:
            is_peak = True
            for existing in peak_indices:
                if abs(idx - existing) < distance:
                    is_peak = False
                    break
            if is_peak:
                peak_indices.append(idx)
                if len(peak_indices) == max_num:
                    break
        return sorted(peak_indices)

    @staticmethod
    def detect_peaks(data):
        """
        1차 및 2차 미분을 이용하여 피크 감지.
        data: 실수형 리스트
        반환: 피크 인덱스 리스트
        """
        if len(data) < 3:
            return []
        first_derivative = [data[i] - data[i - 1] for i in range(1, len(data))]
        second_derivative = [first_derivative[i] - first_derivative[i - 1] for i in range(1, len(first_derivative))]
        peak_indices = []
        for i in range(1, len(second_derivative)):
            if second_derivative[i - 1] > 0 and second_derivative[i] < 0:
                peak_indices.append(i)
        return peak_indices


#########################################
# PolynomialDetrendProcessor 클래스
#########################################
class PolynomialDetrendProcessor:
    def __init__(self, ppg_array, window_size, window_interval, order):
        """
        ppg_array: PPG 데이터 리스트
        window_size: 분석에 사용할 데이터 포인트 수 (여기서는 100, 즉 2초 데이터 @50Hz)
        window_interval: (현재 구현에서는 사용되지 않음)
        order: 다항식 차수
        """
        self.ppg_array = ppg_array
        self.window_size = window_size
        self.window_interval = window_interval
        self.order = order

    def process(self):
        """
        ppg_array의 앞 window_size 개 데이터를 사용하여 다항식 피팅 후,
        추세(DC 성분)를 제거한 데이터를 반환.
        """
        x_values = np.array([i + 1 for i in range(self.window_size)], dtype=float)
        y_values = np.array(self.ppg_array[:self.window_size], dtype=float)
        X = np.vander(x_values, N=self.order + 1, increasing=True)
        XtX = np.dot(X.T, X)
        Xty = np.dot(X.T, y_values)
        coefficients = np.linalg.solve(XtX, Xty)
        detrended = []
        for i in range(self.window_size):
            trend = sum(coefficients[j] * (x_values[i] ** j) for j in range(self.order + 1))
            detrended_value = y_values[i] - trend
            detrended.append(round(detrended_value, 4))
        return detrended


#########################################
# HeartRateAnalyzer 클래스
#########################################
class HeartRateAnalyzer:
    def __init__(self, cal_hr_time=5, threshold1=5.0, threshold2=10.0, threshold3=15.0):
        """
        cal_hr_time: 안정적인 심박수 계산을 위한 최소 분석 주기 횟수 (예: 5번 주기)
        threshold1, threshold2, threshold3: 가속도 노이즈 임계값 기준
        """
        self.ppg_array = [0.0] * 50  # 초기 PPG 버퍼 (첫 50 샘플)
        self.check_hr_count = 0
        self.hr_error_count = 0
        self.peak_error_count = 0
        self.is_fitting = False
        self.is_wearing = True
        self.is_moving_noise = False
        self.global_noise_threshold = 0.0
        self.result_hr = 0.0
        self.peak_bpm_values = []
        self.cal_hr_time = cal_hr_time
        self.threshold1 = threshold1
        self.threshold2 = threshold2
        self.threshold3 = threshold3

    def calculate_stddev(self, values):
        mean = np.mean(values)
        variance = np.mean((np.array(values) - mean) ** 2)
        return math.sqrt(variance)

    def update_hr(self, interpolated_ppg, interpolated_acc):
        """
        interpolated_ppg: 새로운 PPG 데이터 리스트
        interpolated_acc: 새로운 가속도 데이터 리스트, 각 항목은 [x, y, z]

        50Hz 기준, 2초분(100샘플) 데이터가 모이면 HR을 계산합니다.
        Flutter 코드의 안정화 및 노이즈 조건 분기 로직을 반영합니다.
        """
        # 새로운 PPG 데이터 추가
        self.ppg_array.extend(interpolated_ppg)

        # 2초분(100 샘플) 이상이면 계산 시작
        if len(self.ppg_array) >= 100:
            # 안정화 대기: check_hr_count가 cal_hr_time 미만이면 안정화 진행
            if self.check_hr_count < self.cal_hr_time:
                self.is_fitting = False
                if not self.is_moving_noise:
                    self.check_hr_count += 1

            # 초기 detrend 처리 (order = 2)
            processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 2)
            detrend_value = processor.process()

            # 센서 미착용 판단: PPG 데이터의 합이 0이면
            if sum(self.ppg_array) == 0:
                print("[Sensor] PPG sensor reading is 0. Sensor not worn.")
                self.is_wearing = False
                self.check_hr_count = 0
                self.result_hr = 0.0
                self.peak_bpm_values.clear()
                return self.result_hr, detrend_value
            else:
                self.is_wearing = True

            # 가속도 데이터 처리
            dataSize = len(interpolated_acc)
            if dataSize > 0:
                xMean = sum(entry[0] for entry in interpolated_acc) / dataSize
                yMean = sum(entry[1] for entry in interpolated_acc) / dataSize
                zMean = sum(entry[2] for entry in interpolated_acc) / dataSize
                xVariance = sum((entry[0] - xMean) ** 2 for entry in interpolated_acc) / dataSize
                yVariance = sum((entry[1] - yMean) ** 2 for entry in interpolated_acc) / dataSize
                zVariance = sum((entry[2] - zMean) ** 2 for entry in interpolated_acc) / dataSize
                xStdDev = math.sqrt(xVariance)
                yStdDev = math.sqrt(yVariance)
                zStdDev = math.sqrt(zVariance)

            else:
                xStdDev = yStdDev = zStdDev = 0
            noiseThreshold = xStdDev + yStdDev + zStdDev
            self.global_noise_threshold = noiseThreshold

            # 움직임 노이즈 판단 기준을 조정 (threshold를 낮추거나 변경)
            self.is_moving_noise = True if noiseThreshold > 5 else False  # 기준값 500으로 설정 (기존 5.0)

            # 안정화 및 센서 착용 상태에서 HR 계산 진행
            if self.check_hr_count >= self.cal_hr_time and self.is_wearing:
                self.is_fitting = True
                mean_val = np.mean(detrend_value)
                variance = np.mean((np.array(detrend_value) - mean_val) ** 2)
                standard_deviation = math.sqrt(variance)
                threshold_height = mean_val + 0.5 * standard_deviation
                min_distance = 12
                max_num = 8
                sampling_interval = 0.02

                # 첫 번째 피크 검출 및 HR 산출
                peak_indices = PeakDetector.find_peaks(detrend_value,
                                                       height=threshold_height,
                                                       distance=min_distance,
                                                       max_num=max_num)
                peak_intervals = []
                for i in range(1, len(peak_indices)):
                    index_diff = peak_indices[i] - peak_indices[i - 1]
                    time_diff = index_diff * sampling_interval
                    if time_diff <= 0.20 or time_diff >= 1.5:
                        continue
                    temp_hr = 60 / time_diff
                    peak_intervals.append(time_diff)

                # 추가 분기: 노이즈 조건에 따른 재처리
                if self.threshold1 <= noiseThreshold < self.threshold2:
                    processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 5)
                    detrend_value = processor.process()
                    mean_val = np.mean(detrend_value)
                    variance = np.mean((np.array(detrend_value) - mean_val) ** 2)
                    standard_deviation = math.sqrt(variance)
                    threshold_height = mean_val + 0.5 * standard_deviation
                    peak_indices = PeakDetector.find_peaks(detrend_value,
                                                           height=threshold_height,
                                                           distance=min_distance,
                                                           max_num=max_num)
                    peak_intervals = []
                    for i in range(1, len(peak_indices)):
                        index_diff = peak_indices[i] - peak_indices[i - 1]
                        time_diff = index_diff * sampling_interval
                        if time_diff <= 0.25 or time_diff >= 1.5:
                            continue
                        temp_hr = 60 / time_diff
                        peak_intervals.append(time_diff)

                elif noiseThreshold >= self.threshold2:
                    if noiseThreshold >= self.threshold3 and self.result_hr >= 140:
                        processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 25)
                        detrend_value = processor.process()
                        mean_val = np.mean(detrend_value)
                        variance = np.mean((np.array(detrend_value) - mean_val) ** 2)
                        standard_deviation = math.sqrt(variance)
                        threshold_height = mean_val + 0.5 * standard_deviation
                        peak_indices = PeakDetector.find_peaks(detrend_value,
                                                               height=threshold_height,
                                                               distance=min_distance,
                                                               max_num=max_num)
                        peak_intervals = []
                        for i in range(1, len(peak_indices)):
                            index_diff = peak_indices[i] - peak_indices[i - 1]
                            time_diff = index_diff * sampling_interval
                            if time_diff <= 0.25 or time_diff >= 1.5:
                                continue
                            temp_hr = 60 / time_diff
                            peak_intervals.append(time_diff)
                    else:
                        processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 7)
                        detrend_value = processor.process()
                        mean_val = np.mean(detrend_value)
                        variance = np.mean((np.array(detrend_value) - mean_val) ** 2)
                        standard_deviation = math.sqrt(variance)
                        threshold_height = mean_val + 0.5 * standard_deviation
                        peak_indices = PeakDetector.find_peaks(detrend_value,
                                                               height=threshold_height,
                                                               distance=min_distance,
                                                               max_num=max_num)
                        peak_intervals = []
                        for i in range(1, len(peak_indices)):
                            index_diff = peak_indices[i] - peak_indices[i - 1]
                            time_diff = index_diff * sampling_interval
                            if time_diff <= 0.25 or time_diff >= 1.5:
                                continue
                            temp_hr = 60 / time_diff
                            peak_intervals.append(time_diff)

                if len(self.peak_bpm_values) > 15:
                    self.peak_bpm_values.pop(0)
                if peak_intervals:
                    self.hr_error_count = 0
                    self.peak_error_count = 0
                    avg_peak_interval = np.mean(peak_intervals)
                    bpm = 60 / avg_peak_interval
                    if not self.peak_bpm_values:
                        self.peak_bpm_values.append(bpm)
                        self.result_hr = bpm
                    else:
                        self.peak_bpm_values.append(bpm)
                        self.result_hr = np.mean(self.peak_bpm_values)

            # 데이터 오버랩: 다음 2초 분석을 위해 최신 50개 샘플만 유지 (1초 중첩)
            self.ppg_array = self.ppg_array[-50:]
            return self.result_hr, detrend_value
        else:
            return self.result_hr, []
