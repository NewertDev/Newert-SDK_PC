import numpy as np
import math
import random
from scipy.signal import find_peaks
import asyncio

class PeakDetector:
    @staticmethod
    def find_peaks(data, height=50, distance=1, max_num=10):
        peak_indices = []
        candidate_indices = []

        for i in range(1, len(data) - 1):
            if data[i] > data[i - 1] and data[i] > data[i + 1]:
                candidate_indices.append(i)

        candidate_indices = [idx for idx in candidate_indices if data[idx] > height]
        candidate_indices.sort(key=lambda x: data[x], reverse=True)

        for idx in candidate_indices:
            if all(abs(idx - peak) >= distance for peak in peak_indices):
                peak_indices.append(idx)
                if len(peak_indices) == max_num:
                    break

        return sorted(peak_indices)

class PolynomialDetrendProcessor:
    def __init__(self, ppg_array, window_size, window_interval, order):
        self.ppg_array = ppg_array
        self.window_size = window_size
        self.window_interval = window_interval
        self.order = order
        self.ppg_array_without_dc = []

    def process(self):
        x_values = np.arange(1, self.window_size + 1)
        y_values = self.ppg_array[:self.window_size]
        vandermonde_matrix = np.vander(x_values, N=self.order + 1, increasing=True)
        x_transposed = vandermonde_matrix.T
        x_transposed_x = x_transposed @ vandermonde_matrix
        x_transposed_y = x_transposed @ y_values
        coefficients = np.linalg.solve(x_transposed_x, x_transposed_y)
        for i in range(self.window_size):
            trend = sum(coefficients[j] * (x_values[i] ** j) for j in range(self.order + 1))
            detrended_value = y_values[i] - trend
            self.ppg_array_without_dc.append(round(detrended_value, 4))
        return self.ppg_array_without_dc

class HeartRateAnalyzer:
    def __init__(self, cal_hr_time):
        self.hr_graph_elapsed = 0.0
        self.ppg_array = [0.0] * 50
        self.check_hr_count = 0
        self.hr_error_count = 0
        self.peak_error_count = 0
        self.result_hr = 0.0
        self.peak_bpm_values = []
        self.cal_hr_time = cal_hr_time

    def calculate_stddev(self, values):
        mean = np.mean(values)
        variance = np.mean((values - mean) ** 2)
        return math.sqrt(variance)

    def update_hr(self, interpolated_ppg, interpolated_acc):
        self.ppg_array.extend(interpolated_ppg)

        print("len ppg_array : ", len(self.ppg_array))
        if len(self.ppg_array) >= 100:
            detrend_processor = PolynomialDetrendProcessor(self.ppg_array, 100, 10, 2)
            detrend_value = detrend_processor.process()

            is_ppg_zero = sum(self.ppg_array)
            if is_ppg_zero == 0:
                self.check_hr_count = 0
                self.result_hr = 0.0
                self.peak_bpm_values.clear()


            x_std = self.calculate_stddev([entry[0] for entry in interpolated_acc])
            y_std = self.calculate_stddev([entry[1] for entry in interpolated_acc])
            z_std = self.calculate_stddev([entry[2] for entry in interpolated_acc])

            print("x_std, y_std, z_std", x_std, y_std, z_std)
            noise_threshold = x_std + y_std + z_std
            print("noise_threshold", noise_threshold)

            mean = np.mean(detrend_value)
            std_dev = self.calculate_stddev(detrend_value)

            threshold_height = mean + (0.5 * std_dev)
            peak_indices = PeakDetector.find_peaks(detrend_value, height=threshold_height, distance=12)

            peak_intervals = []
            sampling_interval = 0.02

            print('peak_indices',peak_indices)

            for i in range(1, len(peak_indices)):
                index_diff = peak_indices[i] - peak_indices[i - 1]
                time_diff = index_diff * sampling_interval

                if 0.25 <= time_diff <= 1.5:
                    temp_hr = 60 / time_diff
                    if len(self.peak_bpm_values) >= 15:
                        if (self.result_hr != 0):
                            if abs((self.result_hr - temp_hr) / self.result_hr) < 0.20:
                                self.peak_bpm_values.append(temp_hr)
                                self.result_hr = np.mean(self.peak_bpm_values)
                    else:
                        self.peak_bpm_values.append(temp_hr)
                        self.result_hr = np.mean(self.peak_bpm_values)

            if len(self.peak_bpm_values) > 15:
                self.peak_bpm_values.pop(0)

        self.ppg_array = self.ppg_array[-50:]
        return [self.result_hr, detrend_value]

# Example usage:
# analyzer = HeartRateAnalyzer(cal_hr_time=5)
# interpolated_ppg = [random.uniform(0.8, 1.2) for _ in range(50)]
# interpolated_acc = [[random.uniform(0.1, 0.5) for _ in range(3)] for _ in range(50)]
